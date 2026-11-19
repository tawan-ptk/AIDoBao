"""Software fixtures: meal grouping, arithmetic, confirmation and revisions."""
import copy
import pytest
from services.journal import prepare_journal,compact_journal
from services.nutrition import estimate_meal,daily_energy
from services.schemas import Record,inspect_record
from services.calorie_chat import calorie_request
from services.chat_management import edited_record
from tests.test_api import client

STAMP='2026-10-12T12:00:00+07:00'
def capture(text):return compact_journal(prepare_journal(text,STAMP))

@pytest.mark.parametrize('text,total',[
    ('ข้าวกับไข่พะโล้',432.9),
    ('กินข้าวกับไข่พะโล้',432.9),
    ('ตอนเที่ยงกินข้าว 2 ทัพพี กับไข่พะโล้ 1 ส่วน',512.9),
    ('กินข้าวกับต้มพะโล้',438),
    ('กินข้าว 2 ทัพพีกับต้มพะโล้ครึ่งถ้วย',339),
    ('กินข้าวสวย 1 ถ้วย กับไข่ต้ม 2 ฟอง',400),
])
def test_one_meal_with_separate_component_amounts(text,total):
    result=capture(text)
    assert len(result['items'])==1 and result['unparsed']==[]
    r=result['items'][0]['record'];energy=estimate_meal(r)
    assert len(r['data']['components'])==2
    assert 'quantity' not in r['data'] and 'unit' not in r['data']
    assert energy['kcal']==[total,total]
    assert len(energy['references'])==2 and all(ref['url'].startswith('https://') for ref in energy['references'])
    assert r['journal']['date']=='2026-10-12'
    assert r['journal']['clock'] is None if r['journal']['period']!='unspecified' else r['journal']['clock']=='12:00:00'
    assert r['evidence']=={} and r['text']==r['data']['name']
    summary=daily_energy([r],'2026-10-12')
    assert summary['meal_count']==1 and summary['kcal']==[total,total]

def test_literal_bare_combo_in_chat_is_only_a_reviewable_draft(client):
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':'ข้าวกับไข่พะโล้'}]}).json()
    assert result['status']=='agent_proposal'
    assert len(result['actions'][0]['records'])==1
    assert estimate_meal(result['actions'][0]['records'][0])['kcal']==[432.9,432.9]
    assert client.get('/api/records').json()['items']==[]

def test_defaults_are_visible_and_independent_not_claimed_actual_intake():
    e=estimate_meal(capture('กินข้าวกับไข่พะโล้')['items'][0]['record'])
    assert e['assumed_portion'] and 'ทัพพีเล็ก' in e['assumption'] and 'ส่วน' in e['assumption']
    assert 'เด็กวัยเรียน' in e['components'][1]['reference']['basis']
    assert all(p['quantity'] is None for p in capture('กินข้าวกับไข่พะโล้')['items'][0]['record']['data']['components'])
    assert e['actual_consumed_kcal'] is None

def test_distinct_meal_periods_stay_distinct_and_whole_dish_not_double_counted():
    result=capture('เช้ากินข้าวกับไข่ต้ม ตอนเที่ยงกินข้าวกับต้มพะโล้')
    assert len(result['items'])==2
    assert [i['record']['journal']['period'] for i in result['items']]==['morning','noon']
    for name in ['ข้าวมันไก่','ข้าวสวยกับไก่ต้ม','ข้าวกะเพราไก่ไข่ดาว']:
        r=capture('กิน'+name)['items'][0]['record']
        assert 'components' not in r['data']
        assert estimate_meal(r)['kcal'] is not None

def test_unknown_side_and_unknown_rice_unit_show_partial_not_full_total():
    for text,known in [('กินข้าวกับอาหารลึกลับ',[80,80]),('กินข้าว 1 จานกับไข่ต้ม 2 ฟอง',[160,160])]:
        r=capture(text)['items'][0]['record'];e=estimate_meal(r)
        assert e['status']=='partial' and e['kcal']==known and e['unknown_component_count']==1
        s=daily_energy([r],'2026-10-12')
        assert s['status']=='partial' and s['unknown_count']==1 and s['kcal']==known
        answer=calorie_request('2026-10-12 รวมกี่แคล',[r|{'id':'fixture'}])
        assert 'ประเมินได้ไม่ครบ' in answer['answer'] and len(answer['meal_references'])==1

@pytest.mark.parametrize('bad',[True,'2',0,-1,float('inf'),float('nan')])
def test_invalid_component_never_becomes_a_default_or_a_number(bad):
    r=capture('กินข้าวกับไข่พะโล้')['items'][0]['record']
    r['data']['components'][0]['quantity']=bad
    assert inspect_record(Record.model_validate(r))['status']=='fail'
    assert estimate_meal(r)['kcal'] is None

def test_ambiguous_whole_meal_amount_and_rename_do_not_reuse_component_energy():
    r=capture('กินข้าวกับไข่พะโล้')['items'][0]['record']|{'id':'fixture'}
    bad=copy.deepcopy(r);bad['data'].update(quantity=1,unit='จาน')
    assert estimate_meal(bad)['status']=='ambiguous_quantity'
    assert inspect_record(Record.model_validate({k:v for k,v in bad.items() if k!='id'}))['status']=='fail'
    with pytest.raises(ValueError,match='แยกกัน'):edited_record(r,'ครึ่งจาน',quantity_only=True)
    renamed=edited_record(r,'ไข่ต้ม')
    assert 'components' not in renamed['data'] and estimate_meal(renamed)['kcal']==[80,80]

def test_api_one_meal_confirm_edit_delete_and_daily_sum(client):
    r=capture('ตอนเที่ยงกินข้าว 2 ทัพพี กับไข่พะโล้ 1 ส่วน')['items'][0]['record']
    consent={'kind':'consent','data':{'local_storage':True},'source':'SOFTWARE FIXTURE ONLY'}
    p=client.post('/api/records/batch-preview',json={'records':[consent,r]}).json()
    assert p['can_confirm'] and client.get('/api/records').json()['items']==[]
    def confirm(p,key):assert client.post('/api/confirm',json={'draft_id':p['draft_id'],'idempotency_key':key,'confirmed':True}).status_code==200
    def meals():return [r for r in client.get('/api/records').json()['items'] if r['kind']=='meal']
    def total():return client.post('/api/chat',json={'messages':[{'role':'user','content':'2026-10-12 รวมกี่แคล'}]}).json()['energy_summary']
    confirm(p,'combined-save')
    assert len(meals())==1 and total()['kcal']==[512.9,512.9]
    old=meals()[0];edit={k:v for k,v in old.items() if k not in ('id','version','status','created_at')}
    edit['previous_id']=old['id'];edit['data']['components'][0]['quantity']=1
    p=client.post('/api/records/batch-preview',json={'records':[edit]}).json()
    assert total()['kcal']==[512.9,512.9]
    confirm(p,'combined-edit')
    assert len(meals())==1 and total()['kcal']==[432.9,432.9] and total()['meal_count']==1
    p=client.post('/api/records/delete-preview',json={'record_ids':[meals()[0]['id']]}).json()
    confirm(p,'combined-delete')
    assert meals()==[] and total()['kcal'] is None

def test_live_energy_endpoint_accepts_components_and_does_not_save(client):
    data=capture('กินข้าว 2 ทัพพีกับไข่ต้ม 2 ฟอง')['items'][0]['record']['data']
    result=client.post('/api/food-energy',json={k:v for k,v in data.items() if k!='occurred_at'})
    assert result.status_code==200 and result.json()['kcal']==[320,320]
    data['components'][0]['quantity']=1
    assert client.post('/api/food-energy',json={k:v for k,v in data.items() if k!='occurred_at'}).json()['kcal']==[240,240]
    data['components'][0]['quantity']=True
    assert client.post('/api/food-energy',json=data).status_code==422
    assert client.get('/api/records').json()['items']==[]

def test_basic_thai_dishes_keep_rice_included_and_scale_only_verified_weights():
    from services.food_reference import THAI_DISH_FACTS,food_reference
    for ident,name,grams,kcal,page,includes_rice,aliases in THAI_DISH_FACTS:
        r=capture('กิน'+name)['items'][0]['record'];e=estimate_meal(r)
        assert 'components' not in r['data'] and e['kcal']==[kcal,kcal]
        assert e['reference']['sample_weight_g']==grams
        assert e['reference']['includes_rice']==includes_rice
        assert '2551' in e['reference']['basis']
        e=estimate_meal({'kind':'meal','data':{'name':name,'quantity':grams/2,'unit':'กรัม'}})
        assert e['kcal']==[kcal/2,kcal/2]
    assert food_reference('ข้าวกะเพราไก่')['id']=='basil_chicken_rice'
    assert food_reference('ผัดกะเพราไก่')['kcal'] is None # Rice dish cannot supply the side's energy.

def test_unspecified_plain_milk_is_a_labelled_range_not_lowfat_substitution():
    for name in ['นม','นมจืด']:
        e=estimate_meal({'kind':'meal','data':{'name':name,'quantity':240,'unit':'มล.'}})
        assert e['kcal']==[90,150] and 'ยังไม่ทราบไขมัน' in e['note']
        assert e['reference']['additional_sources']
    assert estimate_meal({'kind':'meal','data':{'name':'นมพร่องมันเนย'}})['kcal']==[120,120]
    assert estimate_meal({'kind':'meal','data':{'name':'นมข้นหวาน'}})['kcal'] is None
