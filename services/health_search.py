"""Public MedlinePlus search; never send raw questions or owner data."""
import hashlib
import time
from datetime import datetime,timezone
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from services.chat_routing import SEARCH_TOPICS

ENDPOINT='https://wsearch.nlm.nih.gov/ws/query'

def parse_results(raw):
    root=ElementTree.fromstring(raw)
    found=[]
    for document in root.findall('.//document'):
        url=document.get('url','')
        if urlparse(url).scheme!='https' or urlparse(url).hostname!='medlineplus.gov':continue
        fields={c.get('name'):BeautifulSoup(c.text or '', 'html.parser').get_text(' ',strip=True) for c in document.findall('content')}
        text=fields.get('FullSummary') or fields.get('snippet') or ''
        if not text or not fields.get('title'):continue
        found.append({'document_id':'medlineplus-'+hashlib.sha256(url.encode()).hexdigest()[:16],
            'chunk_id':'medlineplus-'+hashlib.sha256((url+text).encode()).hexdigest()[:20],
            'heading':fields['title'],'text':text,'url':url,'publisher':'MedlinePlus, U.S. National Library of Medicine',
            'accessed_at':datetime.now(timezone.utc).date().isoformat(),
            'location':'MedlinePlus Web Service: '+('FullSummary' if fields.get('FullSummary') else 'search snippet'),
            'content_type':'source_summary','clinical_review':'not_reviewed','retrieval':'online'})
    return found[:2]

class HealthSearch:
    def __init__(self):self.cache={}
    def search(self,topic):
        if topic not in SEARCH_TOPICS:return {'status':'invalid_topic','citations':[]}
        cached=self.cache.get(topic)
        if cached and time.monotonic()-cached[0]<3600:return cached[1]
        try:
            # Explicit allowlist topic, fixed HTTPS host, no cookies, redirects or personal query.
            with httpx.Client(timeout=12,follow_redirects=False) as client:
                with client.stream('GET',ENDPOINT,params={'db':'healthTopics','term':topic,'retmax':2,'rettype':'brief','tool':'ruamwan'}) as response:
                    response.raise_for_status()
                    body=bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body)>1000000:raise ValueError('response too large')
            found=parse_results(bytes(body))
            result={'status':'evidence_found' if found else 'not_found','citations':found}
        except (httpx.HTTPError,ValueError,ElementTree.ParseError,DefusedXmlException):
            return {'status':'unavailable','citations':[]}
        self.cache[topic]=(time.monotonic(),result)
        return result
