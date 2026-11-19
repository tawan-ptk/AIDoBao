"""SOFTWARE TEST ONLY: Thai input contracts, never training or clinical evidence."""
import copy,json
import pytest
from services.journal import prepare_journal
from services.schemas import Record,inspect_record
from services.store import Store
from services.calculators import summarize,comparable_measurements

STAMP='2026-10-12T09:00:00+07:00'
def prepare(text,stamp=STAMP):return prepare_journal(text,stamp)
def one(text,stamp=STAMP):return prepare(text,stamp)['items'][0]['record']

def test_walk_uses_capture_date_and_keeps_duration_unknown():
    r=one('เดิน 16.00')
    assert r['kind']=='activity' and r['data']['start']=='2026-10-12T16:00:00+07:00'
    check=inspect_record(Record.model_validate(r))
    assert check['status']=='unknown' and check['can_record'] and 'end' in check['missing']
    assert summarize([r|{'id':'test'}])==[]

def test_seven_domains_from_one_message():
    text='ตอนเช้ากินข้าว 1 จาน\nตอนบ่ายเดิน\nงีบตอนบ่าย\nกินยา 1 เม็ด\nนัดหมอ 16.00\nชั่งน้ำหนัก 65 กิโลกรัม\nรู้สึกเหนื่อย'
    r=prepare(text)
    assert [x['record']['kind'] for x in r['items']]==['meal','activity','sleep','medication','appointment','measurement','wellbeing']
    assert not r['unparsed']
    assert all(inspect_record(Record.model_validate(x['record']))['can_record'] for x in r['items'])
    assert r['items'][3]['record']['data']['state']=='unknown'

def test_period_has_no_fabricated_exact_time_and_can_be_refined(tmp_path):
    r=one('ตอนบ่ายเดิน');assert r['journal']['period']=='afternoon' and r['journal']['clock'] is None
    assert not r['data'].get('start')
    s=Store(tmp_path/'software.sqlite');s.confirm_record('a',{'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}},'consent')
    first=s.confirm_batch('a',[r],'first')['items'][0]
    edit=copy.deepcopy(r);edit['previous_id']=first['id'];edit['journal']['clock']='16:00'
    edit['data']|={'start':'2026-10-12T16:00:00+07:00','end':'2026-10-12T16:30:00+07:00'}
    s.confirm_batch('a',[edit],'edit')
    assert len(s.records('a',current=False))==3
    assert summarize(s.records('a'))[0]['minutes']==30

def test_bangkok_date_uses_capture_instant_even_if_confirmed_after_midnight():
    assert one('เดิน','2026-10-11T17:01:00+00:00')['journal']['date']=='2026-10-12'
    assert one('เดิน','2026-10-12T16:59:00+00:00')['journal']['date']=='2026-10-12'
    assert one('เดิน','2026-10-12T17:01:00+00:00')['journal']['date']=='2026-10-13'

def test_explicit_dates_headings_and_overnight_sleep():
    r=prepare('เมื่อวานตอนเช้า\nกินข้าว\nเดิน 16.00')
    assert len(r['items'])==2 and not r['unparsed']
    assert all(x['record']['journal']['date']=='2026-10-11' for x in r['items'])
    assert r['items'][1]['record']['data']['start']=='2026-10-11T16:00:00+07:00'
    assert one('12/10/2569 เดิน')['journal']['date']=='2026-10-12'
    r=one('นอน 23.00-07.00')
    assert r['data']['end']=='2026-10-13T07:00:00+07:00'

@pytest.mark.parametrize('text',['ไม่ได้เดิน','พรุ่งนี้จะเดิน','ถ้ามีเวลาจะเดิน','อยากกินยา','วันนี้ยังไม่กินข้าว'])
def test_negation_and_intentions_are_not_actual_events(text):
    r=prepare(text);assert not r['items'] and r['unparsed']

def test_decimal_measurement_is_not_a_clock_and_unknown_unit_is_not_inferred():
    assert one('น้ำหนัก 16.00 กก')['journal']['clock']=='09:00'
    assert one('น้ำหนัก 16.00 กก')['journal']['clock_source']=='capture_time'
    r=one('น้ำตาล 120');assert not r['data'].get('unit') and not r['data'].get('value')
    assert comparable_measurements([r|{'id':'test'}])==[]

def test_source_coverage_and_model_cannot_add_or_rewrite_items():
    r=prepare('เดิน 16.00 แล้วรู้สึกเหนื่อย');assert len(r['items'])==2
    assert all(x['record']['text'] in 'เดิน 16.00 แล้วรู้สึกเหนื่อย' for x in r['items'])
    r=prepare_journal('ข้อความที่ไม่ชัด',STAMP,json.dumps({'items':[{'text':'ข้อความที่แต่งเพิ่ม','kind':'medication'}]}))
    assert not r['items'] and r['unparsed']

def test_batch_rolls_back_all_records_and_retry_is_idempotent(tmp_path):
    s=Store(tmp_path/'software.sqlite');s.confirm_record('a',{'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}},'consent')
    a,b=one('ตอนเช้ากินข้าว'),one('ตอนบ่ายเดิน')
    with pytest.raises(ValueError):s.confirm_batch('a',[a,a],'rollback')
    assert len(s.records('a'))==1 and s.revision('a')==1
    result=s.confirm_batch('a',[a,b],'save');assert result==s.confirm_batch('a',[a,b],'save')
    assert len(s.records('a'))==3 and s.records('b')==[]
