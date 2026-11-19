"""Read-only calorie questions: deterministic arithmetic, never generated numbers."""
import re
from datetime import datetime,timedelta

from services.food_portions import find_portion,strip_portions
from services.food_reference import food_reference
from services.nutrition import ZONE,estimate_meal,daily_energy,calorie_text

ENERGY=re.compile(r'แคล|กิโลแคล|calori|kcal|พลังงาน',re.I)
DAILY=re.compile(r'วันนี้|เมื่อวาน|ทั้งวัน|รวม|ยอด|ทั้งหมด|\d{4}-\d{2}-\d{2}')
FDA_LABEL='https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label'

def food_query(query,keep_portions=False):
    text=re.sub(r'(?:กี่|เท่าไร|เท่าไหร่|จำนวน)?\s*(?:กิโลแคลอรี(?:่)?|แคล[ลอรีรี่]*|calories?|kcal)(?:\s*(?:เท่าไร|เท่าไหร่))?', '', query,flags=re.I)
    text=re.sub(r'วันนี้|เมื่อวาน|(?:ตอน|ช่วง)(?:เช้า|เที่ยง|บ่าย|เย็น|กลางคืน)','',text)
    # Several prefixes may stack, e.g. "ช่วยคำนวณแคลของ...".
    for _ in range(6):
        text=re.sub(r'^(?:ช่วย|ของ|ขอ|คำนวณ|นับ|บอก|พลังงาน|ใน|ต่อ|ฉัน|ผม|หนู|เรา|กิน|ทาน|รับประทาน|ดื่ม|อาหาร|เมนู)\s*','',text.strip())
    text=re.sub(r'(?:ประมาณ|มี|ให้|ได้|เท่าไร|เท่าไหร่|ครับ|ค่ะ|คะ|นะ|\?)\s*$','',text.strip())
    text=re.sub(r'(?:มี|ให้|ได้)\s*$','',text.strip())
    return (text if keep_portions else strip_portions(text)).strip(' ?.!')

def calorie_request(query,records,now=None):
    if not ENERGY.search(query):return None
    if re.match(r'^(?:ช่วย)?(?:บันทึก|จด|เพิ่มบันทึก)',query):return None
    if re.search(r'แคล.*(?:คืออะไร|หมายถึง)|พลังงาน.*คืออะไร|(?:นับ|คำนวณ).*แคล.*(?:ยังไง|อย่างไร)',query):
        definition=bool(re.search(r'คืออะไร|หมายถึง',query))
        answer=('แคลอรีเป็นหน่วยบอกพลังงานที่ได้จากอาหารและเครื่องดื่มครับ บนฉลาก ตัวเลขแคลอรีต้องดูคู่กับปริมาณต่อหนึ่งหน่วยบริโภค กินสองหน่วยก็ได้พลังงานสองเท่า' if definition else
                'บอกชื่ออาหารและปริมาณได้เลยครับ เช่น “ข้าวมันไก่ครึ่งจาน” หรือ “ไข่ต้ม 2 ฟอง” ผมจะใช้ค่าต่อหน่วยอ้างอิงคูณกับปริมาณที่บันทึก ถ้ามีฉลากให้ดูพลังงานต่อหน่วยและจำนวนหน่วยที่กินด้วย')
        answer+='\n\nถาม “วันนี้รวมกี่แคล” เพื่อรวมจากบันทึกที่ยืนยันแล้วได้ รายการที่ยังไม่มีข้อมูลจะแสดงแยกไว้ครับ'
        return {'status':'calorie_help','route':'calorie','mode':'read_only','answer':answer,'record_sources':[],
                'suggestions':['วันนี้รวมกี่แคล','ข้าวมันไก่ 1 จานกี่แคล'],
                'citations':[{'publisher':'FDA','heading':'How to Understand and Use the Nutrition Facts Label','url':FDA_LABEL,
                              'location':'Serving Information / Calories','accessed_at':'2026-10-12','content_type':'editorial_summary',
                              'text':'พลังงานบนฉลากอ้างอิงหนึ่งหน่วยบริโภค จำนวนหน่วยที่กินจึงใช้คูณพลังงาน ความต้องการต่อวันต่างกันตามบุคคล'}]}
    # Explicit lists describe this meal, even when the user says "รวม" or
    # "วันนี้". Do not accidentally substitute the saved daily records.
    from services.journal import split_meal_span,prepare_journal,compact_journal
    listed=re.sub(r'\s*(?:รวม|ทั้งหมด)\s*$','',food_query(query,keep_portions=True))
    spans=split_meal_span(listed)
    if spans:
        estimates=[estimate_meal(compact_journal(prepare_journal('กิน'+span))['items'][0]['record']) for span in spans]
        from services.nutrition import rounded
        known=[e for e in estimates if e['kcal'] is not None]
        total=[rounded(sum(e['kcal'][j] for e in known)) for j in (0,1)] if known else None
        lines=[e['name']+' · '+calorie_text(e) for e in estimates]
        if total:lines.append('รวมรายการที่บอกประมาณ '+f'{total[0]:g}'+('–'+f'{total[1]:g}' if total[0]!=total[1] else '')+' kcal')
        if len(known)<len(estimates):lines.append('ยังไม่รวม '+str(len(estimates)-len(known))+' รายการที่แปลงปริมาณไม่ได้')
        if any(e['assumed_portion'] for e in known):lines.append('รายการที่ไม่ระบุปริมาณใช้หนึ่งหน่วยอ้างอิง แก้ปริมาณได้ครับ')
        return {'status':'calorie_meal_summary','route':'calorie','mode':'read_only','answer':'\n\n'.join(lines),
                'energy_estimates':estimates,'total_kcal':total,'citations':[],
                'record_sources':[],'meal_references':[e['reference'] for e in known],
                'suggestions':['วันนี้รวมกี่แคล'],'clinical_review':'not_reviewed'}
    # Targets, comparisons, physiology and exercise use the health Q&A path.
    if re.search(r'ควร|ต้อง(?:กิน|ทาน)|เป้าหมาย|ลดน้ำหนัก|อ้วน|เผาผลาญ|ออกกำลัง|แคล.*(?:คืออะไร|สำคัญ|หมายถึง)|พลังงาน.*(?:คืออะไร|สำคัญ)',query):return None
    now=(now or datetime.now(ZONE)).astimezone(ZONE)
    base={'mode':'read_only','route':'calorie','citations':[],'record_sources':[],
          'suggestions':['วันนี้รวมกี่แคล','ข้าวมันไก่ 1 จานกี่แคล','ไข่ต้ม 2 ฟองกี่แคล'],
          'clinical_review':'not_reviewed'}
    name=food_query(query)
    if DAILY.search(query) and not food_reference(name).get('kcal'):
        day=now.date()-timedelta(days=1) if 'เมื่อวาน' in query else now.date()
        explicit=re.search(r'\d{4}-\d{2}-\d{2}',query)
        if explicit:
            try:day=datetime.strptime(explicit[0],'%Y-%m-%d').date()
            except ValueError:return base|{'status':'needs_clarification','answer':'วันที่ยังไม่ถูกต้องครับ ลองระบุเป็น ปี-เดือน-วัน'}
        summary=daily_energy(records,day)
        if not summary['meal_count']:
            return base|{'status':'calorie_summary','energy_summary':summary,'answer':'ยังไม่มีบันทึกอาหารวันที่ '+str(day)+' ครับ พิมพ์เช่น “เช้ากินข้าวมันไก่ 1 จาน” แล้วกดยืนยันบันทึกก่อน ผมจะรวมแคลอรีให้'}
        if summary['kcal'] is not None:
            lo,hi=summary['kcal'];total=f'{lo:g}'+('–'+f'{hi:g}' if lo!=hi else '')
            lines=[('รวมเฉพาะรายการที่ประเมินได้' if summary['unknown_count'] else 'รวมจากอาหารที่บันทึก')+'วันที่ '+str(day)+' ประมาณ '+total+' kcal ครับ']
        else:lines=['ยังประเมินแคลอรีจากอาหารที่บันทึกวันที่ '+str(day)+' ไม่ได้ครับ']
        periods={'morning':'เช้า','noon':'เที่ยง','afternoon':'บ่าย','evening':'เย็น','night':'กลางคืน'}
        for item in summary['items']:
            lines.append('• '+(periods.get(item['period'],'')+' · ' if item['period'] in periods else '')+item['name']+' · '+calorie_text(item))
        if summary['unknown_count']:lines.append(str(summary['unknown_count'])+' มื้อยังประเมินได้ไม่ครบ รวมเฉพาะอาหารที่มีข้อมูล ไม่ได้นับส่วนที่ไม่ทราบเป็น 0 kcal')
        if summary['assumed_portion_count']:lines.append(str(summary['assumed_portion_count'])+' รายการยังไม่บอกปริมาณ ใช้ 1 หน่วยเสิร์ฟอ้างอิงตามรายการ แก้ปริมาณแล้วผมจะรวมใหม่ครับ')
        if summary['undated_meal_count']:lines.append('บันทึกอาหารที่ยังไม่มีวันที่ '+str(summary['undated_meal_count'])+' รายการไม่ได้รวมในวันนี้')
        lines.append('เป็นค่าคร่าว ๆ ตามสูตรและขนาดเสิร์ฟ ไม่ใช่เป้าหมายพลังงานเฉพาะตัว')
        refs=[ref for i in summary['items'] if i['kcal'] is not None for ref in (i.get('references') or [i['reference']])]
        return base|{'status':'calorie_summary','energy_summary':summary,'answer':'\n\n'.join(lines),
                     'meal_references':refs,'record_sources':[{'record_id':i['record_id'],'text':i['name'],'time':str(day),'label':'อาหาร','source':'บันทึกที่คุณยืนยัน'} for i in summary['items']]}
    name=food_query(query)
    if not name:return None
    if not food_reference(name).get('kcal') and not re.search(r'กี่|เท่าไร|เท่าไหร่|คำนวณ|นับ',query):return None
    amount=find_portion(query)
    estimate=estimate_meal({'kind':'meal','text':name,'data':{'name':name,**({k:amount[k] for k in ('quantity','unit')} if amount else {})}})
    if estimate['kcal'] is None:
        return base|{'status':'calorie_unknown','energy_estimate':estimate,
                     'answer':name+' · '+estimate['note']+'ครับ ยังไม่ใส่ตัวเลขแทนข้อมูลที่ขาด',
                     'meal_references':[estimate['reference']] if food_reference(name).get('kcal') else []}
    answer=name+' '+calorie_text(estimate)+' ครับ\n\n'+estimate['reference']['basis']+' · '+estimate['note']
    if estimate['assumption']:answer+='\n'+estimate['assumption']
    return base|{'status':'calorie_estimate','answer':answer,'energy_estimate':estimate,'meal_references':[estimate['reference']]}
