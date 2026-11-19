"""SOFTWARE TEST FIXTURES ONLY; temporary database, never user/demo/training records."""
import uuid
import pytest
from fastapi.testclient import TestClient
from services.store import Store
from app import main

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'store',Store(tmp_path/'fixture.sqlite'))
    # Pending drafts now live in the (fresh, per-test) store, not in memory.
    with TestClient(main.app) as c:
        token=c.get('/api/session').json()['csrf'];c.headers['x-csrf-token']=token
        yield c

def test_preview_no_write_confirmation_and_owner(client):
    r={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'}
    preview=client.post('/api/records/preview',json=r).json()
    assert client.get('/api/records').json()['items']==[]
    body={'draft_id':preview['draft_id'],'idempotency_key':str(uuid.uuid4()),'confirmed':False}
    assert client.post('/api/confirm',json=body).status_code==422
    body['confirmed']=True
    assert client.post('/api/confirm',json=body).status_code==200
    assert len(client.get('/api/records').json()['items'])==1
    with TestClient(main.app) as other:
        other.headers['x-csrf-token']=other.get('/api/session').json()['csrf']
        assert other.post('/api/confirm',json=body).status_code==404
        assert other.get('/api/export').json()['records']==[]

def test_csrf_and_cross_origin(client):
    assert client.post('/api/delete',json={'confirmation':'ลบข้อมูลของฉัน'},headers={'x-csrf-token':'bad'}).status_code==403
    assert client.get('/api/export',headers={'Origin':'https://untrusted.invalid'}).status_code==403

def test_ambiguous_preview_cannot_confirm(client):
    r={'kind':'measurement','data':{'name':'glucose','value':100},'source':'SOFTWARE TEST ONLY'}
    p=client.post('/api/records/preview',json=r).json();assert p['can_confirm'] is False
    assert client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':'test','confirmed':True}).status_code==422

def test_ui_and_no_invented_profile(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.post('/api/plans/preview',json={'start_date':'2026-10-12'}).status_code==422
    assert client.get('/api/readiness').json()['production'] is False

def test_extraction_failure_is_not_success_and_never_writes(client,monkeypatch):
    import json
    from types import SimpleNamespace
    output={'record':{'kind':'wellbeing','data':{'note':None,'occurred_at':None},'source':'SOFTWARE TEST ONLY','origin':'model_proposal'},'metrics':{'extraction_status':'invalid_model_output'}}
    monkeypatch.setattr(main.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(output)))
    r=client.post('/api/extract',json={'kind':'wellbeing','text':'SOFTWARE TEST ONLY'})
    assert r.status_code==200
    assert r.json()['model_status']=='invalid_model_output'
    assert client.get('/api/records').json()['items']==[]

def test_bulk_journal_preview_confirmation_and_later_time_edit(client):
    consent={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'}
    p=client.post('/api/records/preview',json=consent).json()
    assert client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':'consent','confirmed':True}).status_code==200
    result=client.post('/api/journal/prepare',json={'text':'ตอนเช้ากินข้าว 1 จาน\nตอนบ่ายเดิน\nรู้สึกเหนื่อย','captured_at':'2026-10-12T09:00:00+07:00','use_model':False}).json()
    assert len(result['items'])==3
    assert len(client.get('/api/records').json()['items'])==1
    p=client.post('/api/records/batch-preview',json={'records':[x['record'] for x in result['items']]}).json()
    assert p['can_confirm'] and any(c['status']=='unknown' for c in p['checks'])
    body={'draft_id':p['draft_id'],'idempotency_key':'bulk','confirmed':True}
    assert client.post('/api/confirm',json=body).json()['count']==3
    assert client.post('/api/confirm',json=body).json()['count']==3
    summary=client.get('/api/summary').json();assert summary['activity_sleep']==[] and summary['incomplete_records']==3
    activity=next(r for r in client.get('/api/records').json()['items'] if r['kind']=='activity')
    record={k:v for k,v in activity.items() if k not in ('id','version','created_at','status')}
    record['previous_id']=activity['id'];record['journal']['clock']='16:00';record['data']|={'start':'2026-10-12T16:00:00+07:00','end':'2026-10-12T16:30:00+07:00'}
    p=client.post('/api/records/batch-preview',json={'records':[record]}).json();assert p['can_confirm']
    assert client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':'edit','confirmed':True}).status_code==200
    assert client.get('/api/summary').json()['activity_sleep'][0]['minutes']==30
    assert len(client.get('/api/records?history=true').json()['items'])==5

def test_chat_reads_only_owner_records_and_never_writes(client):
    from services.journal import prepare_journal
    owner=main.store.session_get(client.cookies.get('routine_session'))['owner']
    consent={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'}
    for who in (owner,'different-owner'):main.store.confirm_record(who,consent,'consent')
    a=prepare_journal('เดิน 16.00','2026-10-12T09:00:00+07:00')['items'][0]['record']
    b=prepare_journal('เดิน 17.00','2026-10-12T09:00:00+07:00')['items'][0]['record']
    own=main.store.confirm_record(owner,a,'own');other=main.store.confirm_record('different-owner',b,'other')
    before=main.store.export(owner)
    body={'messages':[{'role':'user','content':'สรุปกิจกรรมของฉัน'}]}
    r=client.post('/api/chat',json=body);assert r.status_code==200
    assert [x['record_id'] for x in r.json()['record_sources']]==[own['id']]
    assert other['id'] not in r.text and before==main.store.export(owner)
    assert client.post('/api/chat',json=body,headers={'x-csrf-token':'bad'}).status_code==403
    assert client.post('/api/chat',json={'messages':[{'role':'assistant','content':'invented'}]}).status_code==422

def test_chat_calls_local_model_for_general_food_question_without_writing(client,monkeypatch):
    calls=[]
    monkeypatch.setattr(main,'generate_chat',lambda m,lock:calls.append(m) or {'output':'SOFTWARE TEST ONLY','metrics':{}})
    before=client.get('/api/export').json()
    r=client.post('/api/chat',json={'messages':[{'role':'user','content':'ฉันเป็นเบาหวานฉันจะกินอะไร'}]})
    assert r.status_code==200 and r.json()['status']=='answered_by_model'
    assert calls and r.json()['citations']
    assert client.get('/api/export').json()==before


def test_draft_survives_a_new_process_like_serverless(client,tmp_path,monkeypatch):
    """Preview and confirm may run on different instances: the draft is in the store."""
    consent={'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}}
    preview=client.post('/api/records/preview',json=consent).json()
    monkeypatch.setattr(main,'store',Store(main.store.path))  # new instance, same database
    r=client.post('/api/confirm',json={'draft_id':preview['draft_id'],'idempotency_key':'k1','confirmed':True})
    assert r.status_code==200,r.text

def test_cloud_mode_blocks_browser_sessions_and_demo(monkeypatch):
    monkeypatch.setattr(main,'CLOUD',True)
    with TestClient(main.app) as c:
        assert c.get('/').status_code==404
        assert c.get('/api/session').status_code==404
        assert c.get('/api/records').status_code==401
