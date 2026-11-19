"""Explicit source-specific import contracts; no auto-matching people or nutrients."""
import csv, hashlib, json, math, pathlib

def import_food_catalog(path,rights):
    if rights.get('process') is not True or rights.get('local_catalog') is not True:raise ValueError('food rights pending')
    rows=json.loads(pathlib.Path(path).read_text());out={}
    for f in rows:
        required={'food_id','name','state','basis_grams','nutrients','source','source_record_id','source_revision','ingredients_complete'}
        if required-set(f):raise ValueError('missing food provenance/basis fields')
        if f['food_id'] in out:raise ValueError('duplicate food ID')
        if f['state'] not in ('raw','cooked','packaged'):raise ValueError('unknown food state')
        if not isinstance(f['basis_grams'],(float,int)) or not math.isfinite(f['basis_grams']) or f['basis_grams']<=0:raise ValueError('invalid basis')
        for nutrient,v in f['nutrients'].items():
            if v is not None and (isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0):raise ValueError('invalid nutrient value')
        for unit,p in f.get('portions',{}).items():
            if not p.get('source') or p.get('grams',0)<=0:raise ValueError('portion conversion needs source and grams')
        out[f['food_id']]=f
    return out

def import_activity_catalog(path):
    rows=json.loads(pathlib.Path(path).read_text());seen=set()
    for r in rows:
        for k in ('activity_id','name','type','source_url','source_location','review_status'):
            if not r.get(k):raise ValueError('missing activity source')
        if r['activity_id'] in seen:raise ValueError('duplicate activity')
        seen.add(r['activity_id'])
        if r.get('review_status')!='reviewed' and r.get('recommendation_enabled'):raise ValueError('unreviewed activity cannot prescribe')
    return rows

def import_health_csv(path,source_dataset,subject_column,mapping,rights):
    """mapping: output field -> source_column, unit, method, missing_codes.
    No rows written to user records and no examples written to training.
    """
    if not rights.get('process'):raise ValueError('processing rights pending')
    path=pathlib.Path(path);sha=hashlib.sha256(path.read_bytes()).hexdigest();out=[];seen=set()
    with path.open(newline='') as f:
        for line,r in enumerate(csv.DictReader(f),2):
            sid=r[subject_column]
            if not sid:raise ValueError('missing subject ID')
            if sid in seen:raise ValueError('person-level input has duplicate ID; define repeated-observation key explicitly')
            seen.add(sid);values={}
            for target,spec in mapping.items():
                raw=r[spec['source_column']]
                values[target]={'value':None if raw in spec.get('missing_codes',['']) else raw,'raw_value':raw,'unit':spec['unit'],'method':spec['method'],'source_column':spec['source_column']}
            out.append({'source_dataset':source_dataset,'source_subject_id':sid,'values':values,'provenance':{'file':path.name,'sha256':sha,'row':line}})
    return out
