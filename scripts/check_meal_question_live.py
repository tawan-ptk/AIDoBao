"""Generic fresh-session live regressions; never confirms health records."""
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
def main():
    checks=[]
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=120) as client:
        client.headers['x-csrf-token']=client.get('/api/session').json()['csrf']
        assert client.get('/openapi.json').json()['info']['version']=='0.10.0'
        before=client.get('/api/records').json()['items'];assert before==[]
        for question,status in [
            ('กินข้าวกับอะไรดี','meal_ideas'),('ข้าวกับอะไรดี','meal_ideas'),
            ('วันนี้กินข้าวกับอะไรดี','meal_ideas'),
            ('วันนี้กินอะไรไปบ้าง','no_records'),
            ('กินข้าวกับไข่พะโล้','agent_proposal'),('ข้าวกับไข่พะโล้','agent_proposal'),
            ('ดอกไม้คืออะไร','out_of_scope'),
        ]:
            response=client.post('/api/chat',json={'messages':[{'role':'user','content':question}]})
            response.raise_for_status();result=response.json()
            assert result['status']==status,(question,result)
            if status=='meal_ideas':
                assert result['menus'] and result['mode']=='read_only'
                assert not any(a['type'] in ('records','journal') for a in result.get('actions',[]))
                assert 'แยกได้' not in result['answer'] and '80 kcal' not in result['answer']
            if status=='agent_proposal':
                assert len(result['actions'][0]['records'])==1
                assert len(result['actions'][0]['records'][0]['data']['components'])==2
            checks.append({'question':question,'result':result})
        response=client.post('/api/journal/prepare',json={'text':'กินข้าวกับอะไรดี'})
        response.raise_for_status();result=response.json()
        assert result['items']==[] and result['unparsed'] and 'model_metrics' not in result
        checks.append({'journal_question':result})
        assert client.get('/api/records').json()['items']==before
    report={'label':'SOFTWARE LIVE REGRESSION ONLY; actual local menu model path, no clinical accuracy claim',
            'checks':checks,'no_health_records_written':True}
    (ROOT/'reports/meal-question-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'checks':len(checks),'no_health_records_written':True}))

if __name__=='__main__':main()
