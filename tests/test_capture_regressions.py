"""Software regressions, not patient or clinical validation data."""
import pytest
from services.journal import prepare_journal,compact_journal,split_meal_span
from services.nutrition import estimate_meal
from services.food_reference import FOODS,food_reference
from services.food_portions import find_portion
from services.calorie_chat import calorie_request
from services.care_plan import care_plan_request
from services.chat import answer_chat,online_answer
from services.rag import Retriever
from services.chat_management import management_request
from tests.test_api import client
from app import main

STAMP='2026-10-12T12:00:00+07:00'
def capture(text):return compact_journal(prepare_journal(text,STAMP))

@pytest.mark.parametrize('text,quantity', [('1 จานครึ่ง',1.5),('1 1/2 จาน',1.5),('1½ จาน',1.5),('½ จาน',.5),('๒ จานครึ่ง',2.5)])
def test_half_portions(text,quantity):
    r=capture('กินข้าวมันไก่'+text)['items'][0]['record']
    assert r['text']=='ข้าวมันไก่' and r['data']['quantity']==quantity
    assert estimate_meal(r)['kcal'][0]==558*quantity

@pytest.mark.parametrize('text',['กินข้าวมันไก่ไปประมาณ 1 จานแล้วครับ','กินข้าวมันไก่มาประมาณครึ่งจานค่ะ'])
def test_narrative_particles_are_not_dish_names(text):
    r=capture(text)['items'][0]['record']
    assert r['text']=='ข้าวมันไก่' and estimate_meal(r)['kcal'] is not None

@pytest.mark.parametrize('connector',['กับ',' และ ','และ',' + '])
def test_compound_meal_keeps_individual_amount_date_and_period(connector):
    text='เมื่อวานตอนเช้ากินข้าวมันไก่ครึ่งจาน'+connector+'ไข่ต้ม 2 ฟอง'
    result=capture(text);rows=[x['record'] for x in result['items']]
    assert [r['text'] for r in rows]==['ข้าวมันไก่ กับ ไข่ต้ม']
    assert [c['quantity'] for c in rows[0]['data']['components']]==[.5,2]
    assert estimate_meal(rows[0])['kcal']==[439,469.5]
    assert all(r['journal']['date']=='2026-10-11' and r['journal']['period']=='morning' for r in rows)
    assert result['unparsed']==[] and result['requires_confirmation']
    assert all(x['source_index']>=0 for x in result['items'])

def test_whole_dish_wins_and_ambiguous_modifiers_are_not_discarded():
    for name in ['ข้าวสวยกับไก่ต้ม','ข้าวมันไก่พิเศษเพิ่มหนัง','ข้าวมันไก่กับน้ำจิ้ม']:
        assert split_meal_span(name)==[]
    assert food_reference('ข้าวมันไก่ทอด')['id']=='fried_chicken_rice'
    assert food_reference('ข้าวมันไก่พิเศษเพิ่มหนัง')['kcal'] is None
    assert estimate_meal(capture('กินข้าวมันไก่ 1/0 จาน')['items'][0]['record'])['kcal'] is None

def test_reported_typo_and_second_meal_have_clean_names_and_energy():
    r=capture('วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง')
    assert [i['record']['text'] for i in r['items']]==['ข้าวขาหมู','ต้มยำกุ้ง']
    assert [i['record']['journal']['period'] for i in r['items']]==['morning','noon']
    assert all(i['check']['calculated']['energy']['kcal'] for i in r['items'])

def test_explicit_day_carries_across_several_narrated_meals():
    r=capture('เมื่อวานตอนเช้ากินไข่ต้ม ตอนเที่ยงกินข้าวมันไก่ ตอนเย็นกินต้มยำกุ้ง')
    assert len(r['items'])==3
    assert all(i['record']['journal']['date']=='2026-10-11' for i in r['items'])
    assert [i['record']['journal']['period'] for i in r['items']]==['morning','noon','evening']

@pytest.mark.parametrize('name,q,unit,expected',[
 ('ข้าวหมูแดงไข่ต้ม',1,'จาน',351.1),('สุกี้น้ำทะเล',1,'ชาม',235.4),
 ('ขนมจีนน้ำยา',1,'จาน',370),('ไข่ยัดไส้',1,'ส่วน',181.6),
 ('ฟักทองผัดไข่',1,'ส่วน',145.3),('มะม่วงสุก',1,'ผลเล็ก',120),
])
def test_additional_sources_have_scalable_verified_servings(name,q,unit,expected):
    e=estimate_meal({'kind':'meal','data':{'name':name,'quantity':q,'unit':unit}})
    assert e['kcal']==[expected,expected] and e['reference']['url'].startswith('https://')
    assert e['reference']['location'] and not e['assumed_portion']

def test_inline_total_uses_named_meal_instead_of_saved_daily_records():
    r=calorie_request('วันนี้ข้าวมันไก่ 1 จานกับไข่ต้ม 2 ฟองรวมกี่แคล',[])
    assert r['status']=='calorie_meal_summary' and r['total_kcal']==[718,779]
    assert r['record_sources']==[] and [e['quantity'] for e in r['energy_estimates']]==[1,2]

def test_care_plan_does_not_depend_on_model_or_search_or_create_records(client,monkeypatch):
    def forbidden(*a,**kw):pytest.fail('Starting plan must work without model/search availability')
    monkeypatch.setattr(main,'generate_chat',forbidden)
    monkeypatch.setattr(main.health_search,'search',forbidden)
    for query in ['ฉันอยากให้คุณช่วยฉันจัดแพลนดูแลสุขภาพเกี่ยวกับเบาหวาน','ช่วยวางแผนดูแลเบาหวาน','ขอแผนดูแลเบาหวาน']:
        result=client.post('/api/chat',json={'messages':[{'role':'user','content':query}]}).json()
        assert result['status']=='care_plan_guidance' and result['actions']==[]
        assert len(result['citations'])==2 and 'ครึ่งจาน' in result['answer']
        assert 'คัดข้อความ' not in result['answer']
    assert client.get('/api/records').json()['items']==[]
    assert client.post('/api/chat',json={'messages':[{'role':'user','content':'เขียนโค้ดแผนดูแลเบาหวาน'}]}).json()['status']=='out_of_scope'
    assert len(client.get('/api/food-catalog').json()['items'])==len(FOODS)

def test_care_plan_respects_confirmed_complex_context_and_dose_guard():
    for data in [{'age':12},{'pregnant':True},{'conditions':['โรคไตเรื้อรัง']}]:
        r=care_plan_request('จัดแผนดูแลเบาหวาน',[{'kind':'profile','id':'fixture','data':data}])
        assert 'ครึ่งจาน' not in r['answer'] and 'แผนที่ทีมรักษา' in r['answer']
    assert care_plan_request('จัดแผนดูแลเบาหวานปรับยากี่เม็ด',[]) is None

def test_model_failure_keeps_verifiable_source_text():
    citations=[{'text':'FIRST SOURCE SENTENCE. SECOND SOURCE SENTENCE.','publisher':'MedlinePlus','url':'https://medlineplus.gov/diabetes.html'}]
    def failed(*a):raise RuntimeError('software failure')
    result=online_answer([{'role':'user','content':'สุขภาพ'}],citations,failed)
    assert result['status']=='source_excerpt' and 'FIRST SOURCE SENTENCE.' in result['answer']
    r=answer_chat([{'role':'user','content':'เป็นเบาหวานควรกินอะไร'}],'auto',[],Retriever(),generator=failed)
    assert r['status']=='answered_from_sources' and r['citations'] and 'ครึ่งจาน' in r['answer']

def test_chat_quantity_change_is_only_a_reviewable_proposal():
    record=capture('กินข้าวมันไก่ 1 จาน')['items'][0]['record']|{'id':'fixture','version':1}
    r=management_request('แก้ปริมาณข้าวมันไก่เป็นครึ่งจาน',[record])
    proposed=r['actions'][0]['records'][0]
    assert proposed['previous_id']=='fixture' and proposed['data']['name']=='ข้าวมันไก่'
    assert proposed['data']['quantity']==.5 and record['data']['quantity']==1
    assert estimate_meal(proposed)['kcal']==[279,309.5]

@pytest.mark.parametrize('prefix',['เมื่อวานตอนเช้า','วันนี้ตอนเช้า','วันนี้ฉัน','ฉันเมื่อวานตอนเช้า'])
def test_natural_compound_statement_routes_to_draft_before_personal_lookup(prefix):
    from services.agent import agent_request
    r=agent_request(prefix+'กินข้าวมันไก่ครึ่งจานกับไข่ต้ม 2 ฟอง',[])
    assert r and r['status']=='agent_proposal'
    assert [x['text'] for x in r['actions'][0]['records']]==['ข้าวมันไก่ กับ ไข่ต้ม']
