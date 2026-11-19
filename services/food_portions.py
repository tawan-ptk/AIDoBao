"""Literal food amounts only; never infer a gram weight from dish size."""
import re
from fractions import Fraction

UNIT_PATTERN=r'ทัพพีเล็ก|มิลลิลิตร|กิโลกรัม|ช้อนโต๊ะ|ช้อนชา|ชิ้นคำ|ผลเล็ก|ทัพพี|จาน|ชาม|ถ้วย|แก้ว|กล่อง|ชิ้น|ฟอง|กรัม|ลูก|ผล|จับ|มล\.?|กก\.?|ml\b|kg\b|g\b|ส่วน'
NUMBER_PATTERN=r'\d+\s+\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*/\s*\d+|\d+½|½|\d+(?:\.\d+)?|ครึ่ง|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ'
PORTION=re.compile(r'(?<![\d./-])(?P<number>'+NUMBER_PATTERN+r')\s*(?P<unit>'+UNIT_PATTERN+r')(?P<half>ครึ่ง)?',re.I)
WORDS={'ครึ่ง':.5,'หนึ่ง':1,'สอง':2,'สาม':3,'สี่':4,'ห้า':5,'หก':6,'เจ็ด':7,'แปด':8,'เก้า':9,'สิบ':10}

def unit_name(value):
    value=re.sub(r'\s+','',value or '').lower()
    return {'มล':'มล.','มิลลิลิตร':'มล.','ml':'มล.','g':'กรัม','kg':'กิโลกรัม','กก':'กิโลกรัม','กก.':'กิโลกรัม'}.get(value,value)

def find_portion(text):
    match=PORTION.search(text.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789')))
    if not match:return None
    raw=match['number'].strip()
    try:
        if raw in WORDS:quantity=WORDS[raw]
        elif raw.endswith('½'):quantity=float(raw[:-1] or 0)+.5
        elif re.fullmatch(r'\d+\s+\d+\s*/\s*\d+',raw):
            whole,fraction=raw.split(None,1);quantity=float(whole)+float(Fraction(fraction.replace(' ','')))
        else:quantity=float(Fraction(raw.replace(' ','')))
    except (ValueError,ZeroDivisionError):return None
    if match['half']:quantity+=.5
    return {'quantity':quantity,'unit':unit_name(match['unit']), 'span':text[match.start():match.end()],
            'start':match.start(),'end':match.end()}

def strip_portions(text):
    # Do not mutate the original span offsets used for evidence.
    normalized=text.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))
    for match in reversed(list(PORTION.finditer(normalized))):
        # Invalid quantities stay in the label, so they cannot accidentally
        # become a missing amount that defaults to one serving.
        if find_portion(text[match.start():match.end()]):text=text[:match.start()]+text[match.end():]
    return text
