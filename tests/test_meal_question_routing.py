"""Software regressions: advice is read-only; food statements remain drafts."""
import pytest
from app import main
from tests.test_api import client
from services.agent import agent_request,wants_menu
from services.journal import prepare_journal,split_meal_span
from services.nutrition import estimate_meal

ADVICE=[
    'กินข้าวกับอะไรดี','ข้าวกับอะไรดี','กินข้าวกับอะไรดีครับ',
    'ทานข้าวกับอะไรดีคะ','กินข้าวสวยกับอะไรดี','กินข้าวคู่กับอะไรดี',
    'วันนี้กินข้าวกับอะไรดี','กินข้าวกับอะไรได้บ้าง','กินข้าวกับอะไร',
    'กินข้าวกับอะไรดี?','ควรกินข้าวกับอะไร','แนะนำกับข้าวหน่อย',
]

@pytest.mark.parametrize('query',ADVICE)
def test_advice_questions_use_menu_path_without_record_proposal(query,client,monkeypatch):
    calls=[]
    def choose(messages,*args,**kwargs):
        assert messages[0]['content'].startswith('Choose up to 3 meal IDs from eligible only.')
        calls.append(messages)
        return {'output':'{"menu_ids":["chicken_veg_rice"]}'}
    monkeypatch.setattr(main,'generate_chat',choose)
    assert wants_menu(query) and agent_request(query,[]) is None
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':query}]}).json()
    assert result['status']=='meal_ideas' and result['route']=='personalized_menu'
    assert result['mode']=='read_only' and result['menus'] and calls
    assert not any(a['type'] in ('records','journal') for a in result.get('actions',[]))
    assert 'แยกได้' not in result['answer'] and '80 kcal' not in result['answer']
    assert client.get('/api/records').json()['items']==[]

@pytest.mark.parametrize('query',ADVICE+[
    'กินข้าวกับไข่พะโล้ดีมั้ย','กินข้าวกับไข่พะโล้ได้ไหม',
    'อยากกินข้าวกับไข่พะโล้','จะกินข้าวกับไข่พะโล้',
])
def test_questions_and_intentions_cannot_become_food_components(query):
    assert split_meal_span(query)==[]
    result=prepare_journal(query,'2026-10-12T12:00:00+07:00')
    assert result['items']==[] and result['unparsed']
    assert estimate_meal({'kind':'meal','data':{'name':query}})['kcal'] is None

@pytest.mark.parametrize('query',['วันนี้กินอะไรไปบ้าง','วันนี้กินข้าวกับอะไรไปบ้าง','เมื่อวานกินอะไรบ้าง'])
def test_meal_recall_questions_do_not_select_a_new_menu(query,client,monkeypatch):
    def forbidden(*a,**kw):pytest.fail('Recall reads saved records, not menu AI')
    monkeypatch.setattr(main,'generate_chat',forbidden)
    assert not wants_menu(query) and agent_request(query,[]) is None
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':query}]}).json()
    assert result['route']=='my_data' and result['status']=='no_records'

@pytest.mark.parametrize('query',['กินข้าวกับไข่พะโล้','ข้าวกับไข่พะโล้','กินข้าวกับอาหารลึกลับ'])
def test_real_food_statements_keep_the_composite_draft(query):
    assert not wants_menu(query)
    result=agent_request(query,[])
    assert result['status']=='agent_proposal'
    records=result['actions'][0]['records']
    assert len(records)==1 and len(records[0]['data']['components'])==2

def test_journal_endpoint_does_not_offer_question_as_a_record(client,monkeypatch):
    def forbidden(*a,**kw):pytest.fail('A known question does not need category extraction')
    monkeypatch.setattr(main.subprocess,'run',forbidden)
    result=client.post('/api/journal/prepare',json={'text':'กินข้าวกับอะไรดี'}).json()
    assert result['items']==[] and result['unparsed']
    assert client.get('/api/records').json()['items']==[]

def test_new_food_advice_still_respects_offtopic_guard(client,monkeypatch):
    def forbidden(*a,**kw):pytest.fail('Off-topic text cannot reach menu AI')
    monkeypatch.setattr(main,'generate_chat',forbidden)
    query='กินข้าวกับอะไรดี แล้วเขียนโค้ดให้ด้วย'
    assert not wants_menu(query)
    result=client.post('/api/chat',json={'messages':[{'role':'user','content':query}]}).json()
    assert result['status']=='out_of_scope'
    assert client.get('/api/records').json()['items']==[]

def test_mixed_message_only_extracts_the_meal_that_happened():
    result=prepare_journal('เมื่อเช้ากินข้าวกับไข่ต้ม ตอนเย็นกินข้าวกับอะไรดี','2026-10-12T12:00:00+07:00')
    assert len(result['items'])==1 and result['items'][0]['record']['journal']['period']=='morning'
    assert len(result['items'][0]['record']['data']['components'])==2
    assert [part['text'] for part in result['unparsed']]==['ตอนเย็นกินข้าวกับอะไรดี']
