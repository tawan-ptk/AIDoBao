"""Deterministic arithmetic only. Missing values never silently become zero."""
from decimal import Decimal
from services.schemas import Interval

def duration(start,end):
    i=Interval(start=start,end=end)
    return (i.end-i.start).total_seconds()/60

def convert_unit(value,source_unit,target_unit):
    factors={('lb','kg'):Decimal('0.45359237'),('in','cm'):Decimal('2.54'),('kg','g'):Decimal('1000'),('h','min'):Decimal('60')}
    v=Decimal(str(value))
    if not v.is_finite():raise ValueError('nonfinite value')
    if source_unit==target_unit:f=Decimal(1)
    elif (source_unit,target_unit) in factors:f=factors[source_unit,target_unit]
    elif (target_unit,source_unit) in factors:f=1/factors[target_unit,source_unit]
    else:raise ValueError('unsupported unit conversion; no inferred food portion')
    return {'value':float(v*f),'unit':target_unit,'original_value':str(v),'original_unit':source_unit,'factor':str(f),'formula':'original_value * factor','source':'exact international avoirdupois pound/inch and SI scale definitions'}

def recipe_portion(recipe,portion_grams,catalog):
    if not recipe.get('yield_grams') or not recipe.get('yield_source'):
        return {'status':'incomplete','missing':['measured cooking yield and source'],'totals':{}}
    # Ingredients must specify their own raw/cooked states; no invented retention factors.
    out=nutrient_totals(recipe['ingredients'],catalog)
    ratio=Decimal(str(portion_grams))/Decimal(str(recipe['yield_grams']))
    if not ratio.is_finite() or ratio<=0:raise ValueError('invalid recipe portion')
    return out|{'totals':{k:float(Decimal(str(v))*ratio) for k,v in out['totals'].items()},'recipe_formula':'sum ingredient nutrients * portion_grams / measured_yield_grams','yield_source':recipe['yield_source'],'limitation':'ingredient nutrient arithmetic; cooking retention not inferred'}

def nutrient_totals(items, catalog):
    totals={}; missing=[]; provenance=[]
    for item in items:
        f=catalog.get(item['food_id'])
        if not f:missing.append({'food_id':item['food_id'],'reason':'unknown_food'});continue
        if item.get('state')!=f['state']:missing.append({'food_id':item['food_id'],'reason':'raw_cooked_mismatch'});continue
        qty=Decimal(str(item['quantity']))
        if not qty.is_finite() or qty<=0:raise ValueError('ปริมาณต้องเป็นบวก')
        if item['unit']=='g':grams=qty
        else:
            p=f.get('portions',{}).get(item['unit'])
            if not p or not p.get('source'):missing.append({'food_id':item['food_id'],'reason':'unknown_portion'});continue
            grams=qty*Decimal(str(p['grams']))
        basis=Decimal(str(f['basis_grams']))
        if basis<=0:raise ValueError('invalid basis')
        for nutrient,value in f['nutrients'].items():
            if value is None:missing.append({'food_id':item['food_id'],'nutrient':nutrient});continue
            totals[nutrient]=totals.get(nutrient,Decimal(0))+Decimal(str(value))*grams/basis
        provenance.append({'food_id':item['food_id'],'source':f['source'],'formula':'nutrient_value * edible_grams / basis_grams','edible_grams':str(grams),'basis_grams':str(basis)})
    # Each nutrient needs values from all items, even when a key is absent entirely.
    for nutrient in totals:
        for item in items:
            if nutrient not in catalog.get(item['food_id'],{}).get('nutrients',{}):missing.append({'food_id':item['food_id'],'nutrient':nutrient})
    return {'status':'incomplete' if missing or not items else 'complete','totals':{k:float(v) for k,v in totals.items()},'missing':missing,'provenance':provenance,'note':'sugars remain a separate component; never added to carbohydrate'}

def allergen_check(food, allergies):
    if allergies is None or not food.get('ingredients_complete'):return 'unknown'
    if set(allergies)&set(food.get('allergens',[])):return 'fail'
    return 'pass' # Ingredient comparison only, never cross-contamination certification.

def summarize(records):
    groups={}; seen=set()
    for r in records:
        if r['id'] in seen:continue
        seen.add(r['id']);d=r['data'];kind=r['kind']
        if kind not in ('activity','sleep'):continue
        if not d.get('start') or not d.get('end') or not d.get('method'):continue
        key=(kind,d.get('method','unknown'))
        groups[key]=groups.get(key,0)+duration(d['start'],d['end'])
    return [{'domain':k[0],'method':k[1],'minutes':v} for k,v in groups.items()]

def comparable_measurements(records):
    groups={}
    for r in records:
        if r['kind']!='measurement':continue
        d=r['data'];key=tuple(d.get(k) for k in ('name','unit','context','method'))+(r['origin'],)
        if any(d.get(k) is None for k in ('name','value','unit','occurred_at','context','method')):continue
        groups.setdefault(key,[]).append({'value':d['value'],'occurred_at':d['occurred_at']})
    return [{'name':k[0],'unit':k[1],'context':k[2],'method':k[3],'origin':k[4],'observations':sorted(v,key=lambda x:x['occurred_at'])} for k,v in groups.items()]
