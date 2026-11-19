import json, os, pathlib, secrets, subprocess, sys, threading, time
from datetime import date
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field, AwareDatetime
from services.schemas import Record, Strict, MealComponent, inspect_record
from services.store import Store
from services.scheduler import build_plan, diff_plans
from services.calculators import summarize, comparable_measurements, nutrient_totals
from services.rag import Retriever
from services.rules import REGISTRY
from services.journal import prepare_journal,segments,classification_prompt,compact_journal,compact_record,NON_CAPTURE_LANGUAGE,capture_time
from services.chat import answer_chat
from services.chat_model import generate_chat
from services import llm
from services.model_runtime import adapter_for,runtime_status
from services.learned_assistant import learned_request
from services.chat_routing import classification_messages,OFFTOPIC,out_of_scope_response,is_usage_question,usage_response
from services.chat_management import management_request,record_label
from services.health_search import HealthSearch
from services.agent import agent_request,wants_menu
from services.menu_recommendations import recommend_meals
from services.personalization import personal_context
from services.nutrition import estimate_meal,daily_energy,ZONE
from services.calorie_chat import calorie_request
from services.care_plan import care_plan_request
from services.chat_presets import preset_request
from services.food_reference import FOODS

ROOT=pathlib.Path(__file__).resolve().parents[1]
# Cloud mode (RUAMWAN_CLOUD=1): the record service runs on a server, reachable
# only by the website backend with the API key. Browser sessions, the local
# demo and the API docs are switched off.
CLOUD=os.environ.get('RUAMWAN_CLOUD')=='1'
app=FastAPI(title='Baobuddy AI API',version='0.11.0',**({'docs_url':None,'redoc_url':None,'openapi_url':None} if CLOUD else {}))
extra_hosts=[h.strip() for h in os.environ.get('RUAMWAN_ALLOWED_HOSTS','').split(',') if h.strip()]
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver',*extra_hosts])
# SUPABASE_DB_URL moves every record to Supabase Postgres (private schema 'ruamwan').
store=Store(os.environ.get('LOCAL_DB',str(ROOT/'data/local.sqlite3')),database_url=os.environ.get('SUPABASE_DB_URL') or None,schema=os.environ.get('RUAMWAN_SCHEMA','ruamwan'))
lock=threading.RLock();model_lock=threading.Lock()
retriever=Retriever(ROOT/'data/knowledge/chunks.jsonl')
health_search=HealthSearch()

def classify_chat(query):
    output=generate_chat(classification_messages(query),model_lock,max_tokens=120)
    return json.loads(output['output'])

def session(request):
    authorization=request.headers.get('authorization')
    external_user=request.headers.get('x-ruamwan-user')
    if CLOUD and authorization is None:raise HTTPException(401,'Invalid API credentials')
    if authorization is not None or external_user is not None:
        key=os.environ.get('RUAMWAN_API_KEY','')
        if len(key)<32:raise HTTPException(503,'Server API integration is not configured')
        if not authorization or not secrets.compare_digest(authorization.encode(),('Bearer '+key).encode()):raise HTTPException(401,'Invalid API credentials')
        if not external_user or len(external_user)>200 or not external_user.isascii() or any(ord(c)<33 or ord(c)>126 for c in external_user):raise HTTPException(422,'X-Ruamwan-User must be a stable opaque authenticated user ID (1–200 ASCII characters)')
        return {'owner':store.integration_owner(external_user)}
    token=request.cookies.get('routine_session')
    s=store.session_get(token)
    if not s:raise HTTPException(401,'เปิดหน้าเริ่มต้นเพื่อสร้างเซสชันในเครื่อง')
    if request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('x-csrf-token',''),s['csrf']):raise HTTPException(403,'invalid confirmation token')
    return s

@app.middleware('http')
async def local_security(request,call_next):
    if CLOUD and (not request.url.path.startswith('/api/') or request.url.path=='/api/session'):return Response('Not found',404)
    try:size=int(request.headers.get('content-length','0'))
    except ValueError:return Response('Invalid length',400)
    if size>100000:return Response('Request too large',413)
    origin=request.headers.get('origin')
    if origin and origin not in ('http://localhost:8765','http://127.0.0.1:8765','http://testserver'):
        return Response('Cross-origin access denied',403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.exception_handler(ValueError)
async def value_error(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422,content={'detail':str(exc)})

@app.get('/')
def index():return FileResponse(ROOT/'demo/index.html')

@app.get('/api/session')
def new_session(request:Request,response:Response):
    token=request.cookies.get('routine_session')
    with lock:
        s=store.session_get(token)
        if not s:
            token=secrets.token_urlsafe(32);s={'owner':secrets.token_hex(16),'csrf':secrets.token_urlsafe(24)}
            store.session_save(token,s['owner'],s['csrf'])
    response.set_cookie('routine_session',token,httponly=True,samesite='strict',max_age=7*86400)
    return {'csrf':s['csrf'],'mode':'local_session','note':'เข้าถึงข้อมูลผ่านคุกกี้ของเบราว์เซอร์นี้ได้ 7 วันแม้เปิดเซิร์ฟเวอร์ใหม่ กรุณาส่งออกข้อมูลก่อนคุกกี้หมดอายุ; บัญชีถาวรรอ Supabase Auth'}

def draft(owner,payload,kind):
    # Stored in the database (not process memory) so any instance can confirm it.
    ident=secrets.token_urlsafe(24)
    if not store.draft_put(ident,owner,kind,payload):raise HTTPException(429,'มีรายการรอยืนยันมากเกินไป')
    return ident

@app.post('/api/records/preview')
def preview(record:Record,request:Request):
    s=session(request);check=inspect_record(record);p=record.model_dump(mode='json')
    return {'draft_id':draft(s['owner'],p,'record'),'record':p,'check':check,'can_confirm':check['can_record']}

class JournalRequest(Strict):
    text:str=Field(min_length=1,max_length=4000)
    captured_at:AwareDatetime|None=None
    use_model:bool=True
    compact:bool=True

@app.post('/api/journal/prepare')
def journal_prepare(body:JournalRequest,request:Request):
    session(request)
    result=prepare_journal(body.text,body.captured_at.isoformat() if body.captured_at else None)
    eligible=[x['text'] for x in result['unparsed'] if not NON_CAPTURE_LANGUAGE.search(x['text'])]
    if eligible and body.use_model and llm.available():
        try:
            output=generate_chat([{'role':'system','content':classification_prompt(eligible)},{'role':'user','content':'Return the category JSON only.'}],model_lock,max_tokens=1024)
            result=prepare_journal(body.text,result['captured_at'],output['output'])
            result['model_metrics']=output.get('metrics',{})
        except (HTTPException,ValueError,KeyError):
            result['model_note']='โมเดลยังแยกส่วนที่เหลือไม่ได้ เลือกหมวดเองได้'
    elif eligible and body.use_model and (ROOT/'models/typhoon-4bit/config.json').exists():
        if model_lock.acquire(blocking=False):
            try:
                prompt=classification_prompt(eligible)
                run=subprocess.run([sys.executable,str(ROOT/'scripts/inference.py'),'--task','generate','--max-tokens','1024'],input=json.dumps({'messages':[{'role':'system','content':prompt},{'role':'user','content':'Return the category JSON only.'}]},ensure_ascii=False),text=True,capture_output=True,timeout=90,cwd=ROOT)
                if run.returncode==0:
                    output=json.loads(run.stdout)
                    result=prepare_journal(body.text,result['captured_at'],output['output'])
                    result['model_metrics']=output.get('metrics',{})
                else:result['model_note']='โมเดลยังไม่พร้อม เลือกหมวดของข้อความที่เหลือได้เอง'
            except (subprocess.TimeoutExpired,ValueError,KeyError):
                result['model_note']='โมเดลยังแยกส่วนที่เหลือไม่ได้ เลือกหมวดเองได้'
            finally:model_lock.release()
        else:result['model_note']='โมเดลกำลังทำงาน เลือกหมวดของข้อความที่เหลือได้เอง'
    return compact_journal(result) if body.compact else result

class BatchRecords(Strict):
    records:list[Record]=Field(min_length=1,max_length=30)
    compact:bool=False

@app.post('/api/records/batch-preview')
def batch_preview(body:BatchRecords,request:Request):
    owner=session(request)['owner']
    prepared=[Record.model_validate(compact_record(r.model_dump(mode='json'))) if body.compact else r for r in body.records]
    checks=[inspect_record(r) for r in prepared]
    payload=[r.model_dump(mode='json') for r in prepared]
    consent=any(r['kind']=='consent' and r['data'].get('local_storage') is True for r in store.all_current(owner))
    included=any(r['kind']=='consent' and r['data'].get('local_storage') is True for r in payload)
    return {'draft_id':draft(owner,payload,'records_batch'),'records':payload,'checks':checks,'can_confirm':all(c['can_record'] for c in checks),'requires_consent':not consent and not included}

class Confirmation(Strict):
    draft_id:str
    idempotency_key:str
    confirmed:bool

class DeleteRecordsRequest(Strict):
    scope:Literal['records','all']='records'
    record_ids:list[str]=Field(default_factory=list,max_length=30)

@app.post('/api/records/delete-preview')
def delete_preview(body:DeleteRecordsRequest,request:Request):
    owner=session(request)['owner']
    if body.scope=='all' and body.record_ids:raise ValueError('การลบทั้งหมดไม่ระบุรายการแยก')
    with lock:
        preview=store.deletion_preview(owner,body.record_ids,body.scope)
        payload={k:preview[k] for k in ('scope','record_ids','input_revision','plan_ids')}
        return preview|{'draft_id':draft(owner,payload,'delete_records'),'labels':[record_label(r) for r in preview['records']], 'can_confirm':bool(preview['history_count'] or preview['plan_count'])}

@app.post('/api/confirm')
def confirm(body:Confirmation,request:Request):
    s=session(request)
    if body.confirmed is not True:raise ValueError('ต้องยืนยันก่อนบันทึก')
    with lock:
        d=store.draft_get(body.draft_id,s['owner'])
        if not d:raise HTTPException(404,'รายการยืนยันหมดอายุหรือไม่พบ')
        if d['kind']=='delete_records':
            result=store.confirm_delete(s['owner'],d['payload'],body.idempotency_key)
            # Invalidate old proposals that could recreate deleted information.
            store.drafts_clear(s['owner'],keep=body.draft_id)
            return result
        if d['kind']=='record':return store.confirm_record(s['owner'],d['payload'],body.idempotency_key)
        if d['kind']=='records_batch':return store.confirm_batch(s['owner'],d['payload'],body.idempotency_key)
        return store.confirm_plan(s['owner'],d['payload'],body.idempotency_key)

@app.get('/api/records')
def records(request:Request,limit:int=100,offset:int=0,history:bool=False):
    s=session(request);items=store.records(s['owner'],limit,offset,current=not history)
    return {'items':items,'revision':store.revision(s['owner']),
            'meal_energy':{r['id']:estimate_meal(r) for r in items if r['kind']=='meal'}}

class FoodEnergyRequest(Strict):
    name:str=Field(min_length=1,max_length=120)
    quantity:float|None=Field(default=None,gt=0,le=100000)
    unit:str|None=Field(default=None,max_length=40)
    food_state:Literal['raw','cooked','packaged','unknown']|None=None
    components:list[MealComponent]|None=Field(default=None,min_length=2,max_length=30)

@app.post('/api/food-energy')
def food_energy(body:FoodEnergyRequest,request:Request):
    session(request)
    return estimate_meal({'kind':'meal','text':body.name,'data':body.model_dump(exclude_none=True)})

def plan_for(owner,start_date,general_time_only=False):
    rev=store.revision(owner)
    rows=store.all_current(owner);profiles=[r for r in rows if r['kind']=='profile']
    if not profiles and not general_time_only:raise ValueError('ต้องยืนยันโปรไฟล์และเป้าหมายก่อน')
    # Capture revision before assembling; confirmation rejects concurrent changes.
    plan=build_plan(profiles[-1]['data'] if profiles else {},[r for r in rows if r['kind']=='routine'],[r for r in rows if r['kind']=='constraint'],start_date,rev,general_time_only=general_time_only)
    return plan|{'profile_record_id':profiles[-1]['id'] if profiles else None,'input_record_ids':[r['id'] for r in rows if r['kind'] in ('profile','routine','constraint')]}

class PlanRequest(Strict):
    start_date:date
    previous_plan_id:str|None=None
    reason:str=Field(default='',max_length=1000)
    general_time_only:bool=False

@app.post('/api/plans/preview')
def plan_preview(body:PlanRequest,request:Request):
    s=session(request);plan=plan_for(s['owner'],str(body.start_date),body.general_time_only)
    out={'plan':plan,'draft_id':draft(s['owner'],plan,'plan'),'can_confirm':plan['status']=='pass'}
    if body.previous_plan_id:
        if not body.reason.strip():raise ValueError('ระบุเหตุผลในการปรับหรือคืนแผน')
        old=store.get_plan(s['owner'],body.previous_plan_id)
        out['comparison']=diff_plans(old,plan,body.reason)
    return out

@app.get('/api/plans')
def plans(request:Request,limit:int=20,offset:int=0):return {'items':store.plans(session(request)['owner'],limit,offset)}

@app.get('/api/plans/{ident}/recheck')
def recheck(ident:str,request:Request):
    owner=session(request)['owner'];old=store.get_plan(owner,ident);current=plan_for(owner,old['start_date'],old.get('general_time_only',False))
    return {'original':old,'current_check':current,'comparison':diff_plans(old,current,'ตรวจด้วยข้อมูลล่าสุดทุกด้าน'),'requires_confirmation':True}

class Question(Strict):query:str=Field(min_length=1,max_length=1500)
@app.post('/api/knowledge')
def knowledge(body:Question,request:Request):session(request);return retriever.answer(body.query)

class ChatMessage(Strict):
    role:Literal['user','assistant']
    content:str=Field(min_length=1,max_length=4000)

class ChatRequest(Strict):
    messages:list[ChatMessage]=Field(min_length=1,max_length=20)
    scope:Literal['auto','my_data','knowledge']='auto'
    captured_at:AwareDatetime|None=None

@app.post('/api/chat')
def chat(body:ChatRequest,request:Request):
    owner=session(request)['owner']
    if body.messages[-1].role!='user' or not body.messages[-1].content.strip():raise ValueError('กรุณาพิมพ์คำถาม')
    if sum(len(m.content) for m in body.messages)>16000:raise ValueError('บทสนทนายาวเกินไป กรุณาเริ่มบทสนทนาใหม่')
    rows=store.all_current(owner)
    query=body.messages[-1].content.strip()
    if OFFTOPIC.search(query):return out_of_scope_response()
    if is_usage_question(query):return usage_response(query)
    captured=capture_time(body.captured_at.isoformat() if body.captured_at else None)
    preset=preset_request(query,rows,captured)
    if preset is not None:return preset
    managed=management_request(query,rows,captured)
    if managed is not None:return managed
    calories=calorie_request(query,rows)
    if calories is not None:return calories
    care=care_plan_request(query,rows)
    if care is not None:return care
    if wants_menu(query):
        result=recommend_meals(query,rows,generator=lambda messages:generate_chat(messages,model_lock,max_tokens=250))
        if query.startswith(('บันทึก','ช่วยบันทึก','จด')):
            action=agent_request(query,rows,captured)
            if action:
                result['actions']=action['actions']+result.get('actions',[])
                result['answer']+='\n\n'+action['answer']
        return result
    action=agent_request(query,rows,captured)
    if action is not None:return action
    if adapter_for('intent') or llm.available():
        learned=learned_request(query,lambda messages:generate_chat(messages,model_lock,max_tokens=80))
        if learned is not None:return learned
    return answer_chat([m.model_dump() for m in body.messages],body.scope,rows,retriever,
                       generator=lambda messages:generate_chat(messages,model_lock),
                       classifier=classify_chat,online_search=health_search.search)

class Extract(Strict):
    kind:str
    text:str=Field(min_length=1,max_length=4000)

@app.post('/api/extract')
def extract(body:Extract,request:Request):
    session(request)
    if body.kind not in ('meal','activity','sleep','medication','measurement','wellbeing','appointment'):raise ValueError('ชนิดบันทึกไม่รองรับ')
    if llm.available():
        output=llm.extract_record(body.kind,body.text);record=Record.model_validate(output['record']);check=inspect_record(record)
        status=output['metrics'].get('extraction_status','proposal')
        return {'record':record.model_dump(mode='json'),'check':check,'model_status':status,'metrics':output['metrics']}
    if not (ROOT/'models/typhoon-4bit/config.json').exists():raise HTTPException(503,'โมเดลในเครื่องยังไม่พร้อม ใช้ฟอร์มบันทึกได้')
    if not model_lock.acquire(blocking=False):raise HTTPException(429,'โมเดลกำลังทำงาน กรุณารอสักครู่')
    try:
        run=subprocess.run([sys.executable,str(ROOT/'scripts/inference.py'),'--task','extract'],input=json.dumps(body.model_dump(),ensure_ascii=False),text=True,capture_output=True,timeout=180,cwd=ROOT)
        if run.returncode:raise HTTPException(503,'โหลดโมเดลไม่สำเร็จ ตรวจสิทธิ Metal และ logs โดยไม่ส่งข้อมูลสุขภาพออกนอกเครื่อง')
        output=json.loads(run.stdout);record=Record.model_validate(output['record']);check=inspect_record(record)
        status=output['metrics'].get('extraction_status','proposal')
        if not any(v is not None for v in record.data.values()) and status=='proposal':status='no_supported_fields'
        return {'record':record.model_dump(mode='json'),'check':check,'model_status':status,'metrics':output['metrics']}
    finally:model_lock.release()

@app.get('/api/summary')
def summary(request:Request):
    rows=store.all_current(session(request)['owner'])
    from datetime import datetime
    return {'energy_summary':daily_energy(rows,datetime.now(ZONE).date()),'activity_sleep':summarize(rows),'measurements':comparable_measurements(rows),'counts':{k:sum(r['kind']==k for r in rows) for k in ('meal','activity','sleep','medication','appointment','measurement','wellbeing')},'incomplete_records':sum(inspect_record(Record.model_validate({k:v for k,v in r.items() if k not in ('id','version','created_at','status')}))['status']!='pass' for r in rows),'causal_claim':None}

@app.get('/api/personal-context')
def context(request:Request):return personal_context(store.all_current(session(request)['owner']))

@app.get('/api/food-catalog')
def food_catalog(request:Request):
    session(request)
    return {'items':[{'name':f['name'],'aliases':f['aliases'],'serving':f.get('serving'),'basis':f['basis']} for f in FOODS],
            'version':'2026-10-12-v2','not_measured_intake':True}

@app.get('/api/readiness')
def readiness():
    return {'domains':[{ 'domain':d,'recording':True,'knowledge':d in ('meal','activity','wellbeing'),'scheduling_confirmed_items':True,'clinical_recommendations':False} for d in ('meal','activity','sleep','medication','appointment','measurement','wellbeing')],'food_catalog':'curated_source_servings','dish_references':str(len(FOODS))+' cited examples; recipe/serving limits apply','meal_ideas':'6 ingredient-checked preparations; clinical review pending','agent_actions':['usage_help','navigate','journal_draft','profile_draft','record_edit','record_delete','routine_draft','plan_preview','export'],'activity_catalog':'educational_only','rules':REGISTRY,'model_available':(ROOT/'models/typhoon-4bit/config.json').exists(),'training_report':'reports/finetune-v2-results.md','model_runtime':runtime_status(),'production':False}

@app.get('/api/export')
def export(request:Request):return store.export(session(request)['owner'])

class Delete(Strict):confirmation: str
@app.post('/api/delete')
def delete(body:Delete,request:Request):
    s=session(request)
    if body.confirmation!='ลบข้อมูลของฉัน':raise ValueError('พิมพ์ ลบข้อมูลของฉัน เพื่อยืนยัน')
    store.drafts_clear(s['owner'])
    return store.delete(s['owner'])

if not CLOUD:app.mount('/static',StaticFiles(directory=ROOT/'demo'),name='static')

def api_schema():
    """Describe both supported transports; backend credentials stay off browsers."""
    if app.openapi_schema:return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema=get_openapi(title=app.title,version=app.version,routes=app.routes,
        description='Health assistant and reviewable actions. Server integration: Bearer API key + X-Ruamwan-User from authenticated backend. Local demo: cookie + CSRF. Writes always require preview and explicit user confirmation.')
    schema.setdefault('components',{})['securitySchemes']={
        'ServerKey':{'type':'http','scheme':'bearer','description':'RUAMWAN_API_KEY, server-to-server only'},
        'AuthenticatedUser':{'type':'apiKey','in':'header','name':'X-Ruamwan-User','description':'Stable opaque user ID supplied by trusted authenticated backend, never a browser-selected account'},
        'LocalSession':{'type':'apiKey','in':'cookie','name':'routine_session'},
        'LocalCSRF':{'type':'apiKey','in':'header','name':'X-CSRF-Token'}}
    for path,operations in schema['paths'].items():
        if not path.startswith('/api/') or path in ('/api/readiness','/api/session'):continue
        for method,operation in operations.items():
            if method not in ('get','post','delete','put','patch'):continue
            local={'LocalSession':[]}
            if method!='get':local['LocalCSRF']=[]
            operation['security']=[{'ServerKey':[],'AuthenticatedUser':[]},local]
    app.openapi_schema=schema
    return schema

app.openapi=api_schema
