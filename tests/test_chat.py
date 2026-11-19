"""SOFTWARE TEST ONLY: owner-scoped read-only chat and exact source attribution."""
from datetime import datetime
from services.chat import answer_chat,domains
from services.rag import Retriever
from services.journal import prepare_journal

STAMP='2026-10-12T09:00:00+07:00'
def reply(text,rows=(),previous=None,scope='auto'):
    messages=([{'role':'user','content':previous},{'role':'assistant','content':'SOFTWARE TEST ONLY'}] if previous else [])+[{'role':'user','content':text}]
    return answer_chat(messages,scope,list(rows),Retriever(),datetime.fromisoformat(STAMP))
def row(text,ident='software'):
    return prepare_journal(text,STAMP)['items'][0]['record']|{'id':ident,'version':1,'created_at':STAMP}

def test_today_duration_does_not_make_missing_time_zero():
    r=reply('วันนี้เดินกี่นาที',[row('เดิน 16.00-16.30','full'),row('ตอนบ่ายเดิน','partial')])
    assert r['status']=='answered_from_records' and '30 นาที' in r['answer']
    assert 'อีก 1 รายการยังขาด' in r['answer'] and '0 นาที' not in r['answer'].replace('30 นาที','')
    assert {x['record_id'] for x in r['record_sources']}=={'full','partial'}

def test_followup_uses_prior_domain_but_queries_actual_records_again():
    rows=[row('เมื่อวานตอนเช้ากินข้าว','meal'),row('เมื่อวานเดิน','walk')]
    r=reply('แล้วเมื่อวานล่ะ',rows,previous='วันนี้กินอะไรไปบ้าง')
    assert len(r['record_sources'])==1 and r['record_sources'][0]['domain']=='meal'
    assert '2026-10-11' in r['answer']

def test_no_records_is_not_a_claim_that_user_did_nothing():
    r=reply('วันนี้ทำอะไรไปบ้าง')
    assert r['status']=='no_records' and r['record_sources']==[]
    assert 'ยังไม่พบบันทึก' in r['answer']

def test_medication_changes_are_outside_chat_scope():
    r=reply('ฉันควรเพิ่มยากี่เม็ด')
    assert r['status']=='outside_scope' and not r['citations']

def test_general_health_has_exact_text_citations_and_unknown_abstains():
    r=reply('อาหารกับเบาหวาน')
    assert r['status']=='answered_from_sources' and r['citations']
    for excerpt in r['excerpts']:
        source=next(c for c in r['citations'] if c['chunk_id']==excerpt['chunk_id'])
        assert excerpt['text'] in source['text']
    assert reply('quantum cryptography')['status']=='out_of_scope'
    assert 'medication' not in domains('อยากดูข้อมูลของฉัน')

def test_general_diabetes_questions_use_model_not_record_lookup():
    calls=[]
    def generate(messages):
        calls.append(messages)
        return {'output':'SOFTWARE TEST ONLY: generated answer','metrics':{'load_seconds':1}}
    for question in ['ฉันเป็นเบาหวานฉันจะกินอะไร','ฉันจะหายจากเบาหวานได้ยังไง','เบาหวานรักษาหายไหม']:
        r=answer_chat([{'role':'user','content':question}],'auto',[],Retriever(),generator=generate)
        assert r['status']=='answered_by_model' and r['citations'] and not r['record_sources']
        assert calls[-1][-1]['content']==question
        assert 'ไม่กำหนดหรือปรับขนาดยา' in calls[-1][0]['content']
    assert 'niddk-chat-remission-summary' in [c['chunk_id'] for c in r['citations']]

def test_model_not_used_for_record_totals_unknown_evidence_or_drug_adjustment():
    def forbidden(messages):raise AssertionError('model must not run')
    for question,status in [('วันนี้เดินกี่นาที','no_records'),('ฉันควรหยุดยาไหม','outside_scope'),('quantum cryptography','out_of_scope')]:
        r=answer_chat([{'role':'user','content':question}],'auto',[],Retriever(),generator=forbidden)
        assert r['status']==status

def test_followup_model_context_does_not_include_owner_records():
    calls=[]
    messages=[{'role':'user','content':'เป็นเบาหวานควรกินอะไร'},{'role':'assistant','content':'SOFTWARE ANSWER'},{'role':'user','content':'แล้วผลไม้ล่ะ'}]
    r=answer_chat(messages,'auto',[row('ตอนเช้ากินข้าว PRIVATE TEST RECORD')],Retriever(),generator=lambda m:calls.append(m) or {'output':'SOFTWARE ANSWER'})
    assert r['status']=='answered_by_model'
    assert 'PRIVATE TEST RECORD' not in str(calls)
    assert calls[0][-1]==messages[-1]
