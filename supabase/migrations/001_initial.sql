-- Local prototype migration; execute in a disposable Supabase project only after review.
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
create table public.user_profiles(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.user_profiles(owner_id,id) deferrable initially deferred);
 alter table public.user_profiles enable row level security;
 create policy owner_read on public.user_profiles for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.user_profiles for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index user_profiles_page on public.user_profiles(owner_id,created_at,id);
 create trigger user_profiles_revision after insert on public.user_profiles for each row execute function public.bump_input_revision();
create table public.user_consents(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.user_consents(owner_id,id) deferrable initially deferred);
 alter table public.user_consents enable row level security;
 create policy owner_read on public.user_consents for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.user_consents for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index user_consents_page on public.user_consents(owner_id,created_at,id);
 create trigger user_consents_revision after insert on public.user_consents for each row execute function public.bump_input_revision();
create table public.user_constraints(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.user_constraints(owner_id,id) deferrable initially deferred);
 alter table public.user_constraints enable row level security;
 create policy owner_read on public.user_constraints for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.user_constraints for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index user_constraints_page on public.user_constraints(owner_id,created_at,id);
 create trigger user_constraints_revision after insert on public.user_constraints for each row execute function public.bump_input_revision();
create table public.clinician_targets(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.clinician_targets(owner_id,id) deferrable initially deferred);
 alter table public.clinician_targets enable row level security;
 create policy owner_read on public.clinician_targets for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.clinician_targets for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index clinician_targets_page on public.clinician_targets(owner_id,created_at,id);
 create trigger clinician_targets_revision after insert on public.clinician_targets for each row execute function public.bump_input_revision();
create table public.health_measurements(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.health_measurements(owner_id,id) deferrable initially deferred);
 alter table public.health_measurements enable row level security;
 create policy owner_read on public.health_measurements for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.health_measurements for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index health_measurements_page on public.health_measurements(owner_id,created_at,id);
 create trigger health_measurements_revision after insert on public.health_measurements for each row execute function public.bump_input_revision();
create table public.medication_schedules(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.medication_schedules(owner_id,id) deferrable initially deferred);
 alter table public.medication_schedules enable row level security;
 create policy owner_read on public.medication_schedules for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.medication_schedules for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index medication_schedules_page on public.medication_schedules(owner_id,created_at,id);
 create trigger medication_schedules_revision after insert on public.medication_schedules for each row execute function public.bump_input_revision();
create table public.medication_logs(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.medication_logs(owner_id,id) deferrable initially deferred);
 alter table public.medication_logs enable row level security;
 create policy owner_read on public.medication_logs for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.medication_logs for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index medication_logs_page on public.medication_logs(owner_id,created_at,id);
 create trigger medication_logs_revision after insert on public.medication_logs for each row execute function public.bump_input_revision();
create table public.appointments(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.appointments(owner_id,id) deferrable initially deferred);
 alter table public.appointments enable row level security;
 create policy owner_read on public.appointments for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.appointments for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index appointments_page on public.appointments(owner_id,created_at,id);
 create trigger appointments_revision after insert on public.appointments for each row execute function public.bump_input_revision();
create table public.meal_logs(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.meal_logs(owner_id,id) deferrable initially deferred);
 alter table public.meal_logs enable row level security;
 create policy owner_read on public.meal_logs for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.meal_logs for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index meal_logs_page on public.meal_logs(owner_id,created_at,id);
 create trigger meal_logs_revision after insert on public.meal_logs for each row execute function public.bump_input_revision();
create table public.activity_logs(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.activity_logs(owner_id,id) deferrable initially deferred);
 alter table public.activity_logs enable row level security;
 create policy owner_read on public.activity_logs for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.activity_logs for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index activity_logs_page on public.activity_logs(owner_id,created_at,id);
 create trigger activity_logs_revision after insert on public.activity_logs for each row execute function public.bump_input_revision();
create table public.sleep_logs(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.sleep_logs(owner_id,id) deferrable initially deferred);
 alter table public.sleep_logs enable row level security;
 create policy owner_read on public.sleep_logs for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.sleep_logs for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index sleep_logs_page on public.sleep_logs(owner_id,created_at,id);
 create trigger sleep_logs_revision after insert on public.sleep_logs for each row execute function public.bump_input_revision();
create table public.wellbeing_logs(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.wellbeing_logs(owner_id,id) deferrable initially deferred);
 alter table public.wellbeing_logs enable row level security;
 create policy owner_read on public.wellbeing_logs for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.wellbeing_logs for insert to authenticated with check(owner_id=auth.uid() and (program_status='pass' or (program_status='unknown' and jsonb_typeof(payload->'_journal')='object' and length(payload->>'_text')>0)) and clinician_review='not_reviewed');
 create index wellbeing_logs_page on public.wellbeing_logs(owner_id,created_at,id);
 create trigger wellbeing_logs_revision after insert on public.wellbeing_logs for each row execute function public.bump_input_revision();
create table public.plan_feedback(
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 payload jsonb not null check(jsonb_typeof(payload)='object'), origin text not null check(origin in ('self_report','measured','device_estimate','calculated','clinician_document','model_proposal')),
 provenance jsonb not null, version integer not null default 1 check(version>0), previous_id uuid,
 program_status text not null check(program_status in ('pass','fail','unknown','not_applicable')),
 user_status text not null default 'confirmed' check(user_status='confirmed'),
 clinician_review text not null default 'not_reviewed' check(clinician_review='not_reviewed'),
 idempotency_key uuid not null, created_at timestamptz not null default now(),
 unique(owner_id,id),unique(owner_id,idempotency_key),unique(previous_id),
 foreign key(owner_id,previous_id) references public.plan_feedback(owner_id,id) deferrable initially deferred);
 alter table public.plan_feedback enable row level security;
 create policy owner_read on public.plan_feedback for select to authenticated using(owner_id=auth.uid());
 create policy owner_insert on public.plan_feedback for insert to authenticated with check(owner_id=auth.uid() and program_status='pass' and clinician_review='not_reviewed');
 create index plan_feedback_page on public.plan_feedback(owner_id,created_at,id);
 create trigger plan_feedback_revision after insert on public.plan_feedback for each row execute function public.bump_input_revision();

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
alter table public.meal_log_items enable row level security;
create policy owner_read on public.meal_log_items for select to authenticated using(owner_id=auth.uid());
alter table public.plans enable row level security;
create policy owner_read on public.plans for select to authenticated using(owner_id=auth.uid());
alter table public.plan_items enable row level security;
create policy owner_read on public.plan_items for select to authenticated using(owner_id=auth.uid());
alter table public.rule_evaluations enable row level security;
create policy owner_read on public.rule_evaluations for select to authenticated using(owner_id=auth.uid());
alter table public.audit_events enable row level security;
create policy owner_read on public.audit_events for select to authenticated using(owner_id=auth.uid());
alter table public.source_documents enable row level security;
create policy catalog_read on public.source_documents for select to authenticated using(true);
alter table public.source_chunks enable row level security;
create policy catalog_read on public.source_chunks for select to authenticated using(true);
alter table public.rules enable row level security;
create policy catalog_read on public.rules for select to authenticated using(true);
alter table public.foods enable row level security;
create policy catalog_read on public.foods for select to authenticated using(true);
alter table public.food_nutrients enable row level security;
create policy catalog_read on public.food_nutrients for select to authenticated using(true);
alter table public.portions enable row level security;
create policy catalog_read on public.portions for select to authenticated using(true);
alter table public.food_source_mappings enable row level security;
create policy catalog_read on public.food_source_mappings for select to authenticated using(true);
alter table public.recipes enable row level security;
create policy catalog_read on public.recipes for select to authenticated using(true);
alter table public.recipe_ingredients enable row level security;
create policy catalog_read on public.recipe_ingredients for select to authenticated using(true);
alter table public.activity_catalog enable row level security;
create policy catalog_read on public.activity_catalog for select to authenticated using(true);

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
create function public.export_my_data() returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare result jsonb:='{}'; tab text; rows jsonb;
begin
 if auth.uid() is null then raise exception 'unauthorized'; end if;
 foreach tab in array ARRAY['user_profiles','user_consents','user_constraints','clinician_targets','health_measurements','medication_schedules','medication_logs','appointments','meal_logs','activity_logs','sleep_logs','wellbeing_logs','plan_feedback','meal_log_items','plans','plan_items','rule_evaluations','audit_events'] loop
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
 foreach tab in array ARRAY['rule_evaluations','plan_items','plans','plan_proposals','meal_log_items','plan_feedback','wellbeing_logs','sleep_logs','activity_logs','meal_logs','appointments','medication_logs','medication_schedules','health_measurements','clinician_targets','user_constraints','user_consents','user_profiles','audit_events','user_revisions'] loop
 execute format('delete from public.%I where owner_id=$1',tab) using auth.uid();
 end loop;
end $$;
revoke all on function public.delete_my_data(text) from public;
grant execute on function public.delete_my_data(text) to authenticated;
commit;
