import hashlib, json, pathlib
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'data/raw/niddk.html';soup=BeautifulSoup(p.read_text(),'html.parser')
# Keep a whole H2 section, including subordinate lists/conditions; never token-truncate.
chunks=[]
for i,h in enumerate(soup.find_all('h2')):
    title=h.get_text(' ',strip=True)
    if not title.startswith(('How can','What can','Should I','How do')):continue
    nodes=[]
    for node in h.next_siblings:
        if getattr(node,'name',None)=='h2':break
        if getattr(node,'name',None) in ('script','style','figure'):continue
        if hasattr(node,'get_text'):
            text=node.get_text(' ',strip=True)
            if text:nodes.append(text)
    text='\n'.join(nodes)
    if text:
        chunks.append({'document_id':'niddk-healthy','chunk_id':f'niddk-healthy-h2-{i}','heading':title,'location':f'h2 index {i}; '+title,'url':'https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes','publisher':'NIDDK, National Institutes of Health','accessed_at':'2026-10-11','document_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text,'license':'NIDDK copyright-free text subject to exceptions; no images/logos imported','rights_url':'https://www.niddk.nih.gov/copyright','population':'people with diabetes; section-specific exceptions retained','clinical_review':'not_reviewed'})
(ROOT/'data/knowledge/chunks.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in chunks)+'\n')
print('Indexed complete source sections:',len(chunks))
