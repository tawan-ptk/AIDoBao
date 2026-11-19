"""Optional learned intent fallback, bounded by website vocabulary and actions.

It cannot grant medical scope or execute writes. Record IDs and proposed edits
remain the responsibility of the existing owner-scoped management workflow.
"""
import re

from services.agent import PAGES, response
from services.chat_routing import OFFTOPIC, usage_response
from services.model_tasks import intent_messages, parse_intent

WEBSITE_CUES = re.compile(r'ร่วมวัน|[Bb]ao ?[Bb]uddy|เบาบัดดี้|ใช้งาน|ใช้แอป|ใช้เว็บ|เริ่มใช้|เริ่มต้น|คุยกับคุณ|ถามคุณ|ถาม.*ได้บ้าง|ช่วยอะไร|ช่วย.*ใช้งาน|บอก.*ใช้งาน|เปิด.*หน้า|พาไป|เปลี่ยนไปหน้า|บันทึก|รายการ|จัดตาราง|จัดกิจวัตร|วางตาราง|แบ่งเวลา|เมนู|มื้อถัดไป|มื้อต่อไป|สำเนา|สำรองข้อมูล|ดาวน์โหลด|ส่งออก|ประวัติ')


def learned_request(query, generator):
    if OFFTOPIC.search(query) or not WEBSITE_CUES.search(query):
        return None
    try:
        result = generator(intent_messages(query))
        intent = parse_intent(result['output'])['intent']
    except Exception:
        return None
    if intent == 'usage_help':
        answer = usage_response(query)
        answer['intent_engine'] = 'fine_tuned_local_model'
        return answer
    if intent == 'navigate':
        match = next(((name, page) for name, page in PAGES.items() if name in query), None)
        if match:
            name, page = match
            return response('เปิดหน้าที่ต้องการได้จากปุ่มนี้ครับ', [{'type': 'navigate', 'page': page, 'label': 'เปิด' + name}], intent_engine='fine_tuned_local_model')
    if intent == 'export' and re.search(r'ข้อมูล|บันทึก|ประวัติ', query):
        return response('ดาวน์โหลดข้อมูลของคุณได้จากปุ่มนี้ครับ', [{'type': 'export', 'label': 'ส่งออกข้อมูลของฉัน'}], intent_engine='fine_tuned_local_model')
    if intent in ('edit_record', 'delete_record'):
        # No model-generated target IDs or silently rewritten command.
        return response('บอกชื่อรายการที่ต้องการแก้หรือลบได้เลยครับ เช่น “แก้โจ๊กเป็นข้าวต้ม” หรือ “ลบบันทึกล่าสุด” ผมจะให้ตรวจยืนยันก่อน', intent_engine='fine_tuned_local_model')
    if intent == 'record':
        return response('เปิดตรวจรายการและเวลา แล้วกดยืนยันเพื่อบันทึกได้เลยครับ', [{'type': 'journal', 'text': query, 'label': 'ตรวจรายการที่จะบันทึก'}], intent_engine='fine_tuned_local_model')
    if intent == 'schedule':
        return response('บอกกิจกรรม ระยะเวลา และช่วงที่สะดวกครับ เช่น “จัดตารางพรุ่งนี้เดิน 30 นาทีตอนเย็น”', [{'type': 'navigate', 'page': 'plan', 'label': 'เปิดตารางของฉัน'}], intent_engine='fine_tuned_local_model')
    # health/my_data/menu are resolved by their own validated paths. A learned
    # intent never changes out-of-scope text into eligible medical content.
    return None
