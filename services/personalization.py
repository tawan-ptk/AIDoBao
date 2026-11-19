"""Confirmed context only. Body size is not a diagnosis or a calorie prescription."""
import re
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from services.schemas import Profile

ZONE=ZoneInfo('Asia/Bangkok')

def positive_mention(text,pattern):
    """Match explicit care terms, excluding a directly negated report.

    In particular, ไตรกลีเซอไรด์ is not a kidney condition. This is a
    conservative text flag, not a diagnosis or an override of confirmed data.
    """
    for match in re.finditer(pattern,text,re.I):
        prefix=text[max(0,match.start()-24):match.start()]
        if not re.search(r'(?:ไม่(?:ได้|เคย)?(?:เป็น|มี|ต้อง)?|ไม่มี|ปฏิเสธ)(?:ว่า|ภาวะ|ประวัติ|การ)?\s*$',prefix):return True
    return False

KIDNEY_TERMS=r'โรคไต|ไต(?:เรื้อรัง|วาย|เสื่อม|อักเสบ)|ฟอกไต|ล้างไต|ปลูกถ่ายไต|\b(?:ckd|kidney disease|kidney failure|dialysis)\b|^ไต$'
NUTRITION_TERMS=r'กลืนลำบาก|กลืนไม่ได้|ภาวะการกลืน|dysphagia|สายให้อาหาร|eating disorder|โรคการกินผิดปกติ'

def personal_context(records):
    profiles=[r for r in records if r['kind']=='profile']
    latest=max(profiles,key=lambda r:r.get('created_at',''),default=None)
    p=Profile.model_validate(latest['data'] if latest else {}).model_dump(mode='json')
    sources={k:latest['id'] for k in ('age','weight_kg','height_cm','allergies','conditions','medications','pregnant','complex_care') if latest and p.get(k) is not None}
    # Measurement time, not edit time, determines the latest observation.
    for name,key,unit in [('weight','weight_kg','kg'),('height','height_cm','cm')]:
        options=[]
        for r in records:
            d=r['data']
            if r['kind']!='measurement' or d.get('name')!=name or d.get('unit')!=unit:continue
            stamp=d.get('occurred_at') or (r.get('journal') or {}).get('date')
            if not stamp or not isinstance(d.get('value'),(int,float)) or isinstance(d['value'],bool) or d['value']<=0:continue
            observed=datetime.fromisoformat(stamp)
            if observed.tzinfo is None:observed=observed.replace(tzinfo=ZONE)
            options.append((observed.timestamp(),r))
        if options:
            _,row=max(options,key=lambda x:(x[0],x[1].get('created_at','')))
            observed=row['data'].get('occurred_at') or row['journal']['date']
            observation=datetime.fromisoformat(observed)
            if observation.tzinfo is None:observation=observation.replace(tzinfo=ZONE)
            stamp=(latest or {}).get('created_at')
            cutoff=datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc) if stamp and datetime.fromisoformat(stamp).tzinfo is None else datetime.fromisoformat(stamp) if stamp else None
            if p.get(key) is None or cutoff is None or observation>=cutoff:
                p[key]=row['data']['value'];sources[key]=row['id']
    flags=[]
    if p['age'] is None:flags.append('age_unknown')
    elif p['age']<18:flags.append('child')
    if p['pregnant']:flags.append('pregnancy')
    if p['complex_care']:flags.append('complex_care')
    if any(positive_mention(c,KIDNEY_TERMS) for c in p['conditions']):flags.append('kidney_care')
    if any(positive_mention(c,NUTRITION_TERMS) for c in p['conditions']):flags.append('special_nutrition')
    bmi=None
    if p['age'] is not None and p['age']>=18 and not p['pregnant'] and p['weight_kg'] and p['height_cm'] and 1<=p['weight_kg']<=500 and 30<=p['height_cm']<=260:
        bmi=round(p['weight_kg']/(p['height_cm']/100)**2,1)
    return {'profile':p,'source_record_ids':sources,'flags':flags,'bmi':bmi,'bmi_label':'BMI ผู้ใหญ่ คำนวณจากข้อมูลที่บันทึก ไม่ใช่การวินิจฉัย' if bmi else None,'daily_calorie_target':None,'clinical_review':'not_reviewed'}

def meals_on(records,day):
    out=[]
    for r in records:
        if r['kind']!='meal':continue
        j=r.get('journal') or {};stamp=r['data'].get('occurred_at')
        actual=j.get('date')
        if not actual and stamp:actual=datetime.fromisoformat(stamp).astimezone(ZONE).date().isoformat()
        if actual==str(day):out.append(r)
    return out
