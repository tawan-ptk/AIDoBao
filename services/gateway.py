"""Authenticated, API-only ingress for a TLS tunnel; never exposes demo sessions.

The HTTPS provider terminates TLS; this process binds loopback only. Its fixed
upstream preserves the local app's Host/Origin restrictions and owner checks.
"""
import asyncio,os,re,secrets
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,Response

GET_PATHS={'records','plans','summary','personal-context','export','food-catalog','readiness'}
POST_PATHS={'chat','journal/prepare','records/preview','records/batch-preview','records/delete-preview','confirm','plans/preview','knowledge','food-energy','extract'}
MAX_BODY=100000

@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',timeout=httpx.Timeout(210,connect=5),follow_redirects=False,trust_env=False) as upstream:
        app.state.upstream=upstream
        app.state.capacity=asyncio.Semaphore(4)
        yield

app=FastAPI(title='Ruamwan authenticated gateway',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)

def fail(status,message):return JSONResponse({'detail':message},status_code=status,headers={'Cache-Control':'no-store'})

@app.api_route('/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'])
async def proxy(path:str,request:Request):
    key=os.environ.get('RUAMWAN_API_KEY','')
    if len(key)<32:return fail(503,'Gateway credentials are not configured')
    auth=request.headers.get('authorization','')
    if not secrets.compare_digest(auth.encode(),('Bearer '+key).encode()):return fail(401,'Invalid API credentials')
    user=request.headers.get('x-ruamwan-user','')
    if not user or len(user)>200 or not user.isascii() or any(ord(c)<33 or ord(c)>126 for c in user):return fail(422,'A verified X-Ruamwan-User is required')
    # Browser cookies/CSRF are deliberately unusable at this ingress.
    if request.headers.get('origin') is not None:return fail(403,'Use your authenticated website backend')
    endpoint=path.removeprefix('api/') if path.startswith('api/') else ''
    allowed=request.method=='GET' and (endpoint in GET_PATHS or bool(re.fullmatch(r'plans/[A-Za-z0-9_-]+/recheck',endpoint))) or request.method=='POST' and endpoint in POST_PATHS
    if not allowed:return fail(404,'Endpoint is not published')
    length=request.headers.get('content-length')
    if length is not None:
        try:valid_length=0<=int(length)<=MAX_BODY
        except ValueError:valid_length=False
        if not valid_length:return fail(413,'Request too large or invalid length')
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>MAX_BODY:return fail(413,'Request too large')
        chunks.append(chunk)
    capacity=request.app.state.capacity
    if capacity.locked():return fail(429,'AI gateway is busy; try again shortly')
    headers={'Authorization':auth,'X-Ruamwan-User':user}
    if request.headers.get('content-type'):headers['Content-Type']=request.headers['content-type']
    try:
        async with capacity:
            response=await request.app.state.upstream.request(request.method,'/api/'+endpoint,params=request.query_params,content=b''.join(chunks),headers=headers)
        if 300<=response.status_code<400:return fail(502,'Unexpected upstream redirect')
        return Response(response.content,status_code=response.status_code,headers={'Content-Type':response.headers.get('content-type','application/json'),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    except httpx.TimeoutException:return fail(504,'AI service timed out; check records before retrying a confirmation')
    except httpx.HTTPError:return fail(502,'AI service is unavailable')
