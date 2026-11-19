"""SOFTWARE TEST ONLY: temporary owner data, no real patient records."""
import json
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from app import main
from tests.test_api import client
from services.agent import agent_request
from services.chat_routing import route_question
from services.journal import prepare_journal,compact_journal

NOW=datetime.fromisoformat('2026-10-12T12:00:00+07:00')
def owner(client):return main.store.session_get(client.cookies.get('routine_session'))['owner']
def seed(client,*texts):
    who=owner(client)
    main.store.confirm_record(who,{'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE TEST ONLY'},'consent')
    for i,text in enumerate(texts):
        r=compact_journal(prepare_journal(text,NOW.isoformat()))['items'][0]['record']
        main.store.confirm_record(who,r,'seed-'+str(i))
    return main.store.all_current(who)
def chat(client,text):return client.post('/api/chat',json={'messages':[{'role':'user','content':text}]}).json()
def confirm(client,preview,key='change'):
    return client.post('/api/confirm',json={'draft_id':preview['draft_id'],'idempotency_key':key,'confirmed':True})

@pytest.mark.parametrize('question',['แนะนำหน่อยว่าฉันจะถามคุณว่าอะไรได้บ้าง','ถามอะไรได้บ้าง','คุณช่วยอะไรได้บ้าง','ใช้งานยังไง','แนะนำวิธีใช้งานให้หน่อย','ขอตัวอย่างคำถาม','ลบข้อมูลยังไง','แก้ไขข้อมูลผ่านแชตอย่างไร'])
def test_usage_questions_are_supported_without_search_or_model(client,monkeypatch,question):
    def forbidden(*a,**k):raise AssertionError('usage help must not search or generate')
    monkeypatch.setattr(main,'generate_chat',forbidden);monkeypatch.setattr(main.health_search,'search',forbidden)
    r=chat(client,question)
    assert r['status']=='usage_help' and r['suggestions'] and 'ยืนยัน' in r['answer']
    assert len(r['answer'])<500 and not r['citations']
    assert route_question([{'role':'user','content':question}])['route']=='usage_help'
    assert client.get('/api/records').json()['items']==[]

def test_help_does_not_enable_unrelated_or_medical_usage_topics():
    assert route_question([{'role':'user','content':'วิธีใช้อินซูลิน'}])['route']=='health'
    assert agent_request('สอนใช้งาน python',[]) is None
    assert route_question([{'role':'user','content':'ดอกไม้คืออะไร'}])['route']=='out_of_scope'

def test_latest_delete_uses_last_saved_entry_even_when_backdated(client):
    rows=seed(client,'วันนี้กินข้าวมันไก่','เมื่อวานกินโจ๊ก')
    result=agent_request('ลบบันทึกล่าสุด',rows,NOW)
    latest=next(r for r in rows if r.get('text')=='โจ๊ก')
    assert result['actions'][0]['record_ids']==[latest['id']]
    assert not agent_request('ช่วยลบข้อมูลให้หน่อย',rows,NOW)['actions']

def test_chat_edit_is_a_reviewed_new_version_preserving_original_time(client):
    rows=seed(client,'ตอนเช้ากินข้าวขาหมู 1 จาน')
    old=next(r for r in rows if r['kind']=='meal')
    before=client.get('/api/export').json()
    r=chat(client,'แก้ข้าวขาหมูเป็นโจ๊ก');a=r['actions'][0]
    assert a['inline'] and a['before'][0]['id']==old['id']
    new=a['records'][0]
    assert new['previous_id']==old['id'] and new['data']['name']==new['text']=='โจ๊ก'
    assert new['journal']==old['journal'] and new['data']['quantity']==1
    assert client.get('/api/export').json()==before
    p=client.post('/api/records/batch-preview',json={'records':a['records']}).json()
    assert confirm(client,p).status_code==200
    current=next(r for r in main.store.all_current(owner(client)) if r['kind']=='meal')
    assert current['version']==2 and current['data']['name']=='โจ๊ก'
    assert len([r for r in main.store.records(owner(client),current=False) if r['kind']=='meal'])==2

def test_ambiguous_delete_and_edit_require_selection_and_bulk_logs_keep_profile(client):
    rows=seed(client,'ตอนเช้ากินข้าวขาหมู','ตอนเย็นกินข้าวขาหมู')
    main.store.confirm_record(owner(client),{'kind':'profile','data':{'age':40},'source':'SOFTWARE TEST ONLY'},'profile')
    r=chat(client,'ลบข้าวขาหมู');assert len(r['actions'])==2
    assert all(len(a['record_ids'])==1 for a in r['actions'])
    assert len(chat(client,'แก้ข้าวขาหมูเป็นโจ๊ก')['actions'])==2
    r=chat(client,'ลบบันทึกทั้งหมด');a=r['actions'][0]
    assert a['scope']=='records' and len(a['record_ids'])==2
    p=client.post('/api/records/delete-preview',json={'scope':a['scope'],'record_ids':a['record_ids']}).json()
    assert p['history_count']==2 and confirm(client,p).status_code==200
    assert {r['kind'] for r in main.store.all_current(owner(client))}=={'profile','consent'}

def test_profile_and_exact_time_can_be_edited_without_replacing_other_fields(client):
    rows=seed(client,'เดิน 16.00')
    who=owner(client)
    main.store.confirm_record(who,{'kind':'profile','data':{'age':40,'height_cm':170,'allergies':['ไข่']},'source':'SOFTWARE TEST ONLY'},'profile')
    r=chat(client,'แก้น้ำหนักเป็น 68 กก.')['actions'][0]['records'][0]
    assert r['data']['weight_kg']==68 and r['data']['allergies']==['ไข่'] and r['data']['height_cm']==170
    a=chat(client,'แก้เวลาบันทึกเดินล่าสุดเป็น 17.00')['actions'][0]
    assert a['records'][0]['journal']['clock']=='17:00'
    assert a['records'][0]['data']['start'].endswith('T17:00:00+07:00')
    assert not chat(client,'แก้น้ำหนักเป็น 999 กก.')['actions']
    assert not chat(client,'แก้เวลาเดินเป็น 27.00')['actions']
    assert not chat(client,'ลบข้อมูลที่ไม่รู้จัก')['actions']

def test_targeted_delete_removes_history_derived_plan_and_pending_drafts_only_for_owner(client):
    rows=seed(client,'ตอนเช้ากินข้าวขาหมู','ตอนเที่ยงกินต้มยำกุ้ง')
    who=owner(client);original=next(r for r in rows if r.get('text')=='ข้าวขาหมู')
    edit=chat(client,'แก้ข้าวขาหมูเป็นโจ๊ก')['actions'][0]['records']
    p=client.post('/api/records/batch-preview',json={'records':edit}).json();assert confirm(client,p,'edit').status_code==200
    current=next(r for r in main.store.all_current(who) if r.get('text')=='โจ๊ก')
    main.store.confirm_plan(who,{'status':'pass','input_revision':main.store.revision(who),'items':[{'routine_id':original['id'],'label':'SOFTWARE DELETED LABEL'}]},'plan')
    main.store.confirm_plan(who,{'status':'pass','input_revision':main.store.revision(who),'items':[]},'unrelated-plan')
    pending=client.post('/api/records/batch-preview',json={'records':chat(client,'แก้โจ๊กเป็นข้าวผัดไข่')['actions'][0]['records']}).json()
    a=chat(client,'ลบโจ๊ก')['actions'][0]
    p=client.post('/api/records/delete-preview',json={'record_ids':a['record_ids']}).json()
    assert p['history_count']==2 and p['plan_count']==1
    assert len(main.store.all_current(who))==3
    with TestClient(main.app) as other:
        other.headers['x-csrf-token']=other.get('/api/session').json()['csrf']
        seed(other,'ตอนเช้ากินข้าวขาหมู')
        assert other.post('/api/records/delete-preview',json={'record_ids':[current['id']]}).status_code==422
        assert confirm(other,p).status_code==404
        assert confirm(client,p,'delete').status_code==200
        assert len(main.store.all_current(owner(other)))==2
    assert confirm(client,p,'delete').status_code==200
    assert confirm(client,p,'another-key').status_code==422
    assert confirm(client,pending,'old-edit').status_code==404
    exported=client.get('/api/export').text
    assert 'ข้าวขาหมู' not in exported and 'โจ๊ก' not in exported and 'SOFTWARE DELETED LABEL' not in exported
    assert 'ต้มยำกุ้ง' in exported and len(main.store.plans(who))==1
    with main.store.connect() as c:
        assert 'SOFTWARE DELETED LABEL' not in json.dumps([dict(x) for x in c.execute('SELECT * FROM retries WHERE owner=?',(who,))])

def test_stale_delete_requires_new_preview_and_never_removes_new_data(client):
    rows=seed(client,'เดิน 16.00');who=owner(client)
    r=next(r for r in rows if r['kind']=='activity')
    p=client.post('/api/records/delete-preview',json={'record_ids':[r['id']]}).json()
    main.store.confirm_record(who,{'kind':'profile','data':{'age':50},'source':'SOFTWARE TEST ONLY'},'new-profile')
    assert confirm(client,p).status_code==422
    assert any(x['id']==r['id'] for x in main.store.all_current(who))
    p=client.post('/api/records/delete-preview',json={'scope':'all'}).json()
    main.store.confirm_plan(who,{'status':'pass','input_revision':main.store.revision(who),'items':[]},'new-plan')
    assert confirm(client,p,'all').status_code==422
    assert len(main.store.all_current(who))==3

def test_delete_all_requires_confirmation_and_csrf_and_clears_owner_records(client):
    seed(client,'ตอนเช้ากินข้าวขาหมู')
    a=chat(client,'ลบข้อมูลทั้งหมด')['actions'][0]
    assert a['scope']=='all'
    assert client.post('/api/records/delete-preview',json={'scope':'all'},headers={'x-csrf-token':'invalid'}).status_code==403
    p=client.post('/api/records/delete-preview',json={'scope':'all'}).json()
    body={'draft_id':p['draft_id'],'idempotency_key':'all','confirmed':False}
    assert client.post('/api/confirm',json=body).status_code==422
    assert len(main.store.all_current(owner(client)))==2
    assert confirm(client,p,'all').status_code==200
    assert client.get('/api/export').json()=={'records':[],'plans':[],'audit':[]}
    assert confirm(client,p,'all').status_code==200

@pytest.mark.parametrize('query',['อย่าลบบันทึก','ยังไม่ลบบันทึก','ถ้าลบข้อมูลทั้งหมดจะเป็นอย่างไร'])
def test_negation_and_hypotheticals_never_offer_destructive_actions(query):
    result=agent_request(query,[])
    assert result is None or not any(a['type']=='delete_records' for a in result.get('actions',[]))
