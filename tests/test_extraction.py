"""SOFTWARE TEST ONLY: output contracts, not clinical accuracy."""
import json
import pytest
from scripts.inference import parse_extraction

def test_rejects_array_and_unsupported_evidence():
    with pytest.raises(ValueError):
        parse_extraction(json.dumps({'data':[{'note':'x'}],'evidence':{}}),'wellbeing','x')
    data,_=parse_extraction(json.dumps({'data':{'note':'x'},'evidence':{'note':'not in input'}}),'wellbeing','x')
    assert data['note'] is None

def test_partial_proposal_keeps_missing_unknown():
    data,evidence=parse_extraction(json.dumps({'data':{'note':'SOFTWARE TEST ONLY'},'evidence':{'note':'SOFTWARE TEST ONLY','occurred_at':None}}),'wellbeing','SOFTWARE TEST ONLY')
    assert data=={'note':'SOFTWARE TEST ONLY','occurred_at':None}
    assert evidence=={'note':'SOFTWARE TEST ONLY'}

def test_model_cannot_reuse_unrelated_span_for_a_fabricated_name_or_number():
    output={'data':{'name':'invented dish','quantity':500},'evidence':{'name':'SOFTWARE TEST ONLY','quantity':'2'}}
    data,evidence=parse_extraction(json.dumps(output),'meal','SOFTWARE TEST ONLY 2')
    assert data['name'] is None and data['quantity'] is None and not evidence

def test_model_cannot_attach_fabricated_calendar_date_to_clock_only_evidence():
    output={'data':{'name':'เดิน','start':'2026-10-12T16:00:00+07:00'},'evidence':{'name':'เดิน','start':'16.00'}}
    data,evidence=parse_extraction(json.dumps(output),'activity','เดิน 16.00')
    assert data['name']=='เดิน' and data['start'] is None
    assert evidence=={'name':'เดิน'}

def test_walk_with_time_only_keeps_name_without_inventing_date():
    output={'data':{'name':'เดิน','start':'16.00','end':None,'method':'self_report'},'evidence':{'name':'เดิน','start':'16.00'}}
    data,evidence=parse_extraction(json.dumps(output),'activity','เดิน 16.00')
    assert data=={'name':'เดิน','start':None,'end':None,'method':None}
    assert evidence=={'name':'เดิน'}
