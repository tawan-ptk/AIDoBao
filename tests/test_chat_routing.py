"""SOFTWARE TEST ONLY: automatic personal / health / off-topic policy."""
import pytest
from services.chat_routing import route_question
from services.chat import answer_chat
from services.rag import Retriever

@pytest.mark.parametrize('query,route',[
 ('เป็นเบาหวานจะอ้วนใช่ไหม','health'),('ฉันเป็นเบาหวานจะผอมไหม','health'),
 ('เป็นเบาหวานควรกินอะไร','health'),('ฉันหนักเท่าไร','my_data'),
 ('น้ำหนักฉันตอนนี้เท่าไร','my_data'),('ฉันอ้วนไหม','my_data'),
 ('น้ำหนักล่าสุดของฉัน','my_data'),('วันนี้กินอะไรไปบ้าง','my_data'),
 ('วันนี้ทำอะไรไปบ้าง','my_data'),('สรุปข้อมูลสุขภาพของฉัน','my_data'),
 ('ราคาหุ้นวันนี้','out_of_scope'),('เขียนโค้ดแอปเบาหวานให้หน่อย','out_of_scope'),
 ('แต่งเพลงเกี่ยวกับเบาหวาน','out_of_scope'),('บันทึกยอดขายวันนี้','out_of_scope'),
 ('ควรนอนกี่ชั่วโมง','health'),('สวัสดีครับ','welcome')])
def test_automatic_routing(query,route):
 assert route_question([{'role':'user','content':query}])['route']==route

def test_followups_use_context_but_new_offtopic_question_cannot_inherit_health():
 previous=[{'role':'user','content':'เป็นเบาหวานจะอ้วนใช่ไหม'}]
 assert route_question(previous+[{'role':'user','content':'แล้วถ้าผอมล่ะ'}])['route']=='health'
 assert route_question(previous+[{'role':'user','content':'แล้วราคาหุ้นวันนี้ล่ะ'}])['route']=='out_of_scope'

def test_scope_cannot_override_health_only_policy_or_force_record_lookup():
 for scope in ['auto','knowledge','my_data']:
  def forbidden(*args):raise AssertionError('off-topic request must not search or generate')
  result=answer_chat([{'role':'user','content':'เขียนโค้ดเบาหวาน'}],scope,[],Retriever(),generator=forbidden,online_search=forbidden)
  assert result['status']=='out_of_scope'
  result=answer_chat([{'role':'user','content':'เป็นเบาหวานจะอ้วนใช่ไหม'}],scope,[],Retriever(),generator=lambda m:{'output':'SOFTWARE TEST ONLY'})
  assert result['status']=='answered_by_model' and result['route']=='health'

def test_online_fallback_receives_only_allowlisted_topic_not_question_or_records():
 calls=[]
 result=answer_chat([{'role':'user','content':'ฉันชื่อ SOFTWARE PRIVATE ปวดหัวทำอย่างไร'}], 'auto',[],Retriever(),online_search=lambda topic:calls.append(topic) or {'status':'unavailable','citations':[]})
 assert calls==['headache'] and result['status']=='unknown'
 assert 'เชื่อมต่อ' in result['answer'] and 'เลือก “ข้อมูลของฉัน”' not in result['answer']

def test_unknown_word_can_use_local_classifier_without_external_raw_query():
 calls=[]
 r=route_question([{'role':'user','content':'เวียนศีรษะทำอย่างไร'}],classifier=lambda q:calls.append(q) or {'route':'health','topic':'headache'})
 assert calls and r['route']=='health'
 r=route_question([{'role':'user','content':'SOFTWARE UNKNOWN'}],classifier=lambda q:{'route':'health','topic':'https://untrusted.test'})
 assert r['route']=='out_of_scope'

@pytest.mark.parametrize('question',['คุณคือใคร','ดอกไม้คืออะไร','แล้วดอกไม้คืออะไร','แล้วคุณเป็นใครล่ะ','บันทึกยอดขายวันนี้','ดาวอังคารอยู่ที่ไหน'])
def test_unrelated_questions_cannot_be_promoted_by_classifier_or_history(question):
 def forbidden(*args):raise AssertionError('Unrelated text must not reach AI or search')
 history=[{'role':'user','content':'เป็นเบาหวานควรกินอะไร'},{'role':'assistant','content':'SOFTWARE TEST ONLY'},{'role':'user','content':question}]
 result=answer_chat(history,'auto',[],Retriever(),generator=forbidden,classifier=forbidden,online_search=forbidden)
 assert result['status']=='out_of_scope' and not result['citations']
 assert route_question(history,classifier=lambda q:{'route':'health','topic':'diabetes'})['route']=='out_of_scope'

def test_true_health_context_and_short_followup_remain_supported():
 assert route_question([{'role':'user','content':'แพ้เกสรดอกไม้ทำยังไง'}])['topic']=='allergy'
 history=[{'role':'user','content':'วันนี้กินอะไรไปบ้าง'},{'role':'user','content':'แล้วเมื่อวานล่ะ'}]
 assert route_question(history)['route']=='my_data'

def test_health_model_instructions_do_not_import_unasked_remission_topic():
 from services.chat import model_messages
 retriever=Retriever()
 question='เป็นเบาหวานจะอ้วนใช่ไหม'
 evidence=retriever.answer(question)['citations']
 # Use the same curated evidence selection as the answer engine.
 evidence=[c for c in evidence if c.get('content_type')=='editorial_summary']
 system=model_messages([{'role':'user','content':question}],evidence)[0]['content']
 assert 'คำถามเรื่องหายจากเบาหวาน' not in system
 result=answer_chat([{'role':'user','content':question}],'auto',[],retriever,
                    generator=lambda _: {'output':'น้ำหนักลดเพราะเข้าสู่ภาวะสงบ (remission)'})
 assert result['status']=='answered_from_sources'
 assert result['answer_mode']=='editorial_summary_fallback'
 assert 'ภาวะสงบ' not in result['answer'] and 'remission' not in result['answer']
 assert 'ไม่ได้หมายความว่าจะต้องอ้วนทุกคน' in result['answer']
 question='เบาหวานหายได้ไหม'
 evidence=retriever.answer(question)['citations']
 assert 'คำถามเรื่องหายจากเบาหวาน' in model_messages([{'role':'user','content':question}],evidence)[0]['content']
