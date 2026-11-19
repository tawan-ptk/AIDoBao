"""Software fixtures only: arithmetic, routing, missing coverage and owner isolation."""
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from services.food_reference import FOODS,food_reference
from services.food_portions import find_portion
from services.journal import prepare_journal,compact_journal
from services.nutrition import estimate_meal,daily_energy
from services.calorie_chat import calorie_request,food_query
from tests.test_api import client
from app import main

NOW=datetime.fromisoformat('2026-10-12T12:00:00+07:00')

def meal(text,ident='fixture',stamp=None):
    r=compact_journal(prepare_journal(text,stamp or NOW.isoformat()))['items'][0]['record']
    return r|{'id':ident,'version':1}

@pytest.mark.parametrize('text,label,q,unit,kcal',[
 ('กินข้าวมันไก่ครึ่งจาน','ข้าวมันไก่',.5,'จาน',[279,309.5]),
 ('กินไข่ต้ม 2 ฟอง','ไข่ต้ม',2,'ฟอง',[160,160]),
 ('กินข้าวขาหมู ๒ จาน','ข้าวขาหมู',2,'จาน',[1380,1380]),
 ('กินข้าวสวย 1/2 ทัพพี','ข้าวสวย',.5,'ทัพพี',[40,40]),
 ('ดื่มนมขาดมันเนย 120 ml','นมขาดมันเนย',120,'มล.',[45,45]),
 ('กินเงาะสองผล','เงาะ',2,'ผล',[30,30]),
 ('กินมะละกอ 6 ชิ้นคำ','มะละกอ',6,'ชิ้นคำ',[60,60]),
])
def test_literal_amount_and_name_survive_compaction(text,label,q,unit,kcal):
    r=meal(text);e=estimate_meal(r)
    assert r['text']==r['data']['name']==label
    assert r['data']['quantity']==q and r['data']['unit']==unit
    assert e['kcal']==kcal and not e['assumed_portion']
    assert e['actual_consumed_kcal'] is None

def test_unknowns_are_not_zero_or_guessed_grams():
    assert estimate_meal(meal('กินอาหารลึกลับ'))['kcal'] is None
    assert estimate_meal(meal('กินข้าวมันไก่ 300 กรัม'))['status']=='unknown_unit'
    assert estimate_meal(meal('กินข้าวสวย 1 จาน'))['kcal'] is None
    r=meal('กินข้าวมันไก่');r['data']['quantity']=2
    assert estimate_meal(r)['status']=='missing_unit'
    r['data']={'name':'ข้าวมันไก่','unit':'จาน'}
    assert estimate_meal(r)['status']=='missing_quantity'
    r['data']={'name':'ข้าวมันไก่','food_state':'raw'}
    assert estimate_meal(r)['status']=='food_state_mismatch'

@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True,'2'])
def test_invalid_amount_never_gets_a_total(value):
    assert estimate_meal({'kind':'meal','data':{'name':'ข้าวมันไก่','quantity':value,'unit':'จาน'}})['kcal'] is None

def test_default_portion_is_visible_and_range_uses_recipe_basis():
    e=estimate_meal(meal('กินข้าวมันไก่'))
    assert e['assumed_portion'] and e['quantity']==1 and e['unit']=='จาน' and e['assumption']
    assert estimate_meal(meal('กินต้มยำกุ้ง'))['kcal']==[270,370]
    assert estimate_meal(meal('กินข้าวมันไก่ทอด'))['reference']['id']!='chicken_rice'
    assert food_reference('ข้าวมันไก่เพิ่มไข่')['kcal'] is None

def test_daily_uses_all_meals_not_first_twelve_and_does_not_hide_missing():
    records=[meal('กินไข่ต้ม 1 ฟอง',str(i)) for i in range(15)]
    records += [meal('กินอาหารไม่รู้จัก','unknown'),meal('กินไข่ต้ม 1 ฟอง','old','2026-10-11T23:00:00+07:00'),
                {'kind':'meal','id':'undated','data':{'name':'ไข่ต้ม'}},
                {'kind':'activity','id':'walk','data':{}}]
    summary=daily_energy(records,NOW.date())
    assert summary['kcal']==[1200,1200] and summary['status']=='partial'
    assert summary['meal_count']==16 and summary['unknown_count']==1 and summary['undated_meal_count']==1
    assert summary['daily_target_kcal'] is None

def test_bangkok_date_uses_event_not_save_time():
    records=[{'kind':'meal','id':'utc','data':{'name':'ไข่ต้ม','quantity':1,'unit':'ฟอง','occurred_at':'2026-10-11T18:00:00+00:00'},'created_at':'2026-10-13'}]
    assert daily_energy(records,'2026-10-12')['kcal']==[80,80]
    assert daily_energy(records,'2026-10-11')['kcal'] is None

@pytest.mark.parametrize('query,name', [('ข้าวมันไก่กี่แคล','ข้าวมันไก่'),('ไข่ต้ม 2 ฟองกี่แคล','ไข่ต้ม'),('ช่วยคำนวณแคลอรี่ของข้าวขาหมู 1 จาน','ข้าวขาหมู')])
def test_questions_keep_complete_food_names(query,name):
    assert food_query(query)==name
    assert calorie_request(query,[],NOW)['status']=='calorie_estimate'

def test_daily_questions_default_today_but_named_question_does_not_read_records():
    rows=[meal('กินข้าวมันไก่ 1 จาน')]
    assert calorie_request('คำนวณแคลลอรี่ทั้งวัน',rows,NOW)['energy_summary']['kcal']==[558,619]
    assert calorie_request('เมื่อวานรวมกี่แคล',rows,NOW)['energy_summary']['kcal'] is None
    assert calorie_request('วันนี้กินไข่ต้ม 2 ฟองกี่แคล',rows,NOW)['energy_estimate']['kcal']==[160,160]
    assert calorie_request('ฉันควรกินวันละกี่แคล',rows,NOW) is None
    assert calorie_request('บันทึกอาหารพร้อมแคลอรี',rows,NOW) is None

def test_catalog_has_sources_and_unique_aliases():
    names=[n.replace(' ','') for f in FOODS for n in [f['name'],*f['aliases']]]
    assert len(names)==len(set(names))
    assert all(f['url'].startswith('https://') and f['basis'] and len(f['kcal'])==2 for f in FOODS)

def test_api_preview_chat_edits_deletes_and_owner_totals(client,monkeypatch):
    monkeypatch.setattr(main,'generate_chat',lambda *a,**k:pytest.fail('Calorie arithmetic must not call a model'))
    r=meal('กินข้าวมันไก่ 1 จาน');r.pop('id');r.pop('version')
    consent={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE FIXTURE ONLY'}
    preview=client.post('/api/records/batch-preview',json={'records':[consent,r]}).json()
    assert preview['checks'][1]['calculated']['energy']['kcal']==[558,619]
    assert client.get('/api/records').json()['items']==[]
    def confirm(p,key):assert client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':key,'confirmed':True}).status_code==200
    confirm(preview,'initial')
    def ask():return client.post('/api/chat',json={'messages':[{'role':'user','content':'2026-10-12 รวมกี่แคล'}]}).json()
    assert ask()['energy_summary']['kcal']==[558,619]
    saved=next(r for r in client.get('/api/records').json()['items'] if r['kind']=='meal')
    assert client.get('/api/records').json()['meal_energy'][saved['id']]['kcal']==[558,619]
    edited={k:v for k,v in saved.items() if k not in ('id','version','status','created_at')}
    edited['previous_id']=saved['id'];edited['data']['quantity']=.5
    p=client.post('/api/records/batch-preview',json={'records':[edited]}).json();confirm(p,'edit')
    assert ask()['energy_summary']['kcal']==[279,309.5]
    with TestClient(main.app) as other:
        other.headers['x-csrf-token']=other.get('/api/session').json()['csrf']
        assert other.post('/api/chat',json={'messages':[{'role':'user','content':'2026-10-12 รวมกี่แคล'}]}).json()['energy_summary']['meal_count']==0
    current=next(r for r in client.get('/api/records').json()['items'] if r['kind']=='meal')
    p=client.post('/api/records/delete-preview',json={'record_ids':[current['id']]}).json();confirm(p,'delete')
    assert ask()['energy_summary']['kcal'] is None

def test_energy_endpoint_read_only_and_input_validation(client):
    r=client.post('/api/food-energy',json={'name':'ไข่ต้ม','quantity':2,'unit':'ฟอง'})
    assert r.status_code==200 and r.json()['kcal']==[160,160]
    assert client.get('/api/records').json()['items']==[]
    assert client.post('/api/food-energy',json={'name':'ไข่ต้ม','quantity':-1,'unit':'ฟอง'}).status_code==422
    assert client.post('/api/food-energy',json={'name':'ไข่ต้ม'},headers={'x-csrf-token':'bad'}).status_code==403
