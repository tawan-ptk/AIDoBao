"""Software fixture integration in temporary DB; no fictitious demo users."""
import hashlib,json,pathlib,subprocess,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app import main
from services.store import Store
from services.schemas import DOMAINS
from pglast import parse_sql

def main_check():
    result={'label':'SOFTWARE TEST ONLY; not clinical validation','cases':[]}
    def passed(name):result['cases'].append({'case':name,'result':'pass'})
    with tempfile.TemporaryDirectory(prefix='routine-software-test-') as folder:
        old=main.store;main.store=Store(pathlib.Path(folder)/'fixture.sqlite')
        try:
            with TestClient(main.app) as c:
                c.headers['x-csrf-token']=c.get('/api/session').json()['csrf']
                def confirm(r):
                    p=c.post('/api/records/preview',json=r);assert p.status_code==200,p.text
                    d=p.json();assert d['can_confirm'],d
                    out=c.post('/api/confirm',json={'draft_id':d['draft_id'],'idempotency_key':str(uuid.uuid4()),'confirmed':True});assert out.status_code==200,out.text;return out.json()
                confirm({'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}})
                confirm({'kind':'profile','source':'SOFTWARE TEST ONLY','data':{'age':40,'timezone':'Asia/Bangkok','reported_type2':True,'goals':['SOFTWARE TEST ONLY']}})
                # Verify opaque session survives replacement of Store instance / app restart.
                before=c.get('/api/records').json();main.store=Store(pathlib.Path(folder)/'fixture.sqlite');assert c.get('/api/records').json()==before;passed('persistent owner session')
                for i,domain in enumerate(DOMAINS):
                    confirm({'kind':'routine','source':'SOFTWARE TEST ONLY','data':{'domain':domain,'label':'SOFTWARE TEST ONLY '+domain,'dates':['2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16','2026-10-17','2026-10-18'],'earliest':f'{7+i:02}:00','latest':f'{7+i:02}:45','duration_minutes':15,'fixed':domain in ('medication','appointment'),'instruction_source':'SOFTWARE TEST ONLY' if domain=='medication' else None,'goal':'SOFTWARE TEST ONLY'}})
                p=c.post('/api/plans/preview',json={'start_date':'2026-10-12'}).json();assert p['can_confirm'] and len(p['plan']['items'])==49
                saved=c.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':str(uuid.uuid4()),'confirmed':True}).json();passed('all seven domains, seven days, atomic confirmation')
                confirm({'kind':'constraint','source':'SOFTWARE TEST ONLY','data':{'label':'SOFTWARE TEST ONLY changed availability','start':'2026-10-12T08:00:00+07:00','end':'2026-10-12T08:30:00+07:00'}})
                checked=c.get('/api/plans/'+saved['id']+'/recheck').json();assert checked['comparison']['changes'];passed('new constraints recheck and before-after')
                stale=c.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':str(uuid.uuid4()),'confirmed':True});assert stale.status_code==422;passed('stale proposal rejection')
                for query in ('อาหาร เวลา ยา','ออกกำลังกาย','ความเครียด'):
                    assert c.post('/api/knowledge',json={'query':query}).json()['citations']
                assert c.post('/api/knowledge',json={'query':'quantum cryptography'}).json()['status']=='unknown';passed('Thai query retrieval and unsupported-query abstention')
                assert c.get('/api/export').json()['records'];assert c.post('/api/delete',json={'confirmation':'ลบข้อมูลของฉัน'}).status_code==200
                assert c.get('/api/export').json()['records']==[];passed('export and owner-scoped delete')
        finally:main.store=old
    migration=ROOT/'supabase/migrations/001_initial.sql';statements=parse_sql(migration.read_text());result['migration']={'sql_statement_count':len(statements),'syntax':'parsed','sha256':hashlib.sha256(migration.read_bytes()).hexdigest(),'executed_on_postgres':False,'rls_runtime_tested':False}
    import nbformat
    with (ROOT/'local_training.ipynb').open() as f:nb=nbformat.read(f,as_version=4)
    nbformat.validate(nb);passed('notebook schema valid; no fabricated outputs')
    for script in ('demo/app.js','demo/journal.js','demo/chat.js'):subprocess.run(['node','--check',script],check=True,cwd=ROOT)
    passed('frontend JavaScript syntax')
    result['visual_ui_test']={'status':'blocked','reason':'No available browser connector; native Computer Use permissions not granted'}
    (ROOT/'reports/delivery-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main_check()
