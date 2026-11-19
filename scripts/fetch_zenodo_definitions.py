"""Fetch the original CC-BY questionnaire and dictionary linked by the paper."""
import json
from fetch_sources import fetch, ROOT

results=[]
for ident in ('5914387','5864806'):
    name='zenodo-'+ident+'.json'
    results.append(fetch('https://zenodo.org/api/records/'+ident,name))
    record=json.loads((ROOT/'data/raw'/name).read_text())
    for item in record['files']:
        results.append(fetch(item['links']['self'],'zenodo-'+ident+'-'+item['key']))
(ROOT/'reports/zenodo-definition-downloads.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('Saved questionnaire, dictionary and hashes')
