"""Gateway software fixtures: no public tunnel or real patient data."""
import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
from services.gateway import app,MAX_BODY

KEY='SOFTWARE-ONLY-'+'k'*48
AUTH={'Authorization':'Bearer '+KEY,'X-Ruamwan-User':'software:account-a'}

@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setenv('RUAMWAN_API_KEY',KEY)
    seen=[]
    async def send(method,path,**kwargs):
        seen.append({'method':method,'path':path,**kwargs})
        return httpx.Response(200,json={'items':[]},headers={'Set-Cookie':'must-not-escape=1'})
    with TestClient(app) as c:
        monkeypatch.setattr(app.state.upstream,'request',send)
        yield c,seen

def test_auth_and_route_gate_prevent_demo_sessions_and_cookie_bypass(gateway):
    c,seen=gateway
    assert c.get('/api/records',headers={'Cookie':'routine_session=pretend'}).status_code==401
    assert c.get('/api/records',headers=AUTH|{'Authorization':'Bearer wrong'}).status_code==401
    assert c.get('/api/records',headers={'Authorization':AUTH['Authorization']}).status_code==422
    for path in ('/','/docs','/openapi.json','/api/session','/static/app.js','/api/delete'):
        assert c.get(path,headers=AUTH).status_code==404
    assert c.get('/api/records',headers=AUTH|{'Origin':'https://site.vercel.app'}).status_code==403
    assert seen==[]

def test_forward_only_server_auth_body_query_and_no_session_cookie(gateway):
    c,seen=gateway
    r=c.post('/api/chat?test=1',headers=AUTH|{'Cookie':'routine_session=ignored','X-CSRF-Token':'ignored','X-Forwarded-Host':'evil.example'},json={'messages':[{'role':'user','content':'กินข้าว'}]})
    assert r.status_code==200 and r.headers['cache-control']=='no-store'
    assert 'set-cookie' not in r.headers
    assert seen[0]['path']=='/api/chat'
    assert dict(seen[0]['params'])=={'test':'1'}
    assert set(seen[0]['headers'])=={'Authorization','X-Ruamwan-User','Content-Type'}
    assert seen[0]['headers']['X-Ruamwan-User']=='software:account-a'

def test_size_capacity_timeout_and_fixed_upstream_errors(gateway,monkeypatch):
    c,seen=gateway
    assert c.post('/api/chat',headers=AUTH,content=b'x'*(MAX_BODY+1)).status_code==413
    monkeypatch.setattr(app.state,'capacity',asyncio.Semaphore(0))
    assert c.get('/api/records',headers=AUTH).status_code==429
    assert seen==[]
    monkeypatch.setattr(app.state,'capacity',asyncio.Semaphore(4))
    async def unavailable(*a,**k):raise httpx.ConnectError('private host details')
    monkeypatch.setattr(app.state.upstream,'request',unavailable)
    r=c.get('/api/records',headers=AUTH);assert r.status_code==502 and 'private host' not in r.text
    async def timeout(*a,**k):raise httpx.ReadTimeout('private details')
    monkeypatch.setattr(app.state.upstream,'request',timeout)
    assert c.get('/api/records',headers=AUTH).status_code==504
    async def redirect(*a,**k):return httpx.Response(302,headers={'Location':'https://untrusted.example'})
    monkeypatch.setattr(app.state.upstream,'request',redirect)
    assert c.get('/api/records',headers=AUTH).status_code==502
