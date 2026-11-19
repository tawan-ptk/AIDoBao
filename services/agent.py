"""Website assistant with an allowlist of reviewable actions.
Returns proposals only. The same validation/consent/owner confirmation APIs
handle every write; the model never receives SQL, code or an executable tool.
"""
import re
from services.journal import prepare_journal,compact_journal,capture_time,time_context,MEAL_HEADING,PREFIX,split_meal_span,NON_CAPTURE_LANGUAGE
from services.chat_routing import OFFTOPIC,is_usage_question,usage_response
from services.chat_management import management_request
from services.personalization import personal_context

PAGES={'โปรไฟล์':'profile','ข้อมูลสุขภาพ':'profile','บันทึก':'record','ประวัติ':'record','แผน':'plan','ตาราง':'plan','ความรู้':'knowledge','หน้าหลัก':'overview','ภาพรวม':'overview','แชต':'chat'}

def response(answer,actions=None,**extra):
    return {'status':'agent_proposal','route':'website_assistant','mode':'proposal_only','answer':answer,'actions':actions or [],'citations':[],'record_sources':[],'suggestions':['แนะนำเมนูมื้อเย็น','วันนี้ทำอะไรไปบ้าง','เปิดโปรไฟล์'],'clinical_review':'not_reviewed',**extra}

def agent_request(query,records,now=None):
    if OFFTOPIC.search(query):return None
    if is_usage_question(query):return usage_response(query)
    managed=management_request(query,records,now)
    if managed is not None:return managed
    if re.search(r'^(?:ช่วย)?(?:เปิด|ไป|ดูหน้า)',query):
        page=next((v for k,v in PAGES.items() if k in query),None)
        if page:return response('เปิดหน้าที่ต้องการได้จากปุ่มนี้ครับ',[{'type':'navigate','page':page,'label':'เปิด'+next(k for k,v in PAGES.items() if v==page)}])
    if re.search(r'ประเมิน.*(?:สุขภาพ|สภาวะ|ร่างกาย)|ดัชนีมวลกาย|\bbmi\b|(?:ฉัน|ผม)(?:หนัก|สูง|แพ้อะไร).*(?:เท่า|อะไร)|(?:น้ำหนัก|ส่วนสูง|อายุ|โรคประจำตัว|การแพ้)(?:ของ)?(?:ฉัน|ผม).*(?:เท่า|อะไร)',query,re.I) and not re.search(r'ควร|แนะนำ|ปกติไหม',query):
        ctx=personal_context(records);p=ctx['profile']
        parts=['สรุปจากข้อมูลที่คุณยืนยันไว้ ยังไม่ใช่การวินิจฉัยหรือแผนรักษาครับ']
        for key,label,unit in [('age','อายุ','ปี'),('weight_kg','น้ำหนัก','กก.'),('height_cm','ส่วนสูง','ซม.')]:
            parts.append(label+': '+(str(p[key])+' '+unit if p[key] is not None else 'ยังไม่ทราบ'))
        if ctx['bmi'] is not None:parts.append('BMI ผู้ใหญ่: '+str(ctx['bmi'])+' เป็นค่าคำนวณ ไม่ใช้กำหนดแคลอรีหรือวินิจฉัยโรค')
        else:parts.append('ยังไม่แสดง BMI ผู้ใหญ่เมื่อไม่ทราบอายุ ข้อมูลไม่ครบ เป็นเด็ก หรือกำลังตั้งครรภ์')
        parts.append('โรคที่รายงาน: '+(', '.join(p['conditions']) or ('เบาหวานชนิดที่ 2' if p['reported_type2'] else 'ยังไม่ระบุ')))
        parts.append('การแพ้: '+('ยังไม่ทราบ' if p['allergies'] is None else ', '.join(p['allergies']) or 'ไม่มีการแพ้อาหารที่ทราบ'))
        if ctx['flags']:parts.append('ข้อมูลนี้ต้องใช้ความระมัดระวังในการเลือกอาหารเฉพาะบุคคล ระบบจะไม่ตั้งเป้าหมายลดน้ำหนักหรือกำหนดอาหารรักษาโรคเอง')
        return response('\n\n'.join(parts),[{'type':'navigate','page':'profile','label':'ตรวจหรือเพิ่มข้อมูลสุขภาพ'}],context=ctx)
    if re.search(r'^(?:ช่วย)?(?:ส่งออก|ดาวน์โหลด).*ข้อมูล',query):return response('ดาวน์โหลดข้อมูลที่ยืนยันแล้วของคุณได้จากปุ่มนี้ครับ',[{'type':'export','label':'ส่งออกข้อมูลของฉัน'}])
    if re.search(r'^(?:ช่วย)?(?:แก้|ตั้งค่า|อัปเดต|บันทึก|เพิ่ม).*โปรไฟล์|^(?:ฉัน|ผม)?(?:อายุ|สูง|ส่วนสูง|น้ำหนัก|หนัก|แพ้)',query) and not re.search(r'เท่าไร|เท่าไหร่|ไหม|หรือ|อย่างไร|ยังไง|ไม่แพ้|ไม่ได้แพ้',query):
        profiles=[r for r in records if r['kind']=='profile'];old=max(profiles,key=lambda r:r.get('created_at',''),default=None)
        data=dict(old['data']) if old else {}
        changes={}
        for key,pattern in [('age',r'อายุ\s*(\d+)\s*(?:ปี)?'),('height_cm',r'(?:ส่วนสูง|สูง)\s*(\d+(?:\.\d+)?)\s*(?:ซม|เซนติเมตร|cm)'),('weight_kg',r'(?:น้ำหนัก|หนัก)\s*(\d+(?:\.\d+)?)\s*(?:กก|กิโลกรัม|กิโล|kg)')]:
            m=re.search(pattern,query,re.I)
            if m:changes[key]=int(m[1]) if key=='age' else float(m[1])
        # Only simple single/allergy lists; ambiguous mixed sentences require the form.
        m=re.fullmatch(r'(?:ฉัน|ผม)?แพ้(?:อาหาร)?\s*([^\n\d?!]+)',query)
        if m:changes['allergies']=[x.strip() for x in re.split(r'[,、]|และ',m[1]) if x.strip()]
        if changes:
            data.update(changes)
            record={'kind':'profile','data':data,'source':'ผู้ใช้ระบุข้อมูลโปรไฟล์ในแชต; ตรวจยืนยันก่อนเก็บ','origin':'self_report','previous_id':old['id'] if old else None}
            return response('เตรียมแก้ข้อมูลเฉพาะที่คุณระบุแล้วครับ ตรวจรายละเอียดก่อนยืนยัน',[{'type':'records','records':[record],'inline':True,'before':[old] if old else [],'label':'ตรวจและยืนยันโปรไฟล์'}])
    if re.search(r'จัดตาราง|วางแผน|จัดแผน|จัดแพลน|วางแพลน',query):
        if re.search(r'ยา|อินซูลิน|ปรับ|เพิ่มขนาด|ลดขนาด',query):return response('เวลายาต้องใช้คำสั่งที่ทีมรักษายืนยัน ผมไม่กำหนดขนาดหรือย้ายเวลาให้เองครับ',[{'type':'navigate','page':'plan','label':'กรอกเวลาตามคำสั่งใช้ยา'}])
        if re.search(r'(?:เดิน|วิ่ง|โยคะ|ปั่นจักรยาน|ออกกำลัง|นอน|อ่าน|พัก)',query):
            minutes=re.search(r'(\d+)\s*นาที',query)
            captured=now or capture_time();j,clocks,warnings=time_context(query,captured)
            if warnings:return response('กรุณาระบุวันหรือเวลาให้ชัดเจนก่อนจัดตารางครับ',[{'type':'navigate','page':'plan','label':'เลือกวันและเวลา'}])
            if not minutes or (not clocks and j['period']=='unspecified'):return response('บอกระยะเวลาและช่วงที่สะดวกเพิ่มนิดหนึ่งครับ เช่น “จัดตารางพรุ่งนี้ เดิน 30 นาทีตอนเย็น”')
            if not 1<=int(minutes[1])<=1440:return response('ระยะเวลาต้องอยู่ระหว่าง 1–1440 นาทีครับ')
            windows={'morning':('07:00','10:00'),'noon':('11:00','13:00'),'afternoon':('13:00','16:00'),'evening':('17:00','19:00'),'night':('20:00','22:00')}
            lo,hi=(clocks[0][0],clocks[0][0]) if clocks else windows[j['period']]
            label=re.search(r'เดิน|วิ่ง|โยคะ|ปั่นจักรยาน|ออกกำลังกาย|ออกกำลัง|นอน|พัก',query)
            if not label:return response('เลือกรายการที่ต้องการจัดเวลาในหน้าแผนครับ',[{'type':'navigate','page':'plan','label':'เลือกกิจกรรม'}])
            domain='sleep' if label[0]=='นอน' else 'wellbeing' if label[0]=='พัก' else 'activity'
            ctx=personal_context(records)
            if domain=='activity' and ctx['profile']['mobility_limits']:return response('มีข้อจำกัดการเคลื่อนไหวในโปรไฟล์ กรุณาเลือกกิจกรรมที่ผู้ดูแลยืนยันก่อนจัดเวลาครับ',[{'type':'navigate','page':'plan','label':'ตรวจรายการกับผู้ดูแล'}])
            record={'kind':'routine','text':label[0],'origin':'self_report','source':'ผู้ใช้ขอจัดเวลา; ช่วงเวลาที่ไม่ระบุเป็นตัวเลขคือข้อเสนอให้ตรวจ','data':{'domain':domain,'label':label[0],'dates':[j['date']],'earliest':lo,'latest':hi,'duration_minutes':int(minutes[1]),'fixed':bool(clocks),'goal':label[0]}}
            note='ใช้วันที่ '+j['date']+' และเวลา '+lo+('–'+hi if lo!=hi else '')+' น. '
            if not clocks:note+='ช่วงตัวเลขนี้เป็นข้อเสนอจากช่วงเวลาที่คุณบอก แก้ได้ก่อนยืนยัน '
            return response(note+'นี่คือการจัดเวลาสิ่งที่คุณเลือก ไม่ใช่การประเมินว่ากิจกรรมเหมาะกับสุขภาพ หลังบันทึกรายการแล้วกดเสนอแผนเพื่อตรวจเวลาชนกับรายการเดิมครับ',[{'type':'records','records':[record],'label':'ตรวจและเพิ่มรายการในแผน'},{'type':'plan','start_date':j['date'],'label':'เสนอแผนจากรายการที่ยืนยันแล้ว'}])
        return response('จัดเวลาจากรายการที่คุณยืนยันไว้ได้ครับ ถ้าต้องการเพิ่มรายการ บอกเช่น “จัดตารางพรุ่งนี้เดิน 30 นาทีตอนเย็น”',[{'type':'plan','start_date':(now or capture_time()).date().isoformat(),'label':'ตรวจและเสนอแผน'},{'type':'navigate','page':'plan','label':'แก้รายการและเวลาที่ล็อก'}])
    explicit=re.match(r'^(?:ช่วย)?(?:บันทึก|จด|เพิ่มบันทึก)\s*[:：]?\s*',query)
    # Natural statements can also prepare a draft; questions and intentions cannot.
    starts_action=bool(re.match(r'^(?:ฉัน|ผม|หนู|เรา)?\s*'+PREFIX+r'(?:ฉัน|ผม|หนู|เรา)?\s*(?:กิน|ทาน|รับประทาน|ดื่ม|เดิน|วิ่ง|นอน|งีบ|รู้สึก|ชั่ง|นัดหมอ|'+MEAL_HEADING+')',query))
    # A bare, explicitly named food combination can also open a review draft.
    statement=not NON_CAPTURE_LANGUAGE.search(query) and (starts_action or bool(split_meal_span(query)))
    if explicit or statement:
        text=query[explicit.end():] if explicit else query
        if explicit:text=re.split(r'\s*(?:แล้ว|และ|ช่วย)?\s*แนะนำ(?:เมนู|อาหาร|มื้อ)',text,maxsplit=1)[0].strip()
        result=compact_journal(prepare_journal(text,(now or capture_time()).isoformat()))
        if result['unparsed']:return response('ยังมีข้อความที่แยกได้ไม่ชัด กรุณาตรวจหมวดและชื่อรายการในหน้าบันทึกครับ',[{'type':'journal','text':text,'captured_at':result['captured_at'],'label':'ตรวจและแก้รายการ'}])
        if result['items']:
            records=[item['record'] for item in result['items']]
            periods={'morning':'ตอนเช้า','noon':'ตอนเที่ยง','afternoon':'ตอนบ่าย','evening':'ตอนเย็น','night':'ตอนกลางคืน'}
            labels=[]
            for r in records:
                j=r['journal'];when=j.get('clock') or periods.get(j['period'],'')
                line='• '+r['text']+(' · '+when if when else '')
                if j.get('clock_source')=='capture_time':line+=' (เวลาที่พิมพ์)'
                if r['kind']=='meal':
                    from services.nutrition import estimate_meal,calorie_text
                    energy=estimate_meal(r)
                    line+=' · '+(calorie_text(energy) if energy['kcal'] is not None else 'ยังไม่มีแคลอรีอ้างอิง')
                    if energy['assumed_portion']:line+=' (ใช้ปริมาณอ้างอิง แก้ได้)'
                labels.append(line)
            return response('แยกได้ '+str(len(records))+' รายการครับ\n'+'\n'.join(labels)+'\n\nตรวจชื่อและเวลา แล้วกดยืนยันเพื่อบันทึกได้เลยครับ',[{'type':'records','records':records,'compact':True,'label':'ตรวจและบันทึก '+str(len(records))+' รายการ'},{'type':'journal','text':text,'captured_at':result['captured_at'],'label':'แก้ชื่อหรือเวลา'}],details=[w for item in result['items'] for w in item['warnings']])
    return None


def wants_menu(query):
    if OFFTOPIC.search(query):return False
    # Recall questions must continue to read confirmed records, not choose a
    # new meal. Advice questions can include ข้าว/กับ between กิน and อะไร.
    food_question=r'(?:กิน|ทาน|รับประทาน)\s*(?:ข้าว(?:สวย)?\s*)?(?:กับ|คู่กับ)?\s*อะไร'
    if re.search(food_question+r'\s*(?:ไป(?:แล้ว)?|มา(?:แล้ว)?|แล้ว)?บ้าง(?:\s|[?？.!]|ครับ|ค่ะ|คะ|$)',query):return False
    advice=r'\s*(?:ดี|ได้|เหมาะ|ตอนเช้า|ตอนเที่ยง|ตอนเย็น)'
    ending=r'\s*(?:[?？.!]|ครับ|ค่ะ|คะ|$)'
    pair_question=r'(?:กิน|ทาน|รับประทาน)\s*(?:ข้าว(?:สวย)?\s*(?:กับ|คู่กับ)?|กับ|คู่กับ)\s*อะไร'
    patterns=[
        r'แนะนำ.*(?:เมนู|อาหาร|มื้อ|กับข้าว)|เลือกเมนู|ขอเมนู|แพ้.*กินอะไร',
        r'(?:เช้า|เที่ยง|เย็น|มื้อนี้|มื้อถัดไป|มื้อต่อไป|วันนี้|พรุ่งนี้).*'+food_question+'(?:'+advice+'|'+ending+')',
        food_question+advice,pair_question+ending,
        r'ข้าว(?:สวย)?\s*(?:กิน|ทาน)?\s*(?:กับ|คู่กับ)\s*อะไร(?:'+advice+'|'+ending+')',
        r'(?:ควร|ช่วยเลือก).*'+pair_question,
    ]
    return any(re.search(pattern,query) for pattern in patterns)
