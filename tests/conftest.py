"""Optional: run the whole suite against Postgres instead of SQLite.

    RUAMWAN_TEST_PG_URL=postgresql://... .venv/bin/python -m pytest -q

Each Store(path) gets its own throwaway schema 'ruamwan_test_<hash>', dropped
when the session ends. Production schema 'ruamwan' is never touched.
"""
import hashlib,os

TEST_URL=os.environ.get('RUAMWAN_TEST_PG_URL')
_schemas={}

def pytest_configure(config):
    if not TEST_URL:return
    from services import store
    original=store.Store.__init__
    def init(self,path,database_url=None,schema='ruamwan'):
        name='ruamwan_test_'+hashlib.sha256(str(path).encode()).hexdigest()[:16]
        original(self,path,database_url=TEST_URL,schema=name)
        _schemas[name]=self.backend
    store.Store.__init__=init

def pytest_unconfigure(config):
    if not TEST_URL or not _schemas:return
    import psycopg
    from services.pg_backend import close_pools
    close_pools()
    with psycopg.connect(TEST_URL,prepare_threshold=None) as conn:
        for name in _schemas:
            assert name.startswith('ruamwan_test_')
            conn.execute(f'DROP SCHEMA IF EXISTS {name} CASCADE')

# Tests never call a paid hosted model, even if the shell exports a key.
os.environ.pop('OPENROUTER_API_KEY',None)
