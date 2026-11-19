"""Deterministic reference energy estimates, distinct from measured intake.

All serving conversions come from the catalog. Estimates are derived on read so
editing/deleting a meal cannot leave an old calorie value in a daily total.
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from services.food_reference import food_reference
from services.food_portions import unit_name

ZONE=ZoneInfo('Asia/Bangkok')

def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal('.1'),rounding=ROUND_HALF_UP))

def estimate_meal(record,*,component=False):
    from services.journal import short_label,split_meal_span,components_from_spans
    name=short_label(record)
    data=record.get('data',{})
    components=data.get('components')
    if components is None and not component:
        spans=split_meal_span(data.get('name') or record.get('text',''))
        if spans:
            if data.get('quantity') is not None or data.get('unit'):
                return {'name':name,'status':'ambiguous_quantity','kcal':None,'actual_consumed_kcal':None,
                        'assumed_portion':False,'reference':{},'note':'กรุณาระบุปริมาณของข้าวและกับข้าวแยกกัน เช่น ข้าว 2 ทัพพี กับต้มพะโล้ 1 ถ้วย'}
            components=components_from_spans(spans)
    if components is not None:
        if data.get('quantity') is not None or data.get('unit'):
            return {'name':name,'status':'ambiguous_quantity','kcal':None,'actual_consumed_kcal':None,
                    'assumed_portion':False,'reference':{},'note':'กรุณาระบุปริมาณแยกสำหรับอาหารแต่ละอย่างในมื้อ'}
        from services.schemas import MealComponent
        try:
            if not isinstance(components,list) or not 2<=len(components)<=30:raise ValueError()
            validated=[MealComponent.model_validate(p).model_dump() for p in components]
        except (ValueError,TypeError):
            return {'name':name,'status':'invalid_components','kcal':None,'actual_consumed_kcal':None,
                    'assumed_portion':False,'reference':{},'note':'กรุณาตรวจชื่อ ปริมาณ และหน่วยของอาหารแต่ละอย่างในมื้อ'}
        estimates=[estimate_meal({'kind':'meal','data':p},component=True) for p in validated]
        known=[e for e in estimates if e['kcal'] is not None]
        total=[rounded(sum(Decimal(str(e['kcal'][j])) for e in known)) for j in (0,1)] if known else None
        return {'name':name,'status':'estimated' if len(known)==len(estimates) else 'partial' if known else 'unknown_food',
                'kcal':total,'actual_consumed_kcal':None,'components':estimates,
                'references':[e['reference'] for e in known], 'reference':{},
                'quantity':None,'unit':None,'unknown_component_count':len(estimates)-len(known),
                'catalog_version':'2026-10-12-v2','assumed_portion':any(e['assumed_portion'] for e in estimates),
                'assumption':' · '.join(e['name']+': '+e['assumption'] for e in estimates if e.get('assumption')) or None,
                'note':'รวมข้าวและกับข้าวเป็นมื้อเดียว คิดจากปริมาณแยกแต่ละอย่าง สูตรและขนาดเสิร์ฟจริงอาจต่างกัน'+
                       ('; ยังไม่รวม '+str(len(estimates)-len(known))+' อย่างที่ประเมินไม่ได้' if len(known)<len(estimates) else '')}
    ref=food_reference(name)
    base={'name':name,'status':'unknown_food','kcal':None,'actual_consumed_kcal':None,
          'catalog_version':'2026-10-12-v2',
          'assumed_portion':False,'note':ref['note'],'reference':ref,
          'quantity':record.get('data',{}).get('quantity'),'unit':record.get('data',{}).get('unit')}
    if not ref.get('kcal'):return base
    serving=ref.get('serving')
    if not serving:return base|{'status':'unknown_serving','note':'มีค่าพลังงานสูตรอ้างอิง แต่ยังไม่มีหน่วยเสิร์ฟที่ใช้รวมยอดได้'}
    d=record['data'];q=d.get('quantity');unit=unit_name(d.get('unit'))
    if d.get('food_state')=='raw':
        return base|{'status':'food_state_mismatch','note':'รายการอ้างอิงนี้เป็นอาหารพร้อมกิน จึงไม่ใช้กับน้ำหนักอาหารดิบ'}
    assumed=q is None and not unit
    if assumed:q=serving['quantity'];unit=serving['unit']
    elif q is None:return base|{'status':'missing_quantity','note':'บอกปริมาณเพิ่ม เช่น 1 จาน หรือครึ่งจาน เพื่อรวมแคลอรีครับ'}
    elif not unit:return base|{'status':'missing_unit','note':'มีปริมาณแต่ยังไม่ทราบหน่วย จึงยังรวมแคลอรีไม่ได้'}
    try:
        if isinstance(q,bool) or not isinstance(q,(int,float)):raise ValueError()
        quantity=Decimal(str(q))
        if not quantity.is_finite() or quantity<=0:raise ValueError()
    except (ValueError,ArithmeticError):return base|{'status':'invalid_quantity','note':'ปริมาณต้องเป็นตัวเลขบวก'}
    if unit==serving['unit']:factor=Decimal(1)
    elif unit in serving['unit_factors']:factor=Decimal(str(serving['unit_factors'][unit]))
    else:return base|{'status':'unknown_unit','note':'ยังแปลงหน่วย '+unit+' เป็น '+serving['unit']+' จากแหล่งอ้างอิงไม่ได้ กรุณาเลือกหน่วยอ้างอิงหรือใช้ฉลากจริง'}
    ratio=quantity*factor/Decimal(str(serving['quantity']))
    kcal=[rounded(Decimal(str(v))*ratio) for v in ref['kcal']]
    return base|{'status':'estimated','kcal':kcal,'quantity':float(quantity),'unit':unit,
                 'assumed_portion':assumed,'formula':'reference_kcal * quantity * unit_factor / reference_quantity',
                 'unit_factor':float(factor),'note':ref['note'],
                 'assumption':('ยังไม่ระบุปริมาณ ใช้ '+f'{q:g}'+' '+unit+' อ้างอิง แก้ได้' if assumed else None)}

def meal_date(record):
    if record.get('journal'):return str(record['journal']['date'])
    stamp=record.get('data',{}).get('occurred_at')
    if not stamp:return None
    try:
        dt=datetime.fromisoformat(stamp)
        return dt.astimezone(ZONE).date().isoformat() if dt.tzinfo else None
    except (ValueError,TypeError):return None

def daily_energy(records,day):
    day=str(day);items=[];undated=0
    for r in records:
        if r['kind']!='meal':continue
        observed=meal_date(r)
        if not observed:undated+=1
        if observed!=day:continue
        e=estimate_meal(r)
        items.append(e|{'record_id':r.get('id'),'period':(r.get('journal') or {}).get('period','unspecified')})
    known=[i for i in items if i['kcal'] is not None]
    complete=[i for i in items if i['status']=='estimated']
    total=[rounded(sum(Decimal(str(i['kcal'][j])) for i in known)) for j in (0,1)] if known else None
    return {'date':day,'status':'empty' if not items else 'estimated' if len(complete)==len(items) else 'partial' if known else 'unknown',
            'kcal':total,'items':items,'estimated_count':len(complete),'meal_count':len(items),
            'unknown_count':len(items)-len(complete),'assumed_portion_count':sum(i['assumed_portion'] for i in known),
            'undated_meal_count':undated,'actual_consumed_kcal':None,
            'catalog_version':'2026-10-12-v2',
            'note':'รวมเฉพาะอาหารที่บันทึกในวันที่เลือกและประเมินได้ ไม่ใช่พลังงานที่วัดจริง สูตรและขนาดเสิร์ฟอาจต่างกัน',
            'daily_target_kcal':None}

def calorie_text(estimate):
    if estimate.get('kcal') is None:return 'ยังประเมินแคลอรีไม่ได้ · '+estimate['note']
    low,high=estimate['kcal']
    amount=f'{low:g}'+('–'+f'{high:g}' if low!=high else '')
    return 'ประมาณ '+amount+' kcal · '+('รวมในมื้อนี้'+(' (ยังไม่ครบ)' if estimate.get('status')=='partial' else '') if estimate.get('components') else f'{estimate["quantity"]:g} {estimate["unit"]}')
