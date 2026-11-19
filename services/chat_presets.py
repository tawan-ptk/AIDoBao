"""Quick, rule-based answers for the things people tap or type most often.

Covers: who Baobuddy is, thanks, "สรุปวันนี้", one category for a day ("ยาวันนี้"),
"ติดตามสุขภาพ", and a bare "บันทึกอาหาร" with nothing to record yet.
Read-only: these answers never save, change or delete anything.
"""
import re
from datetime import datetime, timedelta

from services.chat import ZONE, record_date, source_record
from services.journal import short_label

MONTHS = ('ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.')
ORDER = ('meal', 'medication', 'activity', 'sleep', 'measurement', 'wellbeing', 'appointment')
TITLES = {'meal': '🍽️ อาหาร', 'medication': '💊 ยา', 'activity': '🏃 กิจกรรม', 'sleep': '😴 การนอน',
          'measurement': '❤️ ค่าสุขภาพ', 'wellbeing': '🙂 ความรู้สึก', 'appointment': '📅 นัดหมาย'}
SHORT = {'meal': 'อาหาร', 'medication': 'ยา', 'activity': 'กิจกรรม', 'sleep': 'การนอน',
         'measurement': 'ค่าสุขภาพ', 'wellbeing': 'ความรู้สึก', 'appointment': 'นัดหมาย'}
PAGE = {'meal': ('food', 'บันทึกอาหาร'), 'medication': ('medicine', 'บันทึกยา'),
        'activity': ('exercise', 'บันทึกกิจกรรม'), 'sleep': ('health', 'บันทึกการนอน'),
        'measurement': ('health', 'บันทึกค่าสุขภาพ'), 'wellbeing': ('health', 'บันทึกความรู้สึก'),
        'appointment': ('health', 'เพิ่มนัดหมาย')}
PERIOD = {'morning': 'ช่วงเช้า', 'noon': 'ช่วงเที่ยง', 'afternoon': 'ช่วงบ่าย', 'evening': 'ช่วงเย็น', 'night': 'กลางคืน'}
WORDS = {'meal': r'อาหาร|มื้อ\S*|ของกิน', 'medication': r'ยา', 'activity': r'กิจกรรม|ออกกำลัง(?:กาย)?|เดิน|วิ่ง',
         'sleep': r'การนอน|นอน', 'measurement': r'ค่าตรวจ|ค่าสุขภาพ|น้ำตาล|น้ำหนัก|ความดัน',
         'wellbeing': r'ความรู้สึก|อารมณ์', 'appointment': r'นัด(?:หมาย)?'}
MEASURES = {'glucose': 'น้ำตาล', 'weight': 'น้ำหนัก', 'systolic': 'ความดันตัวบน', 'diastolic': 'ความดันตัวล่าง',
            'hba1c': 'HbA1c', 'height': 'ส่วนสูง', 'waist': 'รอบเอว'}
CONTEXT = {'fasting': 'ตอนอดอาหาร', 'before-meal': 'ก่อนอาหาร', 'after-meal': 'หลังอาหาร'}

POLITE = r'(?:ให้หน่อย|หน่อย|ด้วย|บ้าง)?(?:ครับ|ค่ะ|คะ|จ้า|นะ)?[ ?!.]*$'
IDENTITY = re.compile(r'(?:คุณ|เธอ|นาย|แก)?(?:คือ|เป็น)ใคร|ชื่ออะไร|แนะนำตัว|(?:bao ?buddy|เบาบัดดี้)\s*(?:คือ|เป็น)?(?:อะไร|ใคร)'
                      r'|คุณเป็น\s*(?:ai|เอไอ|หุ่นยนต์|บอท|คน)|ใครสร้างคุณ', re.I)
THANKS = re.compile(r'^(?:ขอบคุณ|ขอบใจ|thank)', re.I)
SUMMARY = re.compile(r'^(?:ช่วย|ขอ)?สรุป(?:ให้)?(?:ข้อมูล|บันทึก|กิจวัตร)?(?:ของ)?(?:ฉัน|ผม)?(?:วันนี้|เมื่อวาน|ประจำวัน)?' + POLITE
                     + r'|^วันนี้(?:ฉัน|ผม)?(?:ทำอะไรไป|เป็น(?:ยังไง|อย่างไร))บ้าง' + POLITE)
DAY_KIND = re.compile(r'^(?:บันทึก)?(' + '|'.join(WORDS.values()) + r')(?:ที่บันทึก(?:ไว้)?)?(?:ของ(?:ฉัน|ผม))?(วันนี้|เมื่อวาน)' + POLITE)
DAY_VERB = re.compile(r'^(วันนี้|เมื่อวาน)(?:ฉัน|ผม|เรา)?(?:ได้)?(กิน(?:ข้าว)?|ทาน(?:ข้าว)?|กินยา|ทานยา|ออกกำลัง(?:กาย)?|เดิน|นอน)(?:อะไร)?(?:ไป)?(?:แล้ว)?(?:บ้าง|ยัง|หรือยัง)?' + POLITE)
VERB_KIND = {'กิน': 'meal', 'ทาน': 'meal', 'กินยา': 'medication', 'ทานยา': 'medication', 'ออกกำลัง': 'activity', 'เดิน': 'activity', 'นอน': 'sleep'}
TRACK = re.compile(r'^(?:ติดตาม|ดู)(?:สุขภาพ|ค่าสุขภาพ|ค่าตรวจ|ผลตรวจ)' + POLITE + r'|^ค่า(?:สุขภาพ|ตรวจ)ล่าสุด' + POLITE)
BARE_RECORD = re.compile(r'^(?:ช่วย|ขอ)?(?:บันทึก|จด|เพิ่ม)(?:ข้อมูล)?(' + '|'.join(WORDS.values()) + r'|สุขภาพ)?' + POLITE)


def thai_day(day, today):
    label = f'{day.day} {MONTHS[day.month - 1]}'
    if day == today:
        return 'วันนี้ (' + label + ')'
    if day == today - timedelta(days=1):
        return 'เมื่อวาน (' + label + ')'
    return label


def when(record):
    journal = record.get('journal') or {}
    if journal.get('clock'):
        return journal['clock'][:5] + ' น.'
    if journal.get('period') in PERIOD:
        return PERIOD[journal['period']]
    stamp = record['data'].get('occurred_at') or record['data'].get('start')
    if stamp:
        try:
            return datetime.fromisoformat(stamp).astimezone(ZONE).strftime('%H:%M น.')
        except (TypeError, ValueError):
            pass
    return ''


def label(record):
    data = record['data']
    if record['kind'] == 'measurement' and data.get('value') is not None:
        name = MEASURES.get(data.get('name'), short_label(record))
        return f"{name} {data['value']:g} {data.get('unit') or ''}".strip()
    if record['kind'] == 'medication':
        dose = ' '.join(str(data[k]) for k in ('dose', 'unit') if data.get(k) is not None)
        return (short_label(record) + (' ' + dose if dose else '')).strip()
    return short_label(record) or SHORT[record['kind']]


def kind_of(word):
    return next(k for k, pattern in WORDS.items() if re.fullmatch(pattern, word))


def day_summary(records, day, today, kinds=ORDER):
    rows = [r for r in records if r.get('kind') in kinds and record_date(r) == day.isoformat()]
    title = thai_day(day, today)
    if len(kinds) == 1:
        kind = kinds[0]
        page, button = PAGE[kind]
        if not rows:
            return {'status': 'no_records', 'answer': f'{title} ยังไม่มีบันทึก{SHORT[kind]}ครับ บันทึกเพิ่มได้จากปุ่มด้านล่างเลย',
                    'record_sources': [], 'actions': [{'type': 'navigate', 'page': page, 'label': button}],
                    'suggestions': ['สรุปวันนี้', 'ตอนเที่ยงกินอะไรดี']}
    elif not rows:
        return {'status': 'no_records', 'answer': f'{title} ยังไม่มีบันทึกเลยครับ ลองเริ่มจากมื้ออาหารหรือยาที่ทานไปแล้วก็ได้ครับ',
                'record_sources': [], 'actions': [{'type': 'navigate', 'page': 'food', 'label': 'บันทึกอาหาร'},
                                                  {'type': 'navigate', 'page': 'medicine', 'label': 'บันทึกยา'}],
                'suggestions': ['ตอนเที่ยงกินอะไรดี', 'ช่วยอะไรได้บ้าง']}
    rows.sort(key=lambda r: (when(r) or '99', r.get('created_at', '')))
    blocks = []
    for kind in kinds:
        items = [r for r in rows if r['kind'] == kind]
        if not items:
            continue
        lines = [f'{TITLES[kind]} ({len(items)})'] if len(kinds) > 1 else []
        lines += ['• ' + ' · '.join(x for x in (when(r), label(r)) if x) for r in items[:8]]
        if len(items) > 8:
            lines.append(f'• และอีก {len(items) - 8} รายการ')
        blocks.append('\n'.join(lines))
    head = f'สรุป{title} ครับ' if len(kinds) > 1 else f'{TITLES[kinds[0]]} ที่บันทึก{title} ครับ'
    answer = head + '\n\n' + '\n\n'.join(blocks)
    missing = [SHORT[k] for k in ('meal', 'medication', 'activity') if k in kinds and not any(r['kind'] == k for r in rows)]
    if len(kinds) > 1 and missing:
        answer += '\n\nยังไม่มีบันทึก' + ' '.join(missing)
    return {'status': 'daily_summary', 'answer': answer, 'record_sources': [source_record(r) for r in rows[:12]],
            'suggestions': ['วันนี้รวมกี่แคล', 'ตอนเย็นกินอะไรดี', 'ติดตามสุขภาพ']}


def tracking(records):
    latest = {}
    for r in sorted((r for r in records if r.get('kind') == 'measurement' and r['data'].get('value') is not None),
                    key=lambda r: (record_date(r) or '', r.get('created_at', ''))):
        latest[r['data'].get('name')] = r
    if not latest:
        return {'status': 'no_records', 'answer': 'ยังไม่มีค่าสุขภาพที่บันทึกไว้ครับ ลองบันทึกน้ำตาล น้ำหนัก หรือความดันก่อน แล้วผมจะช่วยสรุปให้ดูครับ',
                'record_sources': [], 'actions': [{'type': 'navigate', 'page': 'health', 'label': 'บันทึกค่าสุขภาพ'}],
                'suggestions': ['สรุปวันนี้', 'ช่วยอะไรได้บ้าง']}
    lines = []
    for name in ('glucose', 'hba1c', 'systolic', 'diastolic', 'weight', 'waist', 'height'):
        r = latest.get(name)
        if not r:
            continue
        day = record_date(r)
        extra = CONTEXT.get(r['data'].get('context'))
        when_text = ' · '.join(x for x in (thai_short(day), extra) if x)
        lines.append('• ' + label(r) + (' · ' + when_text if when_text else ''))
    return {'status': 'health_tracking',
            'answer': 'ค่าสุขภาพล่าสุดที่คุณบันทึกไว้ครับ\n\n' + '\n'.join(lines) + '\n\nเป็นค่าที่บันทึกไว้ ยังไม่ได้ตีความผลตรวจ ถ้าค่าผิดปกติควรปรึกษาแพทย์ครับ',
            'record_sources': [source_record(r) for r in latest.values()],
            'actions': [{'type': 'navigate', 'page': 'health', 'label': 'ดูหน้าสุขภาพ'}],
            'suggestions': ['สรุปวันนี้', 'ค่าน้ำตาลเท่าไรถึงปกติ']}


def thai_short(iso):
    try:
        d = datetime.fromisoformat(iso).date()
    except (TypeError, ValueError):
        return ''
    return f'{d.day} {MONTHS[d.month - 1]}'


def identity_response():
    return {'status': 'identity', 'answer': (
        'ผมชื่อ Baobuddy ครับ 🌿 เป็นผู้ช่วยดูแลสุขภาพในแอป DoBao\n\n'
        'ผมช่วยได้แบบนี้ครับ\n'
        '• สรุปสิ่งที่คุณบันทึกไว้ เช่น อาหาร ยา กิจกรรม และค่าสุขภาพ\n'
        '• แนะนำเมนู และตอบคำถามเรื่องอาหารกับเบาหวาน\n'
        '• ค้นความรู้สุขภาพจากแหล่งที่น่าเชื่อถือ แล้วสรุปให้อ่านง่าย\n'
        '• ช่วยบันทึก แก้ หรือลบรายการ โดยให้คุณตรวจก่อนทุกครั้ง\n\n'
        'ผมไม่วินิจฉัยโรคหรือปรับยาให้นะครับ ถ้ามีอาการผิดปกติควรปรึกษาแพทย์'),
        'suggestions': ['สรุปวันนี้', 'ตอนเที่ยงกินอะไรดี', 'เป็นเบาหวานควรกินอะไร']}


def preset_request(query, records, now=None):
    text = query.strip()
    today = (now or datetime.now(ZONE)).astimezone(ZONE).date()
    base = {'mode': 'read_only', 'citations': [], 'record_sources': [], 'clinical_review': 'not_reviewed'}
    if IDENTITY.search(text):
        return base | {'route': 'identity'} | identity_response()
    if THANKS.search(text) and len(text) <= 30:
        return base | {'route': 'thanks', 'status': 'thanks', 'answer': 'ยินดีครับ 😊 มีอะไรให้ช่วยอีกบอกผมได้เลยนะครับ',
                       'suggestions': ['สรุปวันนี้', 'ตอนเย็นกินอะไรดี']}
    if SUMMARY.search(text):
        day = today - timedelta(days=1) if 'เมื่อวาน' in text else today
        return base | {'route': 'my_data'} | day_summary(records, day, today)
    found = DAY_KIND.search(text)
    if found:
        day = today - timedelta(days=1) if found[2] == 'เมื่อวาน' else today
        return base | {'route': 'my_data'} | day_summary(records, day, today, kinds=(kind_of(found[1]),))
    found = DAY_VERB.search(text)
    if found:
        verb = re.sub(r'ข้าว$|กาย$', '', found[2])
        day = today - timedelta(days=1) if found[1] == 'เมื่อวาน' else today
        return base | {'route': 'my_data'} | day_summary(records, day, today, kinds=(VERB_KIND[verb],))
    if TRACK.search(text):
        return base | {'route': 'my_data'} | tracking(records)
    found = BARE_RECORD.search(text)
    if found:
        word = found[1]
        kind = kind_of(word) if word and word != 'สุขภาพ' else None
        if kind:
            page, button = PAGE[kind]
            examples = {'meal': '“เที่ยงกินข้าวมันไก่ 1 จาน”', 'medication': '“กินยาเมทฟอร์มิน 500 mg หลังอาหารเช้า”',
                        'activity': '“เย็นนี้เดิน 30 นาที”', 'sleep': '“เมื่อคืนนอน 5 ทุ่ม ตื่น 6 โมง”',
                        'measurement': '“น้ำตาลก่อนอาหารเช้า 110”', 'wellbeing': '“วันนี้รู้สึกเครียดนิดหน่อย”',
                        'appointment': '“นัดหมอวันที่ 20 ธ.ค. 9 โมง”'}[kind]
            answer = f'พิมพ์บอกผมได้เลยครับ เช่น {examples} ผมจะแยกรายการให้ตรวจก่อนบันทึก หรือกดปุ่มด้านล่างเพื่อกรอกเองก็ได้ครับ'
        else:
            page, button = 'food', 'เปิดหน้าบันทึก'
            answer = 'อยากบันทึกอะไรดีครับ พิมพ์เล่ามาได้เลย เช่น “เช้ากินโจ๊ก กินยาหลังอาหาร เย็นเดิน 20 นาที” ผมจะแยกเป็นรายการให้ตรวจก่อนบันทึกครับ'
        return base | {'route': 'record_help', 'status': 'record_help', 'answer': answer,
                       'actions': [{'type': 'navigate', 'page': page, 'label': button}],
                       'suggestions': ['สรุปวันนี้', 'ตอนเที่ยงกินอะไรดี']}
    return None
