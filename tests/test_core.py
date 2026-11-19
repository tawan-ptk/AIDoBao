"""ALL data below are SOFTWARE TEST FIXTURES, never patients or training data."""
import copy, json
from datetime import date,timedelta
import pytest
from services.schemas import Record,inspect_record
from services.calculators import duration,nutrient_totals,allergen_check,summarize,comparable_measurements,convert_unit,recipe_portion
from services.scheduler import build_plan,diff_plans
from services.store import Store
from services.rag import Retriever
from services.rules import REGISTRY,health_rule_enabled
from services.importers import import_food_catalog,import_health_csv

PROFILE={'age':40,'timezone':'Asia/Bangkok','reported_type2':True,'goals':['SOFTWARE TEST ONLY']}
def routine(ident,domain,earliest='08:00',latest='10:00',minutes=15,fixed=False,dates=None):
    return {'id':ident,'source':'SOFTWARE TEST ONLY','data':{'domain':domain,'label':ident,'dates':dates or ['2026-10-12'],'earliest':earliest,'latest':latest,'duration_minutes':minutes,'fixed':fixed,'goal':'SOFTWARE TEST ONLY','instruction_source':'SOFTWARE TEST ONLY' if domain=='medication' else None}}
def constraint(start,end):return {'id':'locked','data':{'label':'SOFTWARE TEST ONLY','start':start,'end':end}}
def consent(store,owner='a'):return store.confirm_record(owner,{'kind':'consent','source':'SOFTWARE TEST ONLY','data':{'local_storage':True}},'consent')
def well(note='SOFTWARE TEST ONLY'):
    return {'kind':'wellbeing','data':{'note':note,'occurred_at':'2026-10-12T09:00:00+07:00'},'source':'SOFTWARE TEST ONLY'}

def test_overnight_and_nap_not_actual_sleep():
    r=Record(kind='sleep',source='SOFTWARE TEST ONLY',data={'start':'2026-10-12T23:00:00+07:00','end':'2026-10-13T07:00:00+07:00','method':'time_in_bed','episode':'main'})
    check=inspect_record(r);assert check['calculated']=={'interval_minutes':480,'label':'เวลาบนเตียง'}
    with pytest.raises(ValueError):duration('2026-10-12T23:00:00','2026-10-13T07:00:00')
    rows=[{'id':'1','kind':'sleep','data':r.data},{'id':'1','kind':'sleep','data':r.data},{'id':'2','kind':'sleep','data':r.data|{'method':'device_estimate'}}]
    assert [x['minutes'] for x in summarize(rows)]==[480,480]

def test_ambiguous_glucose_missing_and_wrong_units():
    d={'name':'glucose','value':120,'unit':None,'occurred_at':'2026-10-12T08:00:00+07:00','context':'unknown','method':'fingerstick'}
    c=inspect_record(Record(kind='measurement',source='SOFTWARE TEST ONLY',data=d));assert c['status']=='unknown' and 'unit' in c['missing']
    assert inspect_record(Record(kind='measurement',source='SOFTWARE TEST ONLY',data=d|{'unit':'kg'}))['status']=='fail'
    assert inspect_record(Record(kind='measurement',source='SOFTWARE TEST ONLY',data=d|{'value':float('nan')}))['status']=='fail'

def test_evidence_must_exist():
    with pytest.raises(ValueError):Record(kind='wellbeing',source='SOFTWARE TEST ONLY',text='abc',data={'note':'test'},evidence={'note':'invented'})

def test_exact_units_and_recipe_require_measured_yield():
    assert convert_unit(1,'lb','kg')['value']==0.45359237
    with pytest.raises(ValueError):convert_unit(1,'bowl','g')
    assert recipe_portion({},100,{})['status']=='incomplete'
    catalog={'fixture':{'state':'raw','basis_grams':100,'nutrients':{'carbohydrate_g':20},'source':'SOFTWARE TEST ONLY'}}
    recipe={'ingredients':[{'food_id':'fixture','state':'raw','quantity':100,'unit':'g'}],'yield_grams':200,'yield_source':'SOFTWARE TEST ONLY'}
    assert recipe_portion(recipe,50,catalog)['totals']['carbohydrate_g']==5

def test_overlapping_locked_commitments_are_infeasible():
    blocks=[constraint('2026-10-12T08:00:00+07:00','2026-10-12T10:00:00+07:00'),constraint('2026-10-12T09:00:00+07:00','2026-10-12T11:00:00+07:00')]
    assert build_plan(PROFILE,[routine('a','activity','12:00','13:00')],blocks,'2026-10-12',0)['status']=='infeasible'

def test_nutrients_portions_missing_and_no_double_count():
    catalog={'test':{'state':'cooked','basis_grams':100,'nutrients':{'carbohydrate_g':20,'sugars_g':5,'sodium_mg':None},'source':'SOFTWARE TEST ONLY','portions':{'bowl':{'grams':150,'source':'SOFTWARE TEST ONLY'}}}}
    out=nutrient_totals([{'food_id':'test','state':'cooked','quantity':2,'unit':'bowl'}],catalog)
    assert out['totals']['carbohydrate_g']==60 and out['totals']['sugars_g']==15 and out['status']=='incomplete'
    assert 'sodium_mg' not in out['totals']
    assert nutrient_totals([{'food_id':'test','state':'raw','quantity':1,'unit':'g'}],catalog)['status']=='incomplete'
    assert nutrient_totals([{'food_id':'test','state':'cooked','quantity':1,'unit':'ladle'}],catalog)['status']=='incomplete'
    assert allergen_check({'ingredients_complete':False},[])=='unknown'
    assert allergen_check({'ingredients_complete':True,'allergens':['test']},['test'])=='fail'

def test_seven_day_all_domains_and_replanning():
    dates=[str(date(2026,10,12)+timedelta(days=d)) for d in range(7)]
    rs=[routine('meal','meal','07:00','07:00',30,True,dates),routine('sleep','sleep','23:00','23:00',420,True,dates),routine('activity','activity','17:00','20:00',30,False,dates),routine('medicine','medication','06:30','06:30',5,True,dates),routine('measurement','measurement','06:40','06:40',5,True,dates),routine('wellbeing','wellbeing','20:30','21:00',10,False,dates),routine('appointment','appointment','10:00','10:00',30,True)]
    plan=build_plan(PROFILE,rs,[],'2026-10-12',1)
    assert plan['status']=='pass' and len(plan['items'])==43
    blocks=[constraint('2026-10-12T16:00:00+07:00','2026-10-12T18:00:00+07:00')]
    shifted=build_plan(PROFILE,rs,blocks,'2026-10-12',2)
    assert shifted['status']=='pass'
    diff=diff_plans(plan,shifted,'SOFTWARE TEST ONLY')
    assert len(diff['changes'])==1 and diff['changes'][0]['after']['start'].endswith('18:00:00+07:00')

def test_fixed_medication_cannot_move_and_unknown_relation():
    r=routine('medicine','medication','08:00','10:00',5,True)
    blocked=[constraint('2026-10-12T07:00:00+07:00','2026-10-12T09:00:00+07:00')]
    assert build_plan(PROFILE,[r],blocked,'2026-10-12',1)['status']=='infeasible'
    r['data']['meal_relation']='unknown'
    assert build_plan(PROFILE,[r],[],'2026-10-12',1)['status']=='unknown'

def test_backtracking_and_search_limit():
    # Both have equal choice count; first initially occupies the only usable slot of second.
    rs=[routine('a','activity','08:00','08:15',15),routine('b','meal','07:45','08:00',15)]
    blocked=[constraint('2026-10-12T07:45:00+07:00','2026-10-12T08:00:00+07:00')]
    p=build_plan(PROFILE,rs,blocked,'2026-10-12',0);assert p['status']=='pass'
    assert next(x for x in p['items'] if x['routine_id']=='a')['start'].endswith('08:15:00+07:00')
    assert build_plan(PROFILE,rs,blocked,'2026-10-12',0,max_nodes=1)['status']=='unknown'

def test_constraints_scope_and_mobility_not_ignored():
    assert build_plan(PROFILE|{'pregnant':True},[],[],'2026-10-12',0)['status']=='unknown'
    assert build_plan(PROFILE|{'mobility_limits':['SOFTWARE TEST ONLY']},[routine('a','activity')],[],'2026-10-12',0)['status']=='unknown'
    assert build_plan(PROFILE,[],[],'2026-10-12',0)['status']=='unknown'

def test_transaction_retry_owner_history_and_delete(tmp_path):
    s=Store(tmp_path/'test.sqlite');consent(s);r=well()
    a=s.confirm_record('a',r,'one');assert s.confirm_record('a',r,'one')==a
    with pytest.raises(ValueError):s.confirm_record('a',well('different'),'one')
    with pytest.raises(ValueError):s.confirm_record('a',r,'another')
    assert s.records('b')==[]
    consent(s,'b')
    with pytest.raises(ValueError):s.confirm_record('b',r|{'previous_id':a['id']},'evil')
    edited=s.confirm_record('a',well('correction')|{'previous_id':a['id']},'two');assert edited['version']==2
    assert len(s.records('a',current=False))==3 and len(s.records('a'))==2
    s.delete('a');assert s.records('a')==[] and len(s.records('b'))==1

def test_stale_plan_confirmation_atomic(tmp_path):
    s=Store(tmp_path/'test.sqlite');consent(s)
    p=build_plan(PROFILE,[routine('a','activity')],[],'2026-10-12',s.revision('a'))
    old=s.confirm_plan('a',p,'p');assert old==s.confirm_plan('a',p,'p')
    s.confirm_record('a',well(),'new')
    with pytest.raises(ValueError):s.confirm_plan('a',p,'p2')
    assert s.plans('a')[0]['requires_revalidation'] is True
    assert len(s.plans('a'))==1

def test_measurement_methods_never_silently_merged():
    a={'id':'1','kind':'measurement','origin':'measured','data':{'name':'glucose','unit':'mg/dL','value':100,'context':'fasting','method':'laboratory','occurred_at':'2026-10-12T07:00:00+07:00'}}
    b=copy.deepcopy(a);b['id']='2';b['data']['context']='after-meal'
    assert len(comparable_measurements([a,b]))==2

def test_retrieval_citation_is_stored_text_and_abstains():
    rag=Retriever();r=rag.answer('อาหาร เวลา ยา')
    assert r['citations'] and all(x['text'] in [c['text'] for c in rag.chunks] for x in r['citations'])
    assert rag.answer('quantum cryptography')['status']=='unknown'
    assert not any(health_rule_enabled(r) for r in REGISTRY)

def test_import_rights_missing_codes_duplicate_ids(tmp_path):
    path=tmp_path/'software-fixture.csv';path.write_text('id,w\na,999\n')
    mapping={'weight':{'source_column':'w','unit':'kg','method':'self_report','missing_codes':['999']}}
    rows=import_health_csv(path,'SOFTWARE_TEST_ONLY','id',mapping,{'process':True})
    assert rows[0]['values']['weight']['value'] is None
    path.write_text('id,w\na,1\na,2\n')
    with pytest.raises(ValueError):import_health_csv(path,'SOFTWARE_TEST_ONLY','id',mapping,{'process':True})
    with pytest.raises(ValueError):import_food_catalog(path,{'process':False})
