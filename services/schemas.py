from datetime import datetime, date, time
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator

DOMAINS = ('meal','activity','sleep','medication','appointment','measurement','wellbeing')
Origin = Literal['self_report','measured','device_estimate','calculated','clinician_document','model_proposal']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class MealComponent(Strict):
    name: str = Field(min_length=1,max_length=120)
    quantity: float | None = Field(default=None,gt=0,le=100000)
    unit: str | None = Field(default=None,max_length=40)
    food_state: Literal['raw','cooked','packaged','unknown'] | None = None

    @model_validator(mode='before')
    @classmethod
    def literal_quantity(cls,value):
        if isinstance(value,dict) and value.get('quantity') is not None:
            q=value['quantity']
            if isinstance(q,bool) or not isinstance(q,(int,float)):
                raise ValueError('ปริมาณอาหารต้องเป็นตัวเลข')
        return value

class JournalTime(Strict):
    date: date
    timezone: Literal['Asia/Bangkok'] = 'Asia/Bangkok'
    period: Literal['unspecified','morning','noon','afternoon','evening','night'] = 'unspecified'
    clock: time | None = None
    clock_source: Literal['unspecified','explicit','capture_time','user_edited'] = 'unspecified'
    date_source: Literal['capture_date','explicit','user_edited'] = 'capture_date'
    captured_at: datetime
    context_text: str = Field(default='',max_length=4000)
    @model_validator(mode='after')
    def aware(self):
        if self.captured_at.tzinfo is None:raise ValueError('capture timestamp requires timezone')
        if self.clock and self.clock.tzinfo:raise ValueError('clock uses Asia/Bangkok')
        return self

class Record(Strict):
    kind: Literal['profile','consent','constraint','routine','feedback','meal','activity','sleep','medication','appointment','measurement','wellbeing']
    text: str = Field(default='',max_length=8000)
    data: dict
    origin: Origin = 'self_report'
    source: str = Field(min_length=1,max_length=1000)
    # Substrings support extracted fields; values remain unconfirmed proposals.
    evidence: dict[str,str] = Field(default_factory=dict)
    previous_id: str | None = None
    journal: JournalTime | None = None

    @model_validator(mode='after')
    def valid_evidence(self):
        if self.journal and (self.kind not in DOMAINS or not self.text.strip()):
            raise ValueError('บันทึกแบบเล่าต้องมีข้อความต้นฉบับและหมวดกิจวัตร')
        for field, span in self.evidence.items():
            if field not in self.data or not span or span not in self.text:
                raise ValueError('หลักฐานต้องเป็นข้อความที่พบจริงและอ้างถึงช่องข้อมูลที่มีอยู่')
        return self

class Profile(Strict):
    age: int | None = Field(default=None,ge=1,le=120)
    weight_kg: float | None = Field(default=None,gt=0,le=500)
    height_cm: float | None = Field(default=None,gt=0,le=260)
    conditions: list[str] = Field(default_factory=list,max_length=30)
    medications: list[str] = Field(default_factory=list,max_length=30)
    timezone: str = 'Asia/Bangkok'
    reported_type2: bool | None = None
    complex_care: bool = False
    pregnant: bool = False
    goals: list[str] = Field(default_factory=list)
    allergies: list[str] | None = None
    preferences: list[str] = Field(default_factory=list)
    mobility_limits: list[str] = Field(default_factory=list)
    prohibited_catalog_ids: list[str] = Field(default_factory=list)
    @model_validator(mode='after')
    def zone(self):
        ZoneInfo(self.timezone)
        return self

class Interval(Strict):
    start: datetime
    end: datetime
    @model_validator(mode='after')
    def times(self):
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end <= self.start:
            raise ValueError('ต้องระบุวันเวลาและเขตเวลา โดยเวลาสิ้นสุดอยู่หลังเวลาเริ่ม')
        return self

class Constraint(Interval):
    label: str = Field(min_length=1)

class Routine(Strict):
    domain: Literal['meal','activity','sleep','medication','appointment','measurement','wellbeing']
    label: str = Field(min_length=1,max_length=300)
    dates: list[date] = Field(min_length=1,max_length=7)
    earliest: time
    latest: time
    duration_minutes: int = Field(gt=0,le=1440)
    fixed: bool = False
    catalog_id: str | None = None
    goal: str = Field(min_length=1)
    instruction_source: str | None = None
    # An explicit relation, never inferred from a drug name.
    meal_relation: Literal['none','before','after','with','unknown'] = 'none'
    related_routine_id: str | None = None
    relation_minutes: int | None = Field(default=None,ge=0,le=240)
    @model_validator(mode='after')
    def locked(self):
        if len(set(self.dates)) != len(self.dates): raise ValueError('วันที่ซ้ำ')
        if self.domain in ('medication','appointment') and not self.fixed:
            raise ValueError('ยาและนัดหมายต้องล็อกเวลา')
        if self.domain=='medication' and not self.instruction_source:
            raise ValueError('ต้องระบุแหล่งคำสั่งใช้ยา')
        return self

UNITS = {'weight':{'kg'},'height':{'cm'},'waist':{'cm'},'glucose':{'mg/dL','mmol/L'},'hba1c':{'%','mmol/mol'},'systolic':{'mmHg'},'diastolic':{'mmHg'}}

def inspect_record(record: Record) -> dict:
    d=record.data; missing=[]; errors=[]; calculated={}
    required = {
        'meal':['name','quantity','unit','occurred_at','food_state'],
        'activity':['name','start','end','method'],
        'sleep':['start','end','method','episode'],
        'medication':['name','dose','unit','occurred_at','instruction_source','state'],
        'appointment':['name','start','end'],
        'measurement':['name','value','unit','occurred_at','context','method'],
        'wellbeing':['note','occurred_at'],
        'feedback':['plan_id','reason','occurred_at'],
        'consent':['local_storage'],
    }
    missing=[k for k in required.get(record.kind,[]) if d.get(k) is None or d.get(k)=='']
    allowed={
        'meal':{'name','quantity','unit','occurred_at','food_state','food_id','components'},
        'activity':{'name','start','end','method','intensity','catalog_id'},
        'sleep':{'start','end','method','episode','quality'},
        'medication':{'name','dose','unit','occurred_at','instruction_source','state'},
        'appointment':{'name','start','end','location'},
        'measurement':{'name','value','unit','occurred_at','context','method'},
        'wellbeing':{'note','occurred_at'},'feedback':{'plan_id','reason','occurred_at'},'consent':{'local_storage'},
    }
    if record.kind in allowed and set(d)-allowed[record.kind]:errors.append('มีช่องข้อมูลที่ไม่รองรับ')
    try:
        if record.kind=='meal' and 'components' in d:
            parts=d['components']
            if not isinstance(parts,list) or not 2<=len(parts)<=30:
                raise ValueError('อาหารในมื้อต้องมี 2–30 รายการ')
            for part in parts:MealComponent.model_validate(part)
            missing=[k for k in missing if k not in ('quantity','unit')]
            for part in parts:
                if part.get('quantity') is None:missing.append('ปริมาณ '+part['name'])
                if not part.get('unit'):missing.append('หน่วย '+part['name'])
            if d.get('quantity') is not None or d.get('unit'):
                raise ValueError('กรุณาระบุปริมาณแยกสำหรับอาหารแต่ละอย่างในมื้อ')
        if record.kind=='profile':Profile.model_validate(d)
        if record.kind=='constraint':Constraint.model_validate(d)
        if record.kind=='routine':Routine.model_validate(d)
        if 'start' in d and 'end' in d and d['start'] and d['end']:
            interval=Interval(start=d['start'],end=d['end'])
            minutes=(interval.end-interval.start).total_seconds()/60
            calculated['interval_minutes']=minutes
            if record.kind=='sleep':calculated['label']='เวลาบนเตียง' if d.get('method')=='time_in_bed' else 'ช่วงการนอนตามวิธีที่ระบุ'
        if d.get('occurred_at'):
            dt=datetime.fromisoformat(d['occurred_at'])
            if not dt.tzinfo:errors.append('วันเวลาต้องมีเขตเวลา')
        for field in ('start','end'):
            if d.get(field) and datetime.fromisoformat(d[field]).tzinfo is None:errors.append('วันเวลาต้องมีเขตเวลา')
        if record.journal:
            j=record.journal
            field='start' if record.kind in ('activity','sleep','appointment') else 'occurred_at'
            if d.get(field):
                dt=datetime.fromisoformat(d[field]).astimezone(ZoneInfo(j.timezone))
                if dt.date()!=j.date or (j.clock and dt.time().replace(second=0,microsecond=0)!=j.clock.replace(second=0,microsecond=0)):
                    errors.append('วันที่และเวลาของบันทึกต้องตรงกับวันที่และเวลาที่เลือก')
        for k in ('value','quantity','dose'):
            if d.get(k) is not None:
                import math
                if isinstance(d[k],bool) or not isinstance(d[k],(int,float)) or not math.isfinite(d[k]) or d[k]<=0:errors.append(f'{k}: ต้องเป็นตัวเลขบวกที่จำกัด')
        if record.kind=='measurement' and d.get('name'):
            if d['name'] not in UNITS:errors.append('ชนิดค่าตรวจยังไม่รองรับ')
            elif d.get('unit') and d['unit'] not in UNITS[d['name']]:errors.append('หน่วยไม่ตรงชนิดค่าตรวจ')
            if d.get('context')=='unknown':missing.append('context')
        if record.kind=='sleep' and d.get('method') not in ('time_in_bed','self_report_sleep','device_estimate') and not (record.journal and d.get('method') is None):errors.append('ต้องแยกเวลาบนเตียง/รายงานการหลับ/อุปกรณ์')
        if record.kind=='sleep' and d.get('episode') not in ('main','nap') and not (record.journal and d.get('episode') is None):errors.append('ต้องระบุการนอนหลักหรืองีบ')
        if record.kind=='activity' and d.get('method') not in ('self_report','device_estimate','measured') and not (record.journal and d.get('method') is None):errors.append('ต้องระบุวิธีวัดกิจกรรม')
        if record.kind=='medication' and d.get('state') not in ('reported_taken','reminder_due','acknowledged','unknown') and not (record.journal and d.get('state') is None):errors.append('สถานะยาไม่ถูกต้อง')
        if record.kind=='meal' and d.get('food_state') not in ('raw','cooked','packaged','unknown') and not (record.journal and d.get('food_state') is None):errors.append('สถานะอาหารไม่ถูกต้อง')
        if record.kind=='consent' and d.get('local_storage') is not True:errors.append('ต้องยินยอมก่อนบันทึก')
    except (ValueError,TypeError,KeyError) as e:errors.append(str(e))
    if record.kind=='meal' and not errors:
        from services.nutrition import estimate_meal
        calculated['energy']=estimate_meal(record.model_dump(mode='json'))
    return {'status':'fail' if errors else 'unknown' if missing else 'pass','can_record':not errors and (not missing or record.journal is not None),'missing':missing,'errors':errors,'calculated':calculated,'clinical_status':'not_reviewed'}
