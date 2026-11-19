import argparse,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.env_file import load_env
load_env(ROOT/'.env')  # e.g. SUPABASE_DB_URL; values are never printed
if __name__=='__main__':
    import uvicorn
    parser=argparse.ArgumentParser()
    parser.add_argument('--reload',action='store_true',help='Reload app/services Python changes during development')
    args=parser.parse_args()
    uvicorn.run('app.main:app',host='127.0.0.1',port=8765,access_log=False,
                reload=args.reload,reload_dirs=[str(ROOT/'app'),str(ROOT/'services')] if args.reload else None)
