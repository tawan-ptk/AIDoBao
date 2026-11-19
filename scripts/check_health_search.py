"""Generic public-topic connectivity check; no records, cookies or raw question."""
import json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from services.health_search import HealthSearch
if __name__=='__main__':
    result=HealthSearch().search('headache')
    print(json.dumps(result,ensure_ascii=False,indent=2))
