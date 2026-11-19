"""Additional primary-source snapshots used to corroborate the selected QA."""
import json,pathlib
from fetch_sources import fetch,ROOT
urls={
 'zenodo-paper.html':'https://f1000research.com/articles/11-332',
 'medline-diabetes.html':'https://medlineplus.gov/diabetes.html',
 'medline-diabetestype2.html':'https://medlineplus.gov/diabetestype2.html',
 'medline-exercise.html':'https://medlineplus.gov/exerciseandphysicalfitness.html',
 'medline-sleepdisorders.html':'https://medlineplus.gov/sleepdisorders.html',
 'typhoon-terms.html':'https://opentyphoon.ai/tac',
 'base-apache-LICENSE':'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/main/LICENSE',
}
results=[]
for name,url in urls.items():
    try:
        r=fetch(url,name);results.append(r);print(name,r['bytes'],flush=True)
    except Exception as e:results.append({'url':url,'file':name,'error':str(e)});print(name,e,flush=True)
(ROOT/'reports/review-downloads.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
