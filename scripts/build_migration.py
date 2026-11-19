"""Generate the checked-in initial migration. No connection or deployment."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
USER_TABLES=['user_profiles','user_consents','user_constraints','clinician_targets','health_measurements','medication_schedules','medication_logs','appointments','meal_logs','activity_logs','sleep_logs','wellbeing_logs','plan_feedback']
sql='''-- Local prototype migration; execute in a disposable Supabase project only after review.
-- No model resides in Edge Functions. Clinical review is not writable by end users.
begin;
create extension if not exists pgcrypto;
create table public.user_revisions(owner_id uuid primary key references auth.users(id) on delete cascade, revision bigint not null default 0);
alter table public.user_revisions enable row level security;
create policy owner_read on public.user_revisions for select to authenticated using(owner_id=auth.uid());
create function public.bump_input_revision() returns trigger language plpgsql security definer set search_path=public,pg_temp as $$
begin
 insert into public.user_revisions(owner_id,revision) values(new.owner_id,1)
 on conflict(owner_id) do update set revision=user_revisions.revision+1;
 return new;
end $$;
create table public.source_documents(id text primary key,title text not null,publisher text not null,url text not null,revision text,sha256 text,accessed_at timestamptz not null,rights jsonb not null,population text,exceptions text);
create table public.source_chunks(id text primary key,document_id text not null references public.source_documents(id),location text not null,content text not null,sha256 text not null);
create table public.rules(id text primary key,version integer not null,kind text not null check(kind in ('program','health')),condition jsonb not null,required_fields jsonb not null,units jsonb not null,scope jsonb not null,missing_action text not null default 'unknown',source_chunk_id text references public.source_chunks(id),review_status text not null check(review_status in ('draft','reviewed','deprecated')),reviewer text,reviewed_at timestamptz,enabled boolean not null default false,check(not enabled or kind='program' or (review_status='reviewed' and reviewer is not null and reviewed_at is not null)));
create table public.foods(id text primary key,name text not null,food_kind text not null check(food_kind in ('generic','recipe','branded')),state text not null,basis_grams numeric not null check(basis_grams>0),edible_basis boolean not null,source_document_id text not null references public.source_documents(id),source_record_id text not null,ingredients_complete boolean not null default false);
create table public.food_nutrients(food_id text references public.foods(id),nutrient text not null,value numeric check(value>=0),unit text not null,method text not null,primary key(food_id,nutrient));
create table public.portions(id uuid primary key default gen_random_uuid(),food_id text not null references public.foods(id),name text not null,grams numeric not null check(grams>0),source_document_id text not null references public.source_documents(id));
create table public.food_source_mappings(food_id text references public.foods(id),source_document_id text references public.source_documents(id),source_record_id text not null,primary key(food_id,source_document_id,source_record_id));
create table public.recipes(id uuid primary key default gen_random_uuid(),name text not null,yield_grams numeric check(yield_grams>0),source_document_id text not null references public.source_documents(id));
create table public.recipe_ingredients(recipe_id uuid references public.recipes(id),food_id text references public.foods(id),edible_grams numeric not null check(edible_grams>0),primary key(recipe_id,food_id));
create table public.activity_catalog(id text primary key,name text not null,activity_type text not null,intensity_definition text,source_chunk_id text not null references public.source_chunks(id),equipment jsonb,conditions jsonb,review_status text not null default 'draft');
'''
for table in USER_TABLES:
    # Partial journal entries are confirmed text, while structured completeness stays unknown.
    journal_tables={'health_measurements','medication_logs','appointments','meal_logs','activity_logs','sleep_logs','wellbeing_logs'}
    insert_status="program_status='pass'"
    if table in journal_tables:
        insert_status="(program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0))"
    sql+=f'''create table public.{table}(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.{table}(owner_id,id) deferrable initially deferred);
 alter table public.{table} enable row level security;
 create policy owner_read on public.{table} for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.{table} for insert to authenticated with check(owner_id=auth.uid() and {insert_status} and clinician_review='not_reviewed');
 create index {table}_page on public.{table}(owner_id,created_at,id);
 create trigger {table}_revision after insert on public.{table} for each row execute function public.bump_input_revision();
'''
sql+='''
create table public.meal_log_items(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,meal_log_id uuid not null,food_id text references public.foods(id),quantity numeric check(quantity>0),unit text,provenance jsonb not null,foreign key(owner_id,meal_log_id) references public.meal_logs(owner_id,id) on delete cascade);
create table public.plan_proposals(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,input_revision bigint not null,result jsonb not null,created_at timestamptz not null default now());
-- Only trusted backend may insert checked proposals; authenticated clients can read/confirm.
alter table public.plan_proposals enable row level security;
create policy owner_read on public.plan_proposals for select to authenticated using(owner_id=auth.uid());
create table public.plans(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,version integer not null,input_revision bigint not null,proposal_id uuid not null references public.plan_proposals(id),user_status text not null check(user_status='confirmed'),program_status text not null check(program_status='pass'),clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),idempotency_key uuid not null,created_at timestamptz not null default now(),unique(owner_id,version),unique(owner_id,id),unique(owner_id,idempotency_key));
create table public.plan_items(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,plan_id uuid not null,start_at timestamptz not null,end_at timestamptz not null,payload jsonb not null,check(end_at>start_at),foreign key(owner_id,plan_id) references public.plans(owner_id,id) on delete cascade);
create table public.rule_evaluations(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,plan_id uuid,rule_id text not null references public.rules(id),result text not null check(result in ('pass','fail','unknown','not_applicable')),input_revision bigint not null,foreign key(owner_id,plan_id) references public.plans(owner_id,id) on delete cascade);
create table public.audit_events(id uuid primary key default gen_random_uuid(),owner_id uuid not null references auth.users(id) on delete cascade,event_type text not null,object_id uuid not null,created_at timestamptz not null default now());
create index plan_pagination on public.plans(owner_id,version desc);
create index plan_item_time on public.plan_items(owner_id,start_at);
'''
for table in ['meal_log_items','plans','plan_items','rule_evaluations','audit_events']:
    sql+=f'alter table public.{table} enable row level security;\ncreate policy owner_read on public.{table} for select to authenticated using(owner_id=auth.uid());\n'
for table in ['source_documents','source_chunks','rules','foods','food_nutrients','portions','food_source_mappings','recipes','recipe_ingredients','activity_catalog']:
    sql+=f'alter table public.{table} enable row level security;\ncreate policy catalog_read on public.{table} for select to authenticated using(true);\n'
sql+='''
create function public.confirm_plan(p_proposal_id uuid,p_idempotency_key uuid) returns uuid
language plpgsql security definer set search_path=public,pg_temp as $$
declare uid uuid:=auth.uid(); p public.plan_proposals; saved public.plans; ident uuid; next_version integer; rev bigint; item jsonb;
begin
 if uid is null then raise exception 'unauthorized'; end if;
 -- Serialize confirmations and input updates on the same owner's revision row.
 select revision into rev from public.user_revisions where owner_id=uid for update;
 select * into saved from public.plans where owner_id=uid and idempotency_key=p_idempotency_key;
 if found then
   if saved.proposal_id<>p_proposal_id then raise exception 'idempotency key conflict'; end if;
   return saved.id;
 end if;
 select * into p from public.plan_proposals where id=p_proposal_id and owner_id=uid for update;
 if not found then raise exception 'proposal not found'; end if;
 if rev is null or rev<>p.input_revision then raise exception 'stale plan'; end if;
 if p.result->>'status' is distinct from 'pass' or jsonb_typeof(p.result->'items') is distinct from 'array' then raise exception 'unchecked plan'; end if;
 if jsonb_array_length(p.result->'items')=0 then raise exception 'empty plan'; end if;
 select coalesce(max(version),0)+1 into next_version from public.plans where owner_id=uid;
 insert into public.plans(owner_id,version,input_revision,proposal_id,user_status,program_status,idempotency_key)
 values(uid,next_version,rev,p.id,'confirmed','pass',p_idempotency_key) returning id into ident;
 for item in select * from jsonb_array_elements(p.result->'items') loop
   insert into public.plan_items(owner_id,plan_id,start_at,end_at,payload) values(uid,ident,(item->>'start')::timestamptz,(item->>'end')::timestamptz,item);
 end loop;
 if exists(select 1 from public.plan_items a join public.plan_items b on a.plan_id=b.plan_id and a.id<b.id and a.start_at<b.end_at and b.start_at<a.end_at where a.plan_id=ident) then raise exception 'overlap'; end if;
 insert into public.audit_events(owner_id,event_type,object_id) values(uid,'plan_confirmed',ident);
 return ident;
end $$;
revoke all on function public.confirm_plan(uuid,uuid) from public;
grant execute on function public.confirm_plan(uuid,uuid) to authenticated;
'''
sql+='''create function public.export_my_data() returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare result jsonb:='{}'; tab text; rows jsonb;
begin
 if auth.uid() is null then raise exception 'unauthorized'; end if;
 foreach tab in array ARRAY['''+','.join("'"+x+"'" for x in USER_TABLES+['meal_log_items','plans','plan_items','rule_evaluations','audit_events'])+'''] loop
  execute format('select coalesce(jsonb_agg(to_jsonb(t)),''[]''::jsonb) from public.%I t where owner_id=$1',tab) into rows using auth.uid();
  result:=result||jsonb_build_object(tab,rows);
 end loop;
 return result;
end $$;
revoke all on function public.export_my_data() from public;
grant execute on function public.export_my_data() to authenticated;
create function public.delete_my_data(p_confirmation text) returns void language plpgsql security definer set search_path=public,pg_temp as $$
declare tab text;
begin
 if auth.uid() is null or p_confirmation<>'DELETE MY DATA' then raise exception 'confirmation required'; end if;
 set constraints all deferred;
 foreach tab in array ARRAY['''+','.join("'"+x+"'" for x in ['rule_evaluations','plan_items','plans','plan_proposals','meal_log_items']+list(reversed(USER_TABLES))+['audit_events','user_revisions'])+'''] loop
 execute format('delete from public.%I where owner_id=$1',tab) using auth.uid();
 end loop;
end $$;
revoke all on function public.delete_my_data(text) from public;
grant execute on function public.delete_my_data(text) to authenticated;
commit;
'''
(ROOT/'supabase/migrations/001_initial.sql').write_text(sql)
print('Wrote migration; no database connection made')
