"""Resolve explicit edit/delete requests to owner-provided records, never execute them.

No model-generated IDs, SQL or guesses. Ambiguous matches remain choices.
"""
import copy
import re
from datetime import datetime
from services.journal import capture_time,time_context,short_label
from services.schemas import Record,inspect_record

PERIOD_LABELS={'morning':'เช้า','noon':'เที่ยง','afternoon':'บ่าย','evening':'เย็น','night':'กลางคืน'}
KIND_LABELS={'meal':'อาหาร','activity':'กิจกรรม','sleep':'การนอน','medication':'ยา','appointment':'นัดหมาย','measurement':'ค่าตรวจ','wellbeing':'ความรู้สึก','profile':'โปรไฟล์','routine':'รายการในแผน','constraint':'เวลาที่ล็อก','feedback':'ผลตอบรับ','consent':'ความยินยอมเก็บข้อมูล'}

def record_label(r):
    label=short_label(r) if r['kind'] in ('meal','activity','sleep','medication','appointment','measurement','wellbeing') else r['data'].get('label') or KIND_LABELS.get(r['kind'],r['kind'])
    if r['kind']=='measurement' and r['data'].get('value') is not None:label+=' '+str(r['data']['value'])+' '+str(r['data'].get('unit') or '')
    if r['kind']=='meal' and r['data'].get('quantity') is not None:label+=' · '+str(r['data']['quantity'])+' '+str(r['data'].get('unit') or '')
    j=r.get('journal') or {}
    when=' · '.join(str(x) for x in (j.get('date'),PERIOD_LABELS.get(j.get('period')),j.get('clock')) if x)
    if not when:when=str(r['data'].get('occurred_at') or r['data'].get('start') or '')
    return str(label)+(' · '+when if when else '')

def proposal(answer,actions=None,**extra):
    return {'status':'management_proposal','route':'website_assistant','mode':'proposal_only','answer':answer,'actions':actions or [],'citations':[],'record_sources':[],'suggestions':['ใช้งานยังไง','วันนี้กินอะไรไปบ้าง'],'clinical_review':'not_reviewed',**extra}

def matching_records(target,records,now):
    rows=[r for r in records if r['kind']!='consent']
    original=target
    if 'โปรไฟล์' in target:rows=[r for r in rows if r['kind']=='profile']
    elif re.search(r'บันทึก|รายการล่าสุด',target):rows=[r for r in rows if r['kind'] in ('meal','activity','sleep','medication','appointment','measurement','wellbeing')]
    for word,kind in [('อาหาร','meal'),('มื้อ','meal'),('กิจกรรม','activity'),('การนอน','sleep'),('ค่าตรวจ','measurement'),('นัดหมาย','appointment')]:
        if word in target:
            rows=[r for r in rows if r['kind']==kind];target=target.replace(word,'');break
    try:j,clocks,warnings=time_context(target,now)
    except ValueError:return []
    if warnings:return []
    explicit_date=bool(re.search(r'วันนี้|เมื่อวาน|พรุ่งนี้|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}',target))
    if explicit_date:rows=[r for r in rows if (r.get('journal') or {}).get('date',str(r['data'].get('occurred_at') or r['data'].get('start') or '')[:10])==j['date']]
    # มื้อเช้า is an explicit selector; dish names with เย็น are not.
    period=re.search(r'(?:มื้อ|อาหาร|ตอน|ช่วง)(เช้า|เที่ยง|บ่าย|เย็น|กลางคืน)',original)
    if period:rows=[r for r in rows if (r.get('journal') or {}).get('period')==next(k for k,v in PERIOD_LABELS.items() if v==period[1])]
    if clocks:rows=[r for r in rows if str((r.get('journal') or {}).get('clock') or '')[:5]==clocks[0][0] or str(r['data'].get('occurred_at') or r['data'].get('start') or '')[11:16]==clocks[0][0]]
    target=re.sub(r'(?:มื้อ|อาหาร|ตอน|ช่วง)(?:เช้า|เที่ยง|บ่าย|เย็น|กลางคืน)','',original)
    target=re.sub(r'\d{1,2}[.:]\d{2}(?:\s*น\.)?','',target)
    target=re.sub(r'วันนี้|เมื่อวาน|พรุ่งนี้|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|บันทึก|รายการ|ข้อมูล|อาหาร|กิจกรรม|การนอน|ค่าตรวจ|นัดหมาย|โปรไฟล์|ของฉัน|ของผม|ล่าสุด|ทั้งหมด|ทุก','',target).strip(' :：')
    if target:
        rows=[r for r in rows if target==short_label(r) or target==r['data'].get('label') or (r['kind']=='measurement' and target=={'weight':'น้ำหนัก','height':'ส่วนสูง','glucose':'น้ำตาล'}.get(r['data'].get('name')))]
    if not target and not re.search(r'บันทึก|รายการ|โปรไฟล์|อาหาร|มื้อ|กิจกรรม|การนอน|ค่าตรวจ|นัดหมาย|น้ำหนัก|ส่วนสูง|น้ำตาล',original):return []
    if 'ล่าสุด' in original and rows:
        return [max(rows,key=lambda r:(r.get('created_at',''),r['id']))]
    return rows

def edited_record(old,replacement,time_only=False,quantity_only=False):
    r={k:copy.deepcopy(v) for k,v in old.items() if k not in ('id','version','created_at','status')}
    r['previous_id']=old['id'];r['evidence']={};r['source']='ผู้ใช้ขอแก้บันทึกผ่านแชต; ตรวจยืนยันก่อนเก็บ'
    if quantity_only:
        if r['data'].get('components'):
            raise ValueError('มื้อนี้มีอาหารหลายอย่างครับ กดแก้รายละเอียดเพื่อเปลี่ยนปริมาณข้าวและกับข้าวแยกกัน')
        from services.food_portions import find_portion
        amount=find_portion(replacement)
        if r['kind']!='meal' or not amount or amount['span']!=replacement.strip() or amount['quantity']<=0:
            raise ValueError('ระบุปริมาณอาหารพร้อมหน่วย เช่น “แก้ปริมาณข้าวมันไก่เป็นครึ่งจาน” ครับ')
        r['data'].update(quantity=amount['quantity'],unit=amount['unit'])
    elif time_only:
        clock=re.fullmatch(r'(\d{1,2})[.:](\d{2})(?:\s*น\.)?',replacement)
        if not clock or int(clock[1])>23 or int(clock[2])>59:raise ValueError('ระบุเวลาเป็น 17.00 หรือ 17:00 ครับ')
        if not r.get('journal'):raise ValueError('รายการนี้ยังไม่มีวันที่บันทึก กรุณาระบุวันและเวลาให้ครบครับ')
        value=f'{int(clock[1]):02}:{clock[2]}';r['journal']['clock']=value;r['journal']['clock_source']='user_edited'
        field='start' if r['kind'] in ('activity','sleep','appointment') else 'occurred_at'
        r['data'][field]=r['journal']['date']+'T'+value+':00+07:00'
        if r['data'].get('end') and datetime.fromisoformat(r['data']['end'])<=datetime.fromisoformat(r['data'][field]):raise ValueError('เวลาเริ่มใหม่อยู่หลังเวลาสิ้นสุด กรุณาระบุเวลาเริ่มและสิ้นสุดใหม่ครับ')
    elif r['kind'] in ('meal','activity','medication','appointment','wellbeing','routine','constraint'):
        if len(replacement)>120 or re.search(r'\n|(?:ตอน|ช่วง)(?:เช้า|เที่ยง|เย็น)|\d{1,2}[.:]\d{2}|และ|แล้ว',replacement):raise ValueError('บอกชื่อใหม่สั้น ๆ หรือใช้ “แก้เวลา…เป็น 17.00” ครับ')
        key='note' if r['kind']=='wellbeing' else 'label' if r['kind'] in ('routine','constraint') else 'name'
        r['data'][key]=replacement;r['text']=replacement
        # A renamed food no longer has the previous catalog's identity.
        if r['kind']=='meal':
            r['data'].pop('food_id',None)
            r['data'].pop('components',None)
        if r['kind'] in ('activity','routine'):r['data'].pop('catalog_id',None)
        if r['kind']=='medication':
            for field in ('dose','unit','instruction_source'):r['data'][field]=None
            r['data']['state']='unknown'
    elif r['kind']=='measurement':
        m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(กก\.?|กิโลกรัม|kg|ซม\.?|cm|mg/dL|mmol/L|%)',replacement,re.I)
        if not m:raise ValueError('ระบุค่าพร้อมหน่วย เช่น “แก้บันทึกน้ำหนักล่าสุดเป็น 68 กก.” ครับ')
        unit={'กก':'kg','กก.':'kg','กิโลกรัม':'kg','ซม':'cm','ซม.':'cm'}.get(m[2],m[2])
        r['data'].update(value=float(m[1]),unit=unit)
    else:raise ValueError('บอกช่องที่ต้องการแก้ เช่น “แก้น้ำหนักเป็น 68 กก.” ครับ')
    check=inspect_record(Record.model_validate(r))
    if not check['can_record']:raise ValueError('ข้อมูลใหม่ยังไม่ถูกต้อง กรุณาตรวจชื่อ ค่า หรือเวลาอีกครั้งครับ')
    return r

def profile_change(target,replacement,records):
    fields={'น้ำหนัก':('weight_kg',r'(\d+(?:\.\d+)?)\s*(?:กก\.?|กิโลกรัม|กิโล|kg)'), 'ส่วนสูง':('height_cm',r'(\d+(?:\.\d+)?)\s*(?:ซม\.?|เซนติเมตร|cm)'), 'อายุ':('age',r'(\d+)\s*(?:ปี)?')}
    old=max((r for r in records if r['kind']=='profile'),key=lambda r:r.get('created_at',''),default=None)
    data=copy.deepcopy(old['data']) if old else {}
    if target in fields:
        key,pattern=fields[target];m=re.fullmatch(pattern,replacement,re.I)
        if not m:raise ValueError('ระบุค่าพร้อมหน่วย เช่น “แก้น้ำหนักเป็น 68 กก.” ครับ')
        data[key]=int(m[1]) if key=='age' else float(m[1])
    elif target in ('การแพ้','รายการแพ้','แพ้อาหาร','โรคประจำตัว','ยาที่ใช้','ความชอบ'):
        key={'การแพ้':'allergies','รายการแพ้':'allergies','แพ้อาหาร':'allergies','โรคประจำตัว':'conditions','ยาที่ใช้':'medications','ความชอบ':'preferences'}[target]
        if replacement in ('ไม่ทราบ','ยังไม่ทราบ') and key=='allergies':data[key]=None
        else:data[key]=[] if replacement in ('ไม่มี','ไม่มีที่ทราบ') else [x.strip() for x in re.split(r'[,、]|และ',replacement) if x.strip()]
    else:return None
    r={'kind':'profile','data':data,'previous_id':old['id'] if old else None,'source':'ผู้ใช้ขอแก้โปรไฟล์ผ่านแชต; ตรวจยืนยันก่อนเก็บ','origin':'self_report'}
    if not inspect_record(Record.model_validate(r))['can_record']:raise ValueError('ค่าที่ระบุอยู่นอกช่วงที่รองรับครับ กรุณาตรวจอีกครั้ง')
    if old and data==old['data']:return proposal('ข้อมูลเดิมตรงกับค่าที่ขอแล้วครับ ไม่ต้องแก้ซ้ำ')
    return proposal('เตรียมแก้'+target+'เป็น '+replacement+' ครับ ตรวจรายละเอียดก่อนยืนยันได้เลย', [{'type':'records','records':[r],'inline':True,'before':[old] if old else [],'label':'ตรวจการแก้'+target}])

def management_request(query,records,now=None):
    now=now or capture_time()
    text=re.sub(r'^(?:(?:ฉัน|ผม)?(?:อยากให้|อยาก|ต้องการ)|ช่วย|ขอให้|ขอ)\s*','',query.strip())
    text=re.sub(r'(?:ให้หน่อย|หน่อย|ด้วย)?(?:ครับ|ค่ะ|คะ)?[ ?]*$','',text).strip()
    if re.search(r'อย่า|ยังไม่|ไม่ต้อง|ถ้า|สมมติ|ยังไง|อย่างไร',text):return None
    deleting=re.match(r'^ลบ\s*(.+)$',text)
    editing=re.match(r'^(?:แก้(?:ไข)?|เปลี่ยน|อัปเดต)\s*(.+?)\s*(?:เป็น|ให้เป็น|จากเดิมเป็น)\s*(.+)$',text)
    if not deleting and not editing:
        if re.fullmatch(r'(?:แก้(?:ไข)?|ลบ)(?:ข้อมูล|บันทึก|รายการ)?',text):return proposal('บอกชื่อรายการที่ต้องการครับ เช่น “แก้ข้าวขาหมูเป็นโจ๊ก” หรือ “ลบบันทึกข้าวขาหมูวันนี้”')
        return None
    if deleting and (re.fullmatch(r'ข้อมูล(?:ของฉัน|ของผม)?ทั้งหมด(?:ของฉัน|ของผม)?',deleting[1]) or deleting[1] in ('ทั้งหมด','ข้อมูลของฉัน','ข้อมูลของผม')):
        return proposal('จะลบข้อมูลที่เก็บในเว็บทั้งหมดของคุณ รวมโปรไฟล์ บันทึก และแผนครับ ตรวจจำนวนก่อนกดยืนยันได้เลย',[{'type':'delete_records','scope':'all','record_ids':[],'label':'ตรวจการลบข้อมูลทั้งหมด'}])
    if deleting and deleting[1] in ('ข้อมูล','รายการ','บันทึก'):return proposal('ต้องการลบรายการไหนครับ? บอกชื่อ เช่น “ลบข้าวขาหมูวันนี้” หรือ “ลบบันทึกล่าสุด” ถ้าจะลบทุกอย่าง พิมพ์ “ลบข้อมูลทั้งหมด”')
    target=deleting[1] if deleting else editing[1]
    time_only=bool(editing and target.startswith('เวลา'))
    quantity_only=bool(editing and target.startswith('ปริมาณ'))
    if time_only:target=target.removeprefix('เวลา').strip()
    if quantity_only:target=target.removeprefix('ปริมาณ').strip()
    if editing and not time_only and not quantity_only:
        try:
            profile_target=re.sub(r'^(?:โปรไฟล์|ข้อมูล)\s*','',target).removesuffix('ของฉัน').removesuffix('ของผม').strip()
            p=profile_change(profile_target,editing[2],records)
            if p:return p
        except ValueError as e:return proposal(str(e))
    rows=matching_records(target,records,now)
    if not rows:return proposal('ยังไม่พบรายการที่ตรงครับ ลองระบุชื่อและวัน เช่น “ลบบันทึกข้าวขาหมูวันนี้” หรือ “แก้บันทึกน้ำหนักล่าสุดเป็น 68 กก.”')
    all_matches=bool(deleting and re.search(r'ทั้งหมด|ทุก',target))
    if len(rows)>(30 if all_matches else 20):return proposal('พบหลายรายการครับ เพิ่มชื่อ วันที่ หรือช่วงเวลาเพื่อเลือกให้ตรงก่อน')
    actions=[]
    if deleting:
        groups=[rows] if all_matches else [[r] for r in rows]
        for group in groups:actions.append({'type':'delete_records','scope':'records','record_ids':[r['id'] for r in group],'label':'ตรวจการลบ '+(str(len(group))+' รายการ' if len(group)>1 else record_label(group[0]))})
    else:
        for r in rows:
            try:updated=edited_record(r,editing[2],time_only,quantity_only)
            except ValueError as e:return proposal(str(e))
            actions.append({'type':'records','records':[updated],'inline':True,'before':[r],'label':'แก้ '+record_label(r)+' → '+editing[2]})
    return proposal(('พบ '+str(len(rows))+' รายการครับ เลือกรายการที่ต้องการ'+('ลบ' if deleting else 'แก้ไข') if len(actions)>1 else 'ตรวจรายการ'+('ที่จะลบ' if deleting else 'ก่อนและหลังแก้ไข')+' แล้วกดยืนยันในแชตได้เลยครับ'),actions)
