"""SOFTWARE TEST ONLY: official search parsing, bounded requests and privacy."""
from services.health_search import HealthSearch,parse_results
import httpx

XML=b'''<nlmSearchResult><list><document url="https://medlineplus.gov/headache.html"><content name="title">Headache</content><content name="FullSummary">&lt;p&gt;SOFTWARE TEST SUMMARY&lt;/p&gt;</content></document><document url="https://untrusted.test"><content name="title">Bad</content><content name="FullSummary">Bad</content></document></list></nlmSearchResult>'''

def test_parse_official_summaries_and_ignore_external_urls():
 r=parse_results(XML)
 assert len(r)==1 and r[0]['heading']=='Headache' and r[0]['text']=='SOFTWARE TEST SUMMARY'
 assert r[0]['retrieval']=='online' and r[0]['publisher'].startswith('MedlinePlus')

def test_external_search_is_fixed_host_and_allowlisted_topic_with_cache(monkeypatch):
 calls=[]
 class Response:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def raise_for_status(self):pass
  def iter_bytes(self):yield XML
 class Client:
  def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def stream(self,method,url,params):
   calls.append((url,params));return Response()
 monkeypatch.setattr(httpx,'Client',Client)
 s=HealthSearch()
 assert s.search('headache')['status']=='evidence_found'
 assert s.search('headache')['status']=='evidence_found' and len(calls)==1
 assert calls[0][0]=='https://wsearch.nlm.nih.gov/ws/query'
 assert calls[0][1]['term']=='headache'
 assert s.search('PRIVATE NAME and headache')['status']=='invalid_topic' and len(calls)==1

def test_network_failure_is_explicit_and_not_cached_forever(monkeypatch):
 def fail(**kw):raise httpx.ConnectError('SOFTWARE TEST ONLY')
 monkeypatch.setattr(httpx,'Client',fail)
 s=HealthSearch();assert s.search('headache')=={'status':'unavailable','citations':[]}
 assert not s.cache

def test_online_answer_can_only_publish_exact_sentences_not_model_claims():
 from services.chat import online_answer
 citations=parse_results(XML)
 r=online_answer([{'role':'user','content':'SOFTWARE QUESTION'}],citations,lambda m:{'output':'{"sentence_ids":[0]}'})
 assert r['status']=='answered_from_online_sources'
 assert r['answer'].endswith(citations[0]['text'])
 for output in ['{"sentence_ids":[999]}','{"sentence_ids":[true]}','UNSUPPORTED MEDICAL CLAIM']:
  r=online_answer([{'role':'user','content':'SOFTWARE QUESTION'}],citations,lambda m:{'output':output})
  assert r['status']=='source_excerpt' and 'UNSUPPORTED MEDICAL CLAIM' not in r['answer']
  assert r['answer'].endswith(citations[0]['text'])
