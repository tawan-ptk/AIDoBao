"""Private same-host AI API; generates a server credential, never prints it."""
import os,pathlib,secrets,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.env_file import load_env
load_env(ROOT/'.env')  # e.g. SUPABASE_DB_URL; values are never printed

def configure_key():
    key=os.environ.get('RUAMWAN_API_KEY')
    if key is None:
        path=ROOT/'.secrets/api-key'
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if path.is_symlink():raise ValueError('API key file must not be a symlink')
        try:
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:file.write(secrets.token_urlsafe(48))
        except FileExistsError:pass
        key=path.read_text().strip()
    if len(key)<32 or not key.isascii() or any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError('RUAMWAN_API_KEY must be at least 32 printable ASCII characters')
    os.environ['RUAMWAN_API_KEY']=key

if __name__=='__main__':
    configure_key()
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=8765,access_log=False)
