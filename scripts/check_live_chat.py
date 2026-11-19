"""Probe the live local API with generic questions; never create health records."""
import argparse
import json
import urllib.request
import http.cookiejar
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--question',default='สวัสดี')
    parser.add_argument('--report',help='Optional JSON report; only use generic, non-personal test questions')
    args=parser.parse_args()
    base='http://127.0.0.1:8765'
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with client.open(base+'/openapi.json',timeout=10) as response:
        schema=json.load(response)
    print(json.dumps({'version':schema['info']['version'],'chat_route':'/api/chat' in schema['paths']},ensure_ascii=False),flush=True)
    with client.open(base+'/api/session',timeout=10) as response:
        csrf=json.load(response)['csrf']
    body={'messages':[{'role':'user','content':args.question}],'scope':'auto'}
    request=urllib.request.Request(base+'/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','x-csrf-token':csrf})
    with client.open(request,timeout=200) as response:
        result=json.load(response)
        report={'question':args.question,'http_status':response.status,**result}
        if args.report:
            Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({k:report.get(k) for k in ('http_status','status','answer','model','metrics')},ensure_ascii=False,indent=2))
        else:print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
