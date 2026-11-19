"""SOFTWARE TEST FIXTURES ONLY. Tests validate contracts, not clinical efficacy."""
import json
from datetime import datetime
import pytest
from services.agent import agent_request,wants_menu
from services.journal import prepare_journal,compact_journal,compact_record
from services.personalization import personal_context
from services.menu_recommendations import recommend_meals
from services.food_reference import food_reference
from services.scheduler import build_plan
from services.schemas import Profile,Record,inspect_record
from tests.test_api import client

NOW=datetime.fromisoformat('2026-10-12T12:00:00+07:00')
def profile(**data):return {'id':'software-profile','kind':'profile','created_at':'2026-10-11T00:00:00Z','data':data}
def meal(text):
    r=compact_journal(prepare_journal(text,NOW.isoformat()))['items'][0]['record']
    return r|{'id':'software-'+text,'version':1}
def confirm(client,p,key):return client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':key,'confirmed':True})

@pytest.mark.parametrize('text,label,period',[('ตอนเช้ากินข้าวมันไก่ 1 จาน','ข้าวมันไก่','morning'),('กินเย็นตาโฟ','เย็นตาโฟ','unspecified'),('ดื่มชาเย็น','ชาเย็น','unspecified'),('เดิน 16.00','เดิน','unspecified'),('ฉันกินข้าวตอนเช้าเป็นเมนูข้าวมันไก่','ข้าวมันไก่','morning')])
def test_short_names_preserve_dish_and_explicit_time(text,label,period):
    r=meal(text)
    assert r['text']==label and r['data']['name']==label
    assert r['journal']['period']==period and not r['journal']['context_text']
    assert inspect_record(Record.model_validate({k:v for k,v in r.items() if k not in ('id','version')}))['can_record']

def test_optional_profile_and_child_bmi_no_adult_assumptions():
    assert Profile().age is None and Profile().allergies is None
    child=personal_context([profile(age=12,height_cm=150,weight_kg=50)])
    assert child['bmi'] is None and child['daily_calorie_target'] is None and 'child' in child['flags']
    adult=personal_context([profile(age=40,height_cm=170,weight_kg=70)])
    assert adult['bmi']==24.2 and adult['daily_calorie_target'] is None
    assert personal_context([profile(age=30,pregnant=True,height_cm=160,weight_kg=70)])['bmi'] is None

def test_measurement_event_time_wins_over_edit_time():
    p=profile(age=40,weight_kg=70,height_cm=170)
    def measurement(ident,value,date,edited):return {'id':ident,'kind':'measurement','created_at':edited,'data':{'name':'weight','unit':'kg','value':value,'occurred_at':date}}
    rows=[p,measurement('later_observation',72,'2026-10-12T08:00:00+07:00','2026-10-12'),measurement('old_edited',60,'2026-01-01T08:00:00+07:00','2026-10-13')]
    assert personal_context(rows)['profile']['weight_kg']==72
    assert personal_context(rows)['source_record_ids']['weight_kg']=='later_observation'

def test_food_reference_never_becomes_actual_intake_or_wrong_recipe():
    r=food_reference('ข้าวมันไก่');assert r['kcal']==[558,619] and r['actual_consumed_kcal'] is None
    assert food_reference('ข้าวมันไก่ทอด')['id']=='fried_chicken_rice'
    assert food_reference('ข้าวมันไก่ทอด')['kcal']==[557,557]
    assert food_reference('ข้าวขาหมู')['kcal']==[690,690]
    assert food_reference('ข้าวมันไก่พิเศษเพิ่มหนัง')['status']=='unknown'

def test_allergies_hard_filtered_before_and_after_ai_selection():
    rows=[profile(age=40,allergies=['ไข่','ปลา','ถั่วเหลือง'])]
    seen=[]
    def bad_model(messages):seen.append(messages);return {'output':'{"menu_ids":["tofu_veg_rice"],"kcal":1}'}
    result=recommend_meals('แนะนำเมนูมื้อเย็น',rows,bad_model,now=NOW)
    assert seen and result['engine']=='validated_catalog_fallback'
    assert all(not set(m['ingredients'])&{'ไข่','ปลา','ถั่วเหลือง'} for m in result['menus'])
    assert all(m['kcal'] is None and m['allergen_status']=='requires_ingredient_check' for m in result['menus'])
    other=recommend_meals('แนะนำเมนูมื้อเย็น',[profile(age=40,allergies=['ไก่','หมู'])],now=NOW)
    assert {m['id'] for m in result['menus']}!={m['id'] for m in other['menus']}

def test_unknown_allergy_and_concrete_food_restrictions_need_details():
    assert recommend_meals('แนะนำเมนู',[profile(age=40,allergies=['สารไม่ระบุ'])],now=NOW)['menus']==[]
    for data in ({'age':70,'conditions':['โรคไต']},{'age':30,'conditions':['กลืนลำบาก']}):
        r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(**data)],now=NOW)
        assert r['status']=='needs_care_context' and not r['menus']
        assert 'ตั้งครรภ์' not in r['answer'] and 'อายุเด็ก' not in r['answer']
        assert r['care_context'] and 'ครับ?' in r['answer']
    assert not recommend_meals('ฉันเป็นโรคไต แนะนำเมนู',[],now=NOW)['menus']

@pytest.mark.parametrize('data,code', [({'age':12},'child'),({'age':30,'pregnant':True},'pregnancy'),({'age':30,'complex_care':True},'complex_care')])
def test_general_meal_question_is_answered_for_age_pregnancy_or_unspecified_care(data,code):
    calls=[]
    r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(**data)],lambda messages:calls.append(messages) or {'output':'{"menu_ids":["chicken_veg_rice"]}'},now=NOW)
    assert calls and r['status']=='meal_ideas' and r['menus']
    assert r['menus'][0]['name'] in r['answer']
    assert code in {c['code'] for c in r['care_context']}
    assert all(m['kcal'] is None for m in r['menus']) and r['context']['daily_calorie_target'] is None
    if code=='child':assert r['context']['bmi'] is None and 'ผู้ปกครอง' in r['answer']
    if code in ('child','pregnancy'):assert all(m['id'] not in ('fish_veg_rice','chicken_salad_rice') for m in r['menus'])
    if code=='complex_care':assert 'อาหารที่ทีมรักษาสั่ง' in r['answer'] and 'โรคไต' not in r['answer']

@pytest.mark.parametrize('condition',['ไตรกลีเซอไรด์สูง','ไม่มีโรคไต','ไม่ได้เป็นโรคไต','ไม่มีประวัติโรคไต','เบื่ออาหาร'])
def test_unrelated_or_negated_conditions_do_not_trigger_kidney_or_texture_gate(condition):
    r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(age=40,conditions=[condition])],now=NOW)
    assert r['menus'] and r['status']=='meal_ideas'
    assert 'kidney_care' not in r['context']['flags'] and 'special_nutrition' not in r['context']['flags']

@pytest.mark.parametrize('condition',['โรคไตเรื้อรัง','ไตวาย','ฟอกไต','CKD','kidney disease'])
def test_actual_kidney_reports_still_require_specific_food_constraints(condition):
    r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(age=40,conditions=[condition])],now=NOW)
    assert r['status']=='needs_care_context' and not r['menus']
    assert 'เกี่ยวกับไต' in r['answer'] and 'จำกัดสารอาหาร' in r['answer']


def test_allergy_in_question_is_respected_without_profile_write():
    rows=[profile(age=40,allergies=[])]
    result=recommend_meals('แนะนำเมนูมื้อเย็น ฉันแพ้ไข่และปลา',rows,now=NOW)
    assert result['question_constraints']=={'allergies':['ไข่','ปลา'],'stored':False}
    assert all(not set(m['ingredients'])&{'ไข่','ปลา'} for m in result['menus'])
    assert rows[0]['data']['allergies']==[]

def test_today_only_meals_no_total_or_shame_and_ai_id_selection():
    rows=[profile(age=40,allergies=[]),meal('ตอนเช้ากินข้าวมันไก่'),meal('ตอนเที่ยงกินข้าวขาหมู'),meal('เมื่อวานกินข้าวผัดไข่')]
    result=recommend_meals('แนะนำเมนูมื้อเย็น',rows,lambda _: {'output':'{"menu_ids":["fish_veg_rice"]}'},NOW)
    assert result['engine']=='local_ai_validated_selection'
    assert len(result['meal_references'])==2 and 'ข้าวผัดไข่' not in result['answer']
    assert 'เพิ่มความหลากหลาย' in result['answer'] and 'ไม่ดีต่อสุขภาพทั้งคู่' not in result['answer']
    assert result['context']['daily_calorie_target'] is None

def test_agent_only_proposes_short_records_and_time_windows():
    result=agent_request('บันทึกตอนเช้ากินข้าวมันไก่ ตอนบ่ายเดิน',[],NOW)
    assert result['mode']=='proposal_only'
    records=result['actions'][0]['records'];assert len(records)==2
    assert records[0]['text']=='ข้าวมันไก่' and records[1]['journal']['clock'] is None
    plan=agent_request('จัดตารางพรุ่งนี้เดิน 30 นาทีตอนเย็น',[],NOW)
    routine=plan['actions'][0]['records'][0]
    assert routine['data']['dates']==['2026-10-13'] and 'ข้อเสนอ' in plan['answer']
    assert inspect_record(Record.model_validate(routine))['can_record']
    assert not agent_request('จัดตารางเดิน',[],NOW)['actions']
    assert all(a['type']=='navigate' for a in agent_request('จัดตารางยา',[],NOW)['actions'])
    assert agent_request('บันทึกกินข้าว และ เขียนโค้ด python',[],NOW) is None
    assert not wants_menu('แนะนำเมนูและราคาหุ้นวันนี้')

def test_general_schedule_works_without_forced_adult_type2_profile():
    routine=agent_request('จัดตารางพรุ่งนี้เดิน 30 นาทีตอนเย็น',[],NOW)['actions'][0]['records'][0]|{'id':'software'}
    result=build_plan({},[routine],[],'2026-10-13',0,general_time_only=True)
    assert result['status']=='pass' and result['general_time_only'] and result['clinical_status']=='not_reviewed'

def test_api_short_persistence_and_atomic_first_consent(client):
    narrative='ตอนเช้ากินข้าวมันไก่ 1 จาน'
    r=client.post('/api/journal/prepare',json={'text':narrative,'captured_at':NOW.isoformat(),'use_model':False}).json()
    assert r['items'][0]['record']['text']=='ข้าวมันไก่'
    records=[x['record'] for x in r['items']]
    p=client.post('/api/records/batch-preview',json={'records':records,'compact':True}).json()
    assert p['requires_consent'] and client.get('/api/records').json()['items']==[]
    assert confirm(client,p,'no-consent').status_code==422
    p=client.post('/api/records/batch-preview',json={'records':[{'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'},*records],'compact':True}).json()
    assert not p['requires_consent'] and confirm(client,p,'explicit-consent').status_code==200
    exported=client.get('/api/export').text
    assert narrative not in exported and 'ข้าวมันไก่' in exported
    assert confirm(client,p,'explicit-consent').status_code==200

def test_agent_drafts_never_write_and_menu_context_owner_scoped(client,monkeypatch):
    from app import main
    from services.store import Store
    monkeypatch.setattr(main,'generate_chat',lambda *a,**k:{'output':'{"menu_ids":["chicken_veg_rice"]}'})
    before=client.get('/api/export').json()
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':'บันทึกเดิน 16.00'}]}).json()
    assert result['actions'][0]['records'][0]['text']=='เดิน'
    r=client.post('/api/chat',json={'messages':[{'role':'user','content':'แนะนำเมนูมื้อเย็น'}]}).json()
    assert r['context']['profile']['age'] is None and r['meal_references']==[]
    assert client.get('/api/export').json()==before

def test_decimal_food_quantity_does_not_become_time_or_remain_in_name():
    r=meal('กินข้าว 16.00 กรัม')
    assert r['data']['name']=='ข้าว' and r['data']['quantity']==16
    assert r['journal']['clock']=='12:00:00' and r['journal']['clock_source']=='capture_time' and r['journal']['period']=='unspecified'

def test_question_preferences_and_combined_request_are_respected():
    r=recommend_meals('ขอเมนูไม่กินหมู',[profile(age=40,allergies=[])],now=NOW)
    assert all('หมู' not in m['ingredients'] for m in r['menus'])
    draft=agent_request('บันทึกตอนเช้ากินข้าวมันไก่ และแนะนำเมนูมื้อเย็น',[],NOW)
    assert draft['actions'][0]['records'][0]['text']=='ข้าวมันไก่'

def test_general_ideas_still_cannot_bypass_allergy_filters_with_care_checkbox():
    r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(age=16,complex_care=True,allergies=['ไข่','ถั่วเหลือง','ไก่'])],now=NOW)
    assert r['menus'] and all(not set(m['ingredients'])&{'ไข่','ถั่วเหลือง','ไก่'} for m in r['menus'])

def test_api_reported_dinner_question_returns_menu_without_changing_profile(client,monkeypatch):
    from app import main
    owner=main.store.session_get(client.cookies.get('routine_session'))['owner']
    main.store.confirm_record(owner,{'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'},'consent')
    main.store.confirm_record(owner,{'kind':'profile','data':{'age':35,'complex_care':True,'allergies':[]},'source':'SOFTWARE TEST ONLY'},'profile')
    before=client.get('/api/export').json()
    monkeypatch.setattr(main,'generate_chat',lambda *a,**k:{'output':'{"menu_ids":["chicken_veg_rice"]}'})
    r=client.post('/api/chat',json={'messages':[{'role':'user','content':'ตอนเย็นกินอะไรดี'}]})
    assert r.status_code==200 and r.json()['menus']
    assert r.json()['status']=='meal_ideas' and 'มีอาหารที่ทีมรักษาสั่ง' in r.json()['answer']
    assert any('โปรไฟล์เลือกว่าต้องวางแผนการดูแลเฉพาะ' in text for text in r.json()['details'])
    assert client.get('/api/export').json()==before

@pytest.mark.parametrize('text,names,periods',[
 ('วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง',['ข้าวขาหมู','ต้มยำกุ้ง'],['morning','noon']),
 ('กินข้าวเช้าเป็นข้าวมันไก่ตอนเที่ยงกินต้มยำกุ้ง',['ข้าวมันไก่','ต้มยำกุ้ง'],['morning','noon']),
 ('มื้อเช้าเป็นข้าวผัดไข่ มื้อเย็นเป็นเย็นตาโฟ',['ข้าวผัดไข่','เย็นตาโฟ'],['morning','evening']),
 ('กินข้าวเช้า ข้าวมันไก่',['ข้าวมันไก่'],['morning']),
 ('กินข้าวกลางวันเป็นข้าวขาหมู',['ข้าวขาหมู'],['noon']),
 ('กินข้าวผัดไข่ ดื่มชาเย็น',['ข้าวผัดไข่','ชาเย็น'],['unspecified','unspecified']),
])
def test_meal_grammar_extracts_source_names_and_never_guesses_exact_clock(text,names,periods):
    result=compact_journal(prepare_journal(text,NOW.isoformat()))
    assert not result['unparsed']
    assert [i['record']['text'] for i in result['items']]==names
    assert [i['record']['journal']['period'] for i in result['items']]==periods
    assert all(i['record']['journal']['clock'] is None if period!='unspecified' else i['record']['journal']['clock']=='12:00:00' for i,period in zip(result['items'],periods))
    assert all(name in text for name in names)

def test_reported_typo_draft_and_confirmation_preserve_only_short_fields(client):
    text='วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง'
    draft=client.post('/api/chat',json={'messages':[{'role':'user','content':text}]}).json()
    assert draft['status']=='agent_proposal' and 'ข้อมูลแยกช่อง' not in draft['answer']
    records=draft['actions'][0]['records']
    assert [r['text'] for r in records]==['ข้าวขาหมู','ต้มยำกุ้ง']
    assert client.get('/api/records').json()['items']==[]
    consent={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'}
    preview=client.post('/api/records/batch-preview',json={'records':[consent,*records],'compact':True}).json()
    assert confirm(client,preview,'typo-foods').status_code==200
    saved=client.get('/api/records').json()['items']
    meals=[r for r in saved if r['kind']=='meal']
    assert [r['data']['name'] for r in meals]==['ข้าวขาหมู','ต้มยำกุ้ง']
    assert all(r['journal']['clock'] is None for r in meals)
    assert text not in client.get('/api/export').text

def test_meal_answer_keeps_only_relevant_warnings_visible():
    rows=[profile(age=40,weight_kg=70,height_cm=170,allergies=[],reported_type2=True,medications=['SOFTWARE UNRELATED MEDICINE'])]
    r=recommend_meals('ตอนเย็นกินอะไรดี',rows,now=NOW)
    assert 'BMI' not in r['answer'] and 'อินซูลิน' not in r['answer'] and 'รายการแพ้' not in r['answer']
    assert any('BMI' in text for text in r['details'])
    assert 'ไม่ข้ามหรือเลื่อนมื้อ' not in r['answer']
    for medicine in ['อินซูลิน','sulfonylureas','meglitinides']:
        r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(age=40,allergies=[],medications=[medicine])],now=NOW)
        assert 'ไม่ข้ามหรือเลื่อนมื้อ' in r['answer']
    r=recommend_meals('ตอนเย็นกินอะไรดี',[profile(age=40,allergies=['ไข่'])],now=NOW)
    assert 'ไข่' in r['answer'] and 'เช็กเครื่องปรุงและการปนเปื้อน' in r['answer']
    assert all('ไข่' not in m['ingredients'] for m in r['menus'])

@pytest.mark.parametrize('question',['ดาวอังคารอยู่ที่ไหน','ดอกไม้คืออะไร','แล้วดอกไม้คืออะไร'])
def test_api_offtopic_never_uses_model_or_search(client,monkeypatch,question):
    from app import main
    def forbidden(*args,**kwargs):raise AssertionError('off-topic reached model/search')
    monkeypatch.setattr(main,'generate_chat',forbidden)
    monkeypatch.setattr(main.health_search,'search',forbidden)
    before=client.get('/api/export').json()
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':'เป็นเบาหวานควรกินอะไร'},{'role':'user','content':question}]}).json()
    assert result['status']=='out_of_scope' and result['citations']==[]
    assert client.get('/api/export').json()==before
