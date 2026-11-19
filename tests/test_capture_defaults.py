"""Capture defaults and backend identity contracts; synthetic local fixtures only."""
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from services.journal import prepare_journal,compact_journal
from services.schemas import Record,inspect_record
from services.agent import agent_request
from services.store import Store
from app import main
from tests.test_api import client

STAMP='2026-10-12T17:02:59Z'  # next calendar day in Bangkok

@pytest.mark.parametrize('text,field',[('กินข้าว','occurred_at'),('เดิน','start'),('นอน','start'),('นัดหมอ','start'),('กินยา 1 เม็ด','occurred_at'),('น้ำหนัก 16.00 กก','occurred_at'),('รู้สึกเหนื่อย','occurred_at')])
def test_missing_time_uses_capture_minute_without_inventing_duration(text,field):
    record=compact_journal(prepare_journal(text,STAMP))['items'][0]['record']
    assert record['journal']['date']=='2026-10-13'
    assert record['journal']['clock']=='00:02:00'
    assert record['journal']['clock_source']=='capture_time'
    assert record['data'][field]=='2026-10-13T00:02:00+07:00'
    assert not record['data'].get('end')
    assert field not in record['evidence']
    assert inspect_record(Record.model_validate(record))['can_record']

@pytest.mark.parametrize('text,period,clock,source',[
 ('ตอนเช้ากินข้าว','morning',None,'unspecified'),
 ('ตอนบ่าย\nเดิน','afternoon',None,'unspecified'),
 ('เดิน 16.00','unspecified','16:00','explicit'),
 ('เดิน 25.00','unspecified',None,'unspecified'),
 ('เมื่อวานตอนเย็น\nกินข้าว','evening',None,'unspecified'),
])
def test_explicit_period_clock_or_invalid_time_never_gets_now(text,period,clock,source):
    r=prepare_journal(text,STAMP)['items'][0]['record']
    assert r['journal']['period']==period and r['journal']['clock']==clock
    assert r['journal']['clock_source']==source

def test_many_items_share_capture_and_only_period_items_stay_without_clock():
    items=prepare_journal('กินข้าว\nเดิน\nตอนเย็นกินไข่ต้ม',STAMP)['items']
    assert [r['record']['journal']['clock'] for r in items]==['00:02','00:02',None]
    assert prepare_journal('เมื่อวานกินข้าว',STAMP)['items'][0]['record']['data']['occurred_at']=='2026-10-12T00:02:00+07:00'

def test_chat_api_preserves_original_capture_through_preview_and_confirmation(client):
    r=client.post('/api/chat',json={'messages':[{'role':'user','content':'กินข้าว'}],'captured_at':STAMP}).json()
    record=r['actions'][0]['records'][0]
    assert record['journal']['clock_source']=='capture_time' and 'เวลาที่พิมพ์' in r['answer']
    assert r['actions'][1]['captured_at']=='2026-10-13T00:02:59+07:00'
    assert client.get('/api/records').json()['items']==[]
    consent={'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}}
    p=client.post('/api/records/batch-preview',json={'records':[consent,record],'compact':True}).json()
    assert p['can_confirm']
    body={'draft_id':p['draft_id'],'confirmed':True,'idempotency_key':'capture-test'}
    assert client.post('/api/confirm',json=body).status_code==200
    assert client.post('/api/confirm',json=body).status_code==200
    rows=client.get('/api/records').json()['items']
    meal=next(r for r in rows if r['kind']=='meal')
    assert meal['data']['occurred_at']=='2026-10-13T00:02:00+07:00'
    assert meal['journal']['captured_at']==record['journal']['captured_at']

@pytest.mark.parametrize('route,body',[('/api/chat',{'messages':[{'role':'user','content':'กินข้าว'}]}),('/api/journal/prepare',{'text':'กินข้าว','use_model':False})])
def test_api_rejects_capture_without_timezone(client,route,body):
    assert client.post(route,json={**body,'captured_at':'2026-10-13T12:00:00'}).status_code==422

def headers(user='site:account-a',key='k'*48):return {'Authorization':'Bearer '+key,'X-Ruamwan-User':user}

def test_server_api_durable_identity_isolated_confirmations_and_key_rotation(client,monkeypatch):
    monkeypatch.setenv('RUAMWAN_API_KEY','k'*48)
    with TestClient(main.app) as a,TestClient(main.app) as b:
        a.headers.update(headers());b.headers.update(headers('site:account-b'))
        draft=a.post('/api/records/preview',json={'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}}).json()
        body={'draft_id':draft['draft_id'],'confirmed':True,'idempotency_key':'same-key'}
        assert b.post('/api/confirm',json=body).status_code==404
        assert a.post('/api/confirm',json=body).status_code==200
        assert b.get('/api/records').json()['items']==[]
        assert len(a.get('/api/records').json()['items'])==1
        owner=main.store.integration_owner('site:account-a')
        monkeypatch.setattr(main,'store',Store(main.store.path))
        monkeypatch.setenv('RUAMWAN_API_KEY','n'*48)
        assert a.get('/api/records').status_code==401
        a.headers.update(headers(key='n'*48))
        assert len(a.get('/api/records').json()['items'])==1
        assert main.store.integration_owner('site:account-a')==owner
        with main.store.connect() as db:
            assert db.execute('SELECT subject_hash FROM integration_accounts').fetchone()[0]!='site:account-a'

def test_bad_backend_credentials_never_fall_back_to_local_session(client,monkeypatch):
    monkeypatch.delenv('RUAMWAN_API_KEY',raising=False)
    assert client.get('/api/records',headers=headers()).status_code==503
    monkeypatch.setenv('RUAMWAN_API_KEY','k'*48)
    assert client.get('/api/records',headers=headers(key='wrong')).status_code==401
    assert client.get('/api/records',headers={'X-Ruamwan-User':'site:account-a'}).status_code==401
    assert client.get('/api/records',headers={'Authorization':'Bearer '+'k'*48}).status_code==422
    assert client.get('/api/records',headers=headers('a b')).status_code==422
    assert client.get('/api/records').status_code==200  # local cookie+CSRF unaffected
    schema=client.get('/openapi.json').json()
    assert schema['info']['version']=='0.11.0'
    assert schema['paths']['/api/chat']['post']['security'][0]=={'ServerKey':[],'AuthenticatedUser':[]}
