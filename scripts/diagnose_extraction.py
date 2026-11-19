"""Inspect model formatting with SOFTWARE TEST ONLY input, never user records."""
import json,argparse
import inference

fixture=json.loads((inference.ROOT/'tests/extraction-software-fixture.json').read_text())
ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['original','thai-meal','thai-measurement','walk-activity','walk-meal'],default='original');args=ap.parse_args()
# Isolated software fixtures, never stored as demo records or training examples.
if args.case=='thai-meal':fixture={'kind':'meal','text':'กินข้าวต้มปลา 1 ชาม ตอนเช้า'}
if args.case=='thai-measurement':fixture={'kind':'measurement','text':'ชั่งน้ำหนักได้ 65 กิโลกรัม'}
if args.case in ('walk-activity','walk-meal'):fixture={'kind':'activity' if args.case=='walk-activity' else 'meal','text':'เดิน 16.00'}
original=inference.run
def traced(*args,**kwargs):
    response,metrics=original(*args,**kwargs)
    print(json.dumps({'software_test_raw_output':response},ensure_ascii=False),file=__import__('sys').stderr)
    return response,metrics
inference.run=traced
import io,sys
sys.stdin=io.StringIO(json.dumps(fixture));sys.argv=['inference.py','--task','extract']
inference.main()
