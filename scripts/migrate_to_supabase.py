"""Copy every row from the local SQLite store to Supabase Postgres (schema 'ruamwan').

    .venv/bin/python scripts/migrate_to_supabase.py           # dry run: counts only
    .venv/bin/python scripts/migrate_to_supabase.py --apply   # copy + verify

- Reads SQLite read-only; the local file is never modified or deleted.
- Refuses to write if the target schema already has data (no merge, no overwrite).
- One transaction: either every row arrives or nothing does.
- Verifies row counts and a SHA-256 of every table's content afterwards.
- Prints table names and counts only, never record content or credentials.
"""
import argparse,hashlib,os,pathlib,sqlite3,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.env_file import load_env

TABLES={  # table: (columns, ordering key)
    'records':('id,owner,kind,payload,previous_id,version,created_at','id'),
    'revisions':('owner,revision','owner'),
    'plans':('id,owner,version,payload,input_revision,created_at','id'),
    'retries':('owner,key,digest,result','owner,key'),
    'audit':('id,owner,event,object_id,created_at','id'),
    'local_sessions':('token_hash,owner,csrf,expires_at','token_hash'),
    'integration_accounts':('subject_hash,owner','subject_hash'),
}

def digest(rows):
    h=hashlib.sha256()
    for row in rows:h.update(repr(tuple(getattr(row,'_values',row))).encode());h.update(b'\n')
    return h.hexdigest()

def main():
    load_env(ROOT/'.env')
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--verify',action='store_true',help='only compare an earlier copy; writes nothing')
    parser.add_argument('--sqlite',default=os.environ.get('LOCAL_DB',str(ROOT/'data/local.sqlite3')))
    args=parser.parse_args()
    url=os.environ.get('SUPABASE_DB_URL')
    if not url:sys.exit('SUPABASE_DB_URL is not set in .env')
    src=sqlite3.connect(f'file:{args.sqlite}?mode=ro',uri=True)
    source={t:src.execute(f'SELECT {cols} FROM {t} ORDER BY {key}').fetchall() for t,(cols,key) in TABLES.items()}
    for t,rows in source.items():print(f'SQLite {t}: {len(rows)}')
    from services.store import Store
    store=Store(args.sqlite,database_url=url)  # creates schema/tables if missing
    with store.connect() as conn:
        existing={t:conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in TABLES}
    if args.verify:return verify(store,source)
    if any(existing.values()):
        sys.exit(f'Target already has data {existing}; nothing was written.')
    if not args.apply:
        print('Dry run only. Target is empty and ready. Re-run with --apply to copy.');return
    with store.connect() as wrapped:
        conn=wrapped._conn
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('ruamwan_store'))")
        conn.execute('SET CONSTRAINTS ALL DEFERRED')  # records reference earlier versions
        for t,(cols,_) in TABLES.items():
            if not source[t]:continue
            marks=','.join(['%s']*len(cols.split(',')))
            with conn.cursor() as cur:
                cur.executemany(f'INSERT INTO {t}({cols}) VALUES({marks})',source[t])
        conn.execute("SELECT setval(pg_get_serial_sequence('audit','id'),GREATEST((SELECT COALESCE(MAX(id),0) FROM audit),1))")
    verify(store,source)

def verify(store,source):
    ok=True
    with store.connect() as conn:
        for t,(cols,key) in TABLES.items():
            rows=conn.execute(f'SELECT {cols} FROM {t} ORDER BY {key}').fetchall()
            same=len(rows)==len(source[t]) and digest(rows)==digest(source[t])
            ok&=same
            print(f'Supabase {t}: {len(rows)} {"OK" if same else "MISMATCH"}')
    if not ok:sys.exit('Verification failed. Local SQLite is unchanged; inspect before switching.')
    print('All tables copied and verified. Local SQLite was not modified.')

if __name__=='__main__':
    try:main()
    finally:
        from services.pg_backend import close_pools
        close_pools()
