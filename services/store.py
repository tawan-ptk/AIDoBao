"""Owner-scoped append-only records; atomic confirmation and retry protection."""
import hashlib, json, pathlib, sqlite3, uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from services.schemas import Record, inspect_record

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def now():return datetime.now(timezone.utc).isoformat()

class Store:
    """SQLite by default; Postgres (Supabase) when database_url is given."""
    def __init__(self,path,database_url=None,schema='ruamwan'):
        self.path=str(path);self.backend=None
        if database_url:
            from services.pg_backend import PostgresBackend
            self.backend=PostgresBackend(database_url,schema)
            return
        pathlib.Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, previous_id TEXT REFERENCES records(id), version INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS record_successor ON records(previous_id) WHERE previous_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS record_owner_kind ON records(owner,kind,created_at);
            CREATE TABLE IF NOT EXISTS revisions(owner TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,owner TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,input_revision INTEGER NOT NULL,created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS plan_owner ON plans(owner,version);
            CREATE TABLE IF NOT EXISTS retries(owner TEXT NOT NULL,key TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(owner,key));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,owner TEXT NOT NULL,event TEXT NOT NULL,object_id TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS local_sessions(token_hash TEXT PRIMARY KEY,owner TEXT NOT NULL,csrf TEXT NOT NULL,expires_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS integration_accounts(subject_hash TEXT PRIMARY KEY,owner TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS draft_owner ON drafts(owner,created);
            ''')
    # Pending previews live in the database so preview and confirm may be
    # served by different processes (serverless). They expire after 30 minutes.
    DRAFT_TTL=1800
    def draft_put(self,ident,owner,kind,payload,limit=100):
        import time
        stamp=time.time()
        with self.connect() as c:
            c.execute('DELETE FROM drafts WHERE created<?',(stamp-self.DRAFT_TTL,))
            if c.execute('SELECT COUNT(*) FROM drafts WHERE owner=?',(owner,)).fetchone()[0]>=limit:return False
            c.execute('INSERT INTO drafts VALUES(?,?,?,?,?)',(ident,owner,kind,canonical(payload),stamp))
        return True
    def draft_get(self,ident,owner):
        import time
        with self.connect() as c:
            row=c.execute('SELECT owner,kind,payload,created FROM drafts WHERE id=?',(ident,)).fetchone()
        if not row or row['owner']!=owner or time.time()-row['created']>self.DRAFT_TTL:return None
        return {'owner':row['owner'],'kind':row['kind'],'payload':json.loads(row['payload'])}
    def drafts_clear(self,owner,keep=None):
        with self.connect() as c:
            if keep is None:c.execute('DELETE FROM drafts WHERE owner=?',(owner,))
            else:c.execute('DELETE FROM drafts WHERE owner=? AND id<>?',(owner,keep))
    def connect(self):
        if self.backend:return self.backend.connect()
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
    def session_get(self,token):
        import time
        if not token:return None
        with self.connect() as c:
            row=c.execute('SELECT owner,csrf FROM local_sessions WHERE token_hash=? AND expires_at>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return dict(row) if row else None
    def integration_owner(self,subject):
        # External account IDs are mapped persistently, independent of API key
        # rotation and browser session expiry. Raw IDs are not stored here.
        digest=hashlib.sha256(subject.encode()).hexdigest()
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO integration_accounts VALUES(?,?)',(digest,uuid.uuid4().hex))
            return c.execute('SELECT owner FROM integration_accounts WHERE subject_hash=?',(digest,)).fetchone()['owner']
    def session_save(self,token,owner,csrf):
        import time
        with self.connect() as c:c.execute('INSERT INTO local_sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),owner,csrf,time.time()+7*86400))
    def revision(self,owner,c=None):
        if c is None:
            with self.connect() as con:return self.revision(owner,con)
        row=c.execute('SELECT revision FROM revisions WHERE owner=?',(owner,)).fetchone();return row[0] if row else 0
    def _retry(self,c,owner,key,payload):
        if not key or len(key)>200:raise ValueError('invalid idempotency key')
        digest=hashlib.sha256(canonical(payload).encode()).hexdigest()
        old=c.execute('SELECT * FROM retries WHERE owner=? AND key=?',(owner,key)).fetchone()
        if old:
            if old['digest']!=digest:raise ValueError('retry key reused with different data')
            return digest,json.loads(old['result'])
        return digest,None
    def confirm_record(self,owner,record,key,_connection=None):
        r=Record.model_validate(record);check=inspect_record(r)
        if not check['can_record']:raise ValueError(canonical(check))
        payload=r.model_dump(mode='json')
        with (self.connect() if _connection is None else nullcontext(_connection)) as c:
            if _connection is None:c.execute('BEGIN IMMEDIATE')
            digest,old=self._retry(c,owner,key,payload)
            if old:return old
            if r.kind!='consent':
                consent=c.execute("SELECT 1 FROM records WHERE owner=? AND kind='consent'",(owner,)).fetchone()
                if not consent:raise ValueError('ต้องยินยอมเก็บข้อมูลในเครื่องก่อน')
            if not r.previous_id:
                for active in c.execute('SELECT payload FROM records r WHERE owner=? AND kind=? AND NOT EXISTS(SELECT 1 FROM records s WHERE s.previous_id=r.id)',(owner,r.kind)):
                    existing=json.loads(active[0])
                    same_journal=existing.get('journal')==payload.get('journal') and existing.get('text')==r.text
                    if existing['data']==r.data and existing['origin']==r.origin and (not r.journal or same_journal):
                        raise ValueError('มีรายการเดียวกันที่ยืนยันแล้ว ไม่บันทึกซ้ำ; หากแก้ไขให้ระบุเวอร์ชันเดิม')
            version=1
            if r.previous_id:
                prior=c.execute('SELECT * FROM records WHERE owner=? AND id=?',(owner,r.previous_id)).fetchone()
                if not prior or prior['kind']!=r.kind:raise ValueError('ไม่พบเวอร์ชันเดิมของเจ้าของข้อมูล')
                if c.execute('SELECT 1 FROM records WHERE previous_id=?',(r.previous_id,)).fetchone():raise ValueError('เวอร์ชันเดิมถูกแก้แล้ว กรุณาโหลดใหม่')
                version=prior['version']+1
            ident=str(uuid.uuid4());stamp=now()
            c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?)',(ident,owner,r.kind,canonical(payload),r.previous_id,version,stamp))
            c.execute('INSERT INTO revisions VALUES(?,1) ON CONFLICT(owner) DO UPDATE SET revision=revision+1',(owner,))
            result={'id':ident,'version':version,'status':'user_confirmed','check':check,'revision':self.revision(owner,c)}
            c.execute('INSERT INTO retries VALUES(?,?,?,?)',(owner,key,digest,canonical(result)))
            c.execute('INSERT INTO audit(owner,event,object_id,created_at) VALUES(?,?,?,?)',(owner,'record_confirmed',ident,stamp))
            return result
    def confirm_batch(self,owner,records,key):
        if not 1<=len(records)<=30:raise ValueError('บันทึกครั้งละ 1–30 รายการ')
        payload={'records':records}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            digest,old=self._retry(c,owner,key,payload)
            if old:return old
            results=[self.confirm_record(owner,r,'batch:'+hashlib.sha256((key+':'+str(i)).encode()).hexdigest(),_connection=c) for i,r in enumerate(records)]
            result={'items':results,'count':len(results),'status':'user_confirmed'}
            c.execute('INSERT INTO retries VALUES(?,?,?,?)',(owner,key,digest,canonical(result)))
            return result
    def records(self,owner,limit=100,offset=0,current=True):
        limit=max(1,min(limit,500));offset=max(0,offset)
        where=' AND NOT EXISTS(SELECT 1 FROM records s WHERE s.previous_id=r.id)' if current else ''
        with self.connect() as c:
            rows=c.execute('SELECT * FROM records r WHERE owner=?'+where+' ORDER BY created_at,id LIMIT ? OFFSET ?',(owner,limit,offset)).fetchall()
        return [json.loads(r['payload'])|{'id':r['id'],'version':r['version'],'created_at':r['created_at'],'status':'user_confirmed'} for r in rows]
    def all_current(self,owner):
        out=[]
        while True:
            page=self.records(owner,500,len(out));out.extend(page)
            if len(page)<500:return out
    def confirm_plan(self,owner,plan,key):
        if plan['status']!='pass':raise ValueError('ยืนยันแผนที่จัดเวลาไม่สำเร็จไม่ได้')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');digest,old=self._retry(c,owner,key,plan)
            if old:return old
            if self.revision(owner,c)!=plan['input_revision']:raise ValueError('ข้อมูลเปลี่ยน ต้องตรวจแผนใหม่ก่อนยืนยัน')
            version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM plans WHERE owner=?',(owner,)).fetchone()[0]
            ident=str(uuid.uuid4());stamp=now()
            final=plan|{'id':ident,'version':version,'user_status':'confirmed','items':[x|{'confirmation':'user_confirmed'} for x in plan['items']]}
            c.execute('INSERT INTO plans VALUES(?,?,?,?,?,?)',(ident,owner,version,canonical(final),plan['input_revision'],stamp))
            c.execute('INSERT INTO retries VALUES(?,?,?,?)',(owner,key,digest,canonical(final)))
            c.execute('INSERT INTO audit(owner,event,object_id,created_at) VALUES(?,?,?,?)',(owner,'plan_confirmed',ident,stamp))
            return final
    def plans(self,owner,limit=20,offset=0):
        with self.connect() as c:
            rows=c.execute('SELECT payload FROM plans WHERE owner=? ORDER BY version DESC LIMIT ? OFFSET ?',(owner,min(max(limit,1),100),max(offset,0))).fetchall()
        rev=self.revision(owner)
        return [json.loads(r[0])|{'requires_revalidation':json.loads(r[0])['input_revision']!=rev} for r in rows]
    def get_plan(self,owner,ident):
        with self.connect() as c:r=c.execute('SELECT payload FROM plans WHERE owner=? AND id=?',(owner,ident)).fetchone()
        if not r:raise ValueError('ไม่พบแผน')
        return json.loads(r[0])
    def export(self,owner):
        with self.connect() as c:
            return {table:[dict(r) for r in c.execute(f'SELECT * FROM {table} WHERE owner=?',(owner,))] for table in ('records','plans','audit')}
    def _deletion_scope(self,c,owner,ids,scope):
        rows={r['id']:r for r in c.execute('SELECT * FROM records WHERE owner=?',(owner,))}
        superseded={r['previous_id'] for r in rows.values() if r['previous_id']}
        current={ident:r for ident,r in rows.items() if ident not in superseded}
        if scope=='all':selected=list(current.values());removed=set(rows)
        else:
            if not ids or len(ids)!=len(set(ids)) or any(i not in current for i in ids):raise ValueError('รายการเปลี่ยนหรือไม่พบข้อมูลของคุณ กรุณาขอรายการใหม่')
            selected=[current[i] for i in ids]
            if any(r['kind']=='consent' for r in selected):raise ValueError('หากถอนความยินยอม ให้ใช้ลบข้อมูลทั้งหมดครับ')
            removed=set()
            for row in selected:
                while row:
                    removed.add(row['id']);row=rows.get(row['previous_id'])
        # Plans embed labels and provenance. Remove only affected plans;
        # profile/constraint deletion invalidates their entire care/time context.
        reset_plans=scope=='all' or any(r['kind'] in ('profile','constraint') for r in selected)
        def refers(value):
            if isinstance(value,dict):return any(refers(v) for v in value.values())
            if isinstance(value,list):return any(refers(v) for v in value)
            return isinstance(value,str) and (value in removed or any(value.startswith('user_record:'+i) or value.startswith(i+':') for i in removed))
        plans=[r['id'] for r in c.execute('SELECT id,payload FROM plans WHERE owner=?',(owner,)) if reset_plans or refers(json.loads(r['payload']))]
        return selected,removed,plans
    def deletion_preview(self,owner,ids,scope='records'):
        if scope not in ('records','all'):raise ValueError('invalid deletion scope')
        with self.connect() as c:
            c.execute('BEGIN')
            selected,removed,plans=self._deletion_scope(c,owner,ids,scope)
            return {'scope':scope,'record_ids':ids,'input_revision':self.revision(owner,c),'plan_ids':sorted(plans),
                    'records':[json.loads(r['payload'])|{'id':r['id'],'version':r['version']} for r in selected],
                    'count':len(selected),'history_count':len(removed),'plan_count':len(plans)}
    def confirm_delete(self,owner,payload,key):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');digest,old=self._retry(c,owner,key,payload)
            if old:return old
            if self.revision(owner,c)!=payload['input_revision']:raise ValueError('ข้อมูลเปลี่ยนแล้ว กรุณาขอรายการลบใหม่ก่อนยืนยัน')
            selected,removed,plans=self._deletion_scope(c,owner,payload['record_ids'],payload['scope'])
            if sorted(plans)!=payload['plan_ids']:raise ValueError('แผนเปลี่ยนแล้ว กรุณาตรวจรายการลบใหม่')
            c.execute('PRAGMA defer_foreign_keys=ON')
            for ident in removed:c.execute('DELETE FROM records WHERE owner=? AND id=?',(owner,ident))
            for ident in plans:c.execute('DELETE FROM plans WHERE owner=? AND id=?',(owner,ident))
            # Cached plan confirmation results can also contain deleted labels.
            c.execute('DELETE FROM retries WHERE owner=?',(owner,))
            if payload['scope']=='all':c.execute('DELETE FROM audit WHERE owner=?',(owner,))
            else:
                for ident in removed|set(plans):c.execute('DELETE FROM audit WHERE owner=? AND object_id=?',(owner,ident))
            c.execute('INSERT INTO revisions VALUES(?,1) ON CONFLICT(owner) DO UPDATE SET revision=revision+1',(owner,))
            result={'deleted':True,'scope':payload['scope'],'count':len(selected),'history_count':len(removed),'plan_count':len(plans),'revision':self.revision(owner,c)}
            c.execute('INSERT INTO retries VALUES(?,?,?,?)',(owner,key,digest,canonical(result)))
            return result
    def delete(self,owner):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('PRAGMA defer_foreign_keys=ON')
            for table in ('records','plans','audit','retries','revisions'):c.execute(f'DELETE FROM {table} WHERE owner=?',(owner,))
        return {'deleted':True,'scope':'local database rows; user-created export files are separate'}
