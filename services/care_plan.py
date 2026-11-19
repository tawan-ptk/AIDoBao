"""Source-backed starting guidance. No inferred treatment, doses or write actions."""
import re
from services.personalization import personal_context

HEALTHY='https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes'
MANAGING='https://www.niddk.nih.gov/health-information/diabetes/overview/managing-diabetes'

def care_plan_request(query,records):
    if not re.search(r'เบาหวาน|diabetes',query,re.I):return None
    if not re.search(r'(?:แพลน|แผน|ตาราง).*(?:ดูแล|สุขภาพ|เบาหวาน)|(?:ดูแล|สุขภาพ|เบาหวาน).*(?:แพลน|แผน|ตาราง)|ดูแลเบาหวาน.*(?:ยังไง|อย่างไร)',query):return None
    if re.search(r'ปรับยา|เพิ่มยา|ลดยา|หยุดยา|ขนาดยา|กี่เม็ด|วินิจฉัย',query):return None
    ctx=personal_context(records)
    special=set(ctx['flags'])&{'child','pregnancy','kidney_care','complex_care','special_nutrition'}
    food=('มื้ออาหาร: ใช้เมนูและปริมาณตามแผนที่ทีมรักษาให้ไว้ แล้วบันทึกสิ่งที่กินเพื่อช่วยทบทวนแผน' if special else
          'มื้ออาหาร: ลองแบ่งจานเป็นผักที่มีแป้งน้อยครึ่งจาน โปรตีนหนึ่งในสี่ และข้าวหรือแป้งใยอาหารสูงอีกหนึ่งในสี่ เลือกน้ำเปล่าแทนเครื่องดื่มหวาน')
    lines=['ได้ครับ เริ่มจากแผนดูแลเบาหวานเบื้องต้นนี้ได้เลย',
           '• '+food,
           '• ระหว่างวัน: เลือกกิจกรรมที่ทำไหวและชอบ เริ่มทีละน้อย หากจะเริ่มหรือเพิ่มการออกกำลัง ให้คุยกับทีมรักษาว่าแบบไหนเหมาะกับคุณ',
           '• ยาและค่าน้ำตาล: ใช้ยาตามที่สั่ง ตรวจน้ำตาลตามแผนของทีมรักษา และจดผลไว้ ไม่เปลี่ยนเวลาหรือขนาดยาเอง',
           '• ก่อนนอน: จัดเวลาพักผ่อนให้สม่ำเสมอ และเตรียมบันทึกอาหาร กิจกรรม และค่าน้ำตาลไว้คุยในการนัดครั้งถัดไป']
    if special:lines.append('จากข้อมูลที่คุณยืนยันไว้ ควรให้ทีมรักษาช่วยกำหนดอาหารและกิจกรรมเฉพาะตัวก่อนครับ')
    lines.append('ถ้าต้องการจัดเป็นตาราง บอกเวลาตื่น มื้ออาหาร และช่วงที่สะดวกทำกิจกรรมได้ในข้อความเดียวครับ')
    citations=[{'document_id':'niddk-care-plan','chunk_id':'niddk-care-'+str(i),'heading':title,'url':url,
                'publisher':'NIDDK, National Institutes of Health','accessed_at':'2026-10-12',
                'location':location,'content_type':'editorial_summary','clinical_review':'not_reviewed',
                'text':summary} for i,(title,url,location,summary) in enumerate([
        ('Healthy Living with Diabetes',HEALTHY,'Plate method; physical activity; meal timing',
         'สรุปภาษาไทย: วิธีแบ่งจานคือผักแป้งน้อยครึ่งจาน อาหารคาร์โบไฮเดรตใยอาหารสูงและโปรตีนอย่างละหนึ่งในสี่ เริ่มกิจกรรมทีละน้อยและปรึกษาทีมรักษาเรื่องรูปแบบและเวลาที่เหมาะสม'),
        ('Managing Diabetes',MANAGING,'Healthy lifestyle; medicines; checking blood glucose; keeping track',
         'สรุปภาษาไทย: ใช้ยาตามที่สั่ง ตกลงวิธีและความถี่ตรวจน้ำตาลกับทีมรักษา บันทึกผลและบริบทไว้ทบทวนร่วมกัน การนอนเพียงพอเป็นส่วนหนึ่งของการดูแลเบาหวาน')])]
    return {'status':'care_plan_guidance','route':'health','mode':'read_only','answer':'\n\n'.join(lines),
            'citations':citations,'record_sources':[],'actions':[],
            'suggestions':['จัดตารางพรุ่งนี้เดิน 20 นาทีตอนเย็น','วันนี้รวมกี่แคล','เปิดโปรไฟล์'],
            'clinical_review':'not_reviewed','answer_mode':'source_backed_starting_plan'}
