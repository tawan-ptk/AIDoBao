"""Software fixtures only. No training examples, patient records or clinical claims."""
import argparse,json,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from services.journal import prepare_journal,classification_prompt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model',action='store_true');a=ap.parse_args()
    stamp='2026-10-12T09:00:00+07:00'
    cases=[('เดิน 16.00',['activity']),('ตอนเช้ากินข้าว 1 จาน ตอนบ่ายเดิน',['meal','activity']),('ช่วงเช้า กินข้าว\nช่วงบ่าย งีบ',['meal','sleep']),('กินยา 1 เม็ด ตอนเย็น',['medication']),('นัดหมอ 10:30',['appointment']),('ชั่งน้ำหนัก 65 กิโลกรัม',['measurement']),('รู้สึกเหนื่อยและเครียด',['wellbeing']),('นอน 23.00-07.00',['sleep']),('เมื่อวานตอนเช้า\nกินข้าว\nเดิน',['meal','activity']),('น้ำหนัก 16.00 กก',['measurement']),('ไม่ได้เดิน',[]),('พรุ่งนี้จะเดิน',[]),('กินน้ำตาล 1 ช้อน',['meal'])]
    report={'label':'SOFTWARE TEST ONLY; no clinical or real-user accuracy estimate','date_policy':'Bangkok capture date unless explicitly specified','cases':[]}
    for text,expected in cases:
        start=time.perf_counter();r=prepare_journal(text,stamp);actual=[x['record']['kind'] for x in r['items']]
        report['cases'].append({'text':text,'expected_kinds':expected,'actual_kinds':actual,'pass':actual==expected,'elapsed_ms':(time.perf_counter()-start)*1000,'result':r})
    report['rules_passed']=sum(x['pass'] for x in report['cases']);report['rules_total']=len(cases)
    if a.model:
        from scripts.inference import run
        parts=['มื้อเช้าเป็นข้าวต้มปลา 1 ถ้วย','ปวดหัวตอนบ่าย']
        output,metrics=run([{'role':'system','content':classification_prompt(parts)},{'role':'user','content':'Return the category JSON only.'}],max_tokens=512)
        result=prepare_journal('\n'.join(parts),stamp,output)
        report['model_smoke']={'raw_fixture_output':output,'metrics':metrics,'result':result,'expected_kinds':['meal','wellbeing'],'actual_kinds':[x['record']['kind'] for x in result['items']]}
    path=ROOT/'reports/journal-software-check.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'rules_passed':report['rules_passed'],'rules_total':report['rules_total'],'model_smoke':report.get('model_smoke'),'report':str(path)},ensure_ascii=False,indent=2))
    if report['rules_passed']!=report['rules_total']:sys.exit(1)
if __name__=='__main__':main()
