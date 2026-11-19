"""Load the exported model and backend; synthetic input, no owner data copied."""
import argparse,json,subprocess,sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.export_runtime import verify
from services.model_tasks import intent_messages,parse_intent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('bundle',nargs='?',default=str(ROOT/'dist/ruamwan-ai-macos-0.10.0'))
    args=parser.parse_args();bundle=Path(args.bundle).resolve()
    integrity=verify(bundle)
    worker=subprocess.run([sys.executable,str(bundle/'scripts/inference.py'),'--max-tokens','96'],
        input=json.dumps({'messages':intent_messages('คุณช่วยอะไรได้บ้าง')},ensure_ascii=False),
        text=True,capture_output=True,cwd=bundle,timeout=120)
    if worker.returncode:raise RuntimeError(worker.stderr[-2000:])
    generation=json.loads(worker.stdout)
    assert parse_intent(generation['output'])['intent']=='usage_help'
    # Backend import creates its own new temporary database, outside the export.
    with tempfile.TemporaryDirectory(prefix='ruamwan-bundle-check-') as temp:
        env=dict(os.environ,LOCAL_DB=str(Path(temp)/'software-only.sqlite3'))
        code='''import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    c.headers['x-csrf-token']=c.get('/api/session').json()['csrf']
    assert c.get('/').status_code==200
    r=c.post('/api/journal/prepare',json={'text':'ข้าวกับไข่พะโล้','use_model':False}).json()
    assert len(r['items'])==1
    assert r['items'][0]['check']['calculated']['energy']['kcal']==[432.9,432.9]
    assert r['items'][0]['record']['journal']['clock_source']=='capture_time'
    q=c.post('/api/journal/prepare',json={'text':'กินข้าวกับอะไรดี','use_model':False}).json()
    assert q['items']==[] and q['unparsed']
    assert c.get('/api/records').json()['items']==[]
    print(json.dumps({'backend_ready':True,'composite_meal_ready':True,'capture_default_ready':True,'question_guard_ready':True,'owner_records_written':False}))
'''
        backend=subprocess.run([sys.executable,'-c',code],cwd=bundle,env=env,text=True,capture_output=True,timeout=30)
        if backend.returncode:raise RuntimeError(backend.stderr[-2000:])
        backend_check=json.loads(backend.stdout)
    report={'label':'SOFTWARE EXPORT SMOKE ONLY; current installed environment, not fresh machine',
            'integrity':integrity,'generation':generation,'backend':backend_check,'after_run_integrity':verify(bundle)}
    (ROOT/'reports/export-model-smoke-v0.10.0.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'verified':True,'model_task':generation['metrics']['model_task'],**backend_check}))

if __name__=='__main__':main()
