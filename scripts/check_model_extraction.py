"""Explicit software fixture only; not an annotated patient accuracy benchmark."""
import json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from services.schemas import Record,inspect_record
fixture=(ROOT/'tests/extraction-software-fixture.json').read_text()
result=subprocess.run([sys.executable,str(ROOT/'scripts/inference.py'),'--task','extract'],input=fixture,text=True,capture_output=True,timeout=180,cwd=ROOT)
report={'label':'SOFTWARE TEST ONLY; never training or clinical validation','exit_code':result.returncode}
if result.returncode==0:
    report['result']=json.loads(result.stdout)
    report['schema_check']=inspect_record(Record.model_validate(report['result']['record']))
else:report['error']=result.stderr[-3000:]
(ROOT/'reports/model-extraction-software-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
