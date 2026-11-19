"""Read-only fresh-session software checks. Never confirms health records."""
from pathlib import Path
import json,datetime,sys
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    checks=[]
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=180) as client:
        client.headers['X-CSRF-Token']=client.get('/api/session').json()['csrf']
        assert client.get('/openapi.json').json()['info']['version']=='0.10.0'
        before=client.get('/api/records').json()['items'];assert before==[]
        for question,status in [
            ('ฉันอยากให้คุณช่วยฉันจัดแพลนดูแลสุขภาพเกี่ยวกับเบาหวาน','care_plan_guidance'),
            ('ดอกไม้คืออะไร','out_of_scope'),('แนะนำหน่อยว่าฉันจะถามคุณว่าอะไรได้บ้าง','usage_help'),
            ('วันนี้ข้าวมันไก่ 1 จานกับไข่ต้ม 2 ฟองรวมกี่แคล','calorie_meal_summary'),
            ('ข้าวหมูแดงไข่ต้ม 1 จานกี่แคล','calorie_estimate'),
            ('สุกี้น้ำทะเล 1 ชามกี่แคล','calorie_estimate'),
            ('ข้าวกะเพราไก่ 1 จานกี่แคล','calorie_estimate'),
            ('นม 240 มล.กี่แคล','calorie_estimate'),
            ('อาหารไม่รู้จักกี่แคล','calorie_unknown'),
            ('เมื่อวานตอนเช้ากินข้าวมันไก่ครึ่งจานกับไข่ต้ม 2 ฟอง','agent_proposal'),
            ('ข้าวกับไข่พะโล้','agent_proposal'),
            ('วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง','agent_proposal'),
        ]:
            response=client.post('/api/chat',json={'messages':[{'role':'user','content':question}]});response.raise_for_status();result=response.json()
            assert result['status']==status,(question,result)
            if status=='care_plan_guidance':assert result['citations'] and 'ครึ่งจาน' in result['answer'] and not result['actions']
            if status=='calorie_meal_summary':assert result['total_kcal']==[718,779]
            if status=='agent_proposal':assert len(result['actions'][0]['records'])==(2 if 'ข้าวช้าว' in question else 1)
            checks.append({'query':question,'response':result})
        response=client.post('/api/journal/prepare',json={'text':'ตอนเช้ากินข้าวมันไก่ครึ่งจานกับไข่ต้ม 2 ฟอง','captured_at':'2026-10-12T12:00:00+07:00'});response.raise_for_status();journal=response.json()
        assert [i['record']['text'] for i in journal['items']]==['ข้าวมันไก่ กับ ไข่ต้ม']
        assert journal['items'][0]['check']['calculated']['energy']['kcal']==[439,469.5]
        assert all(i['check']['calculated']['energy']['kcal'] for i in journal['items'])
        checks.append({'journal':journal})
        for text,expected in [('ตอนเที่ยงกินข้าวกับไข่พะโล้',[432.9,432.9]),('ตอนเที่ยงกินข้าว 2 ทัพพีกับต้มพะโล้ครึ่งถ้วย',[339,339])]:
            response=client.post('/api/journal/prepare',json={'text':text,'captured_at':'2026-10-12T12:00:00+07:00','use_model':False});response.raise_for_status();j=response.json()
            assert len(j['items'])==1 and j['items'][0]['check']['calculated']['energy']['kcal']==expected
            assert len(j['items'][0]['record']['data']['components'])==2
            checks.append({'combined_meal':j})
        # Actual fixed-host public search, containing no personal query/data.
        from services.health_search import HealthSearch
        online=HealthSearch().search('diabetes')
        checks.append({'public_online_search':{'status':online['status'],'urls':[c['url'] for c in online['citations']]}})
        assert client.get('/api/records').json()['items']==before
    report={'label':'SOFTWARE LIVE CHECK ONLY; no clinical accuracy claim','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'no_health_records_written':True}
    (ROOT/'reports/nutrition-care-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'checks':len(checks),'online_search':online['status'],'no_health_records_written':True}))
if __name__=='__main__':main()
