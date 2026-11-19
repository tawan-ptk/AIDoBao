"""Run the authenticated origin for a Cloudflare/named HTTPS tunnel."""
import pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.run_api import configure_key

if __name__=='__main__':
    configure_key()
    import uvicorn
    uvicorn.run('services.gateway:app',host='127.0.0.1',port=8766,access_log=False,proxy_headers=False)
