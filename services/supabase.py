"""Future adapter: caller supplies authenticated user JWT; no service key or model SQL."""
import os
import httpx
from services.schemas import Record,inspect_record
TABLES={'profile':'user_profiles','consent':'user_consents','constraint':'user_constraints','measurement':'health_measurements','medication':'medication_logs','appointment':'appointments','meal':'meal_logs','activity':'activity_logs','sleep':'sleep_logs','wellbeing':'wellbeing_logs','feedback':'plan_feedback'}
class SupabaseRepository:
    def __init__(self,user_jwt):
        url=os.environ.get('SUPABASE_URL','');key=os.environ.get('SUPABASE_ANON_KEY','')
        if not url or not key:raise ValueError('Supabase environment not configured; local demo does not require it')
        self.client=httpx.Client(base_url=url.rstrip('/')+'/rest/v1/',headers={'apikey':key,'Authorization':'Bearer '+user_jwt},timeout=20)
    def list_records(self,kind,limit=50,offset=0):
        table=TABLES[kind];r=self.client.get(table,params={'select':'*','order':'created_at.desc,id','limit':max(1,min(limit,100)),'offset':max(0,offset)});r.raise_for_status();return r.json()
    def record_payload(self,owner_id,record,idempotency_key):
        r=Record.model_validate(record);check=inspect_record(r)
        if not check['can_record']:raise ValueError('unvalidated record')
        payload=r.data if r.journal is None else r.data|{'_journal':r.journal.model_dump(mode='json'),'_text':r.text}
        return TABLES[r.kind],{'owner_id':owner_id,'payload':payload,'origin':r.origin,'provenance':{'source':r.source,'evidence':r.evidence},'previous_id':r.previous_id,'program_status':check['status'],'user_status':'confirmed','idempotency_key':idempotency_key}
    def confirm_plan(self,proposal_id,idempotency_key):
        # Proposal inserted by trusted backend only, after local service checks.
        r=self.client.post('rpc/confirm_plan',json={'p_proposal_id':proposal_id,'p_idempotency_key':idempotency_key});r.raise_for_status();return r.json()
    def export(self):
        r=self.client.post('rpc/export_my_data',json={});r.raise_for_status();return r.json()
    def delete(self,confirmation):
        r=self.client.post('rpc/delete_my_data',json={'p_confirmation':confirmation});r.raise_for_status()
