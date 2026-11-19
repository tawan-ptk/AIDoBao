"""Second run informed by v2 errors, with a newly frozen evaluation split.

The old v2 validation/test commands are now development training data for this
specialist and MUST NOT be called held-out for this run. All rows are synthetic
website/extraction commands explicitly permitted by the user, never medical QA.
"""
import hashlib
import json
from pathlib import Path
import random
import sys
import collections

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.inference import FIELDS, extraction_prompt
from services.chat_routing import classification_messages
from transformers import AutoTokenizer


def main():
    out = ROOT / 'data/prepared/finetune-v3'
    if out.exists(): raise ValueError('Specialist data already frozen')
    splits = {s: [] for s in ('train', 'valid', 'test')}
    for old_split in splits:
        for line in (ROOT / f'data/prepared/finetune-v2/{old_split}.jsonl').read_text().splitlines():
            row = json.loads(line)
            if row['provenance']['task'] not in ('extract', 'route'): continue
            p = row['provenance']
            p.update(split='train', reused_from=f'v2/{old_split}',
                     prior_evaluation_reused_as_training=old_split != 'train')
            splits['train'].append(row)

    def add(split, task, group, messages, target, **meta):
        splits[split].append({'messages': messages + [{'role': 'assistant', 'content': json.dumps(target, ensure_ascii=False, separators=(',', ':'))}],
                              'provenance': {'id': f'synthetic-v3/{task}/{split}/{group}/{len(splits[split])}',
                                             'group': f'v3/{task}/{split}/{group}', 'split': split, 'task': task,
                                             'origin': 'synthetic_command_example', 'language': 'th',
                                             'authorization': 'Explicit user authorization for website/extraction synthetic examples, 2026-10-12',
                                             'not_a_patient': True, 'clinical_advice': False, **meta}})

    names = {
        'meal': {'train': ['ข้าวต้มปลา', 'ผัดผักรวม', 'แกงจืดฟัก', 'ยำแตงกวา', 'ปลาย่าง', 'ข้าวไข่เจียว', 'ส้มตำ', 'ฟักทองนึ่ง'],
                 'valid': ['ข้าวอบเผือก', 'แกงป่าเห็ด'], 'test': ['ข้าวคลุกกะปิ', 'ผัดบวบใส่ไข่', 'ซุปฟักทอง']},
        'activity': {'train': ['รำวง', 'เต้นแอโรบิก', 'ตีปิงปอง', 'เล่นเปตอง', 'เดินขึ้นบันได', 'ยืดแขน', 'หมุนไหล่', 'เตะฟุตบอล'],
                     'valid': ['พายเรือ', 'ตีเทนนิส'], 'test': ['เล่นสเกต', 'รำมวยจีน', 'กระโดดเชือก']},
        'appointment': {'train': ['รับผลตรวจ', 'ปรึกษานักกำหนดอาหาร', 'ตรวจฟัน', 'ติดตามอาการ', 'เจาะเลือด', 'ตรวจจอประสาทตา', 'พบเภสัชกร', 'รับยา'],
                        'valid': ['ตรวจหู', 'ตรวจการได้ยิน'], 'test': ['ตรวจผิวหนัง', 'พบทีมดูแล', 'ปรึกษากายภาพบำบัด']},
        'medication': {'train': ['ยาของมื้อเช้า', 'ยาตามคำสั่งแพทย์', 'ยาตามฉลากเดิม', 'ยาที่รับมาวันนี้', 'ยาตามใบนัด', 'ยากล่องเดิม', 'ยาของมื้อเย็น', 'ยาจากร้านยา'],
                       'valid': ['ยาที่ระบุในเอกสาร', 'ยาจากการนัดครั้งก่อน'], 'test': ['ยาที่เจ้าหน้าที่จ่ายให้', 'ยาที่เตรียมไว้', 'ยาที่รับเมื่อวาน']},
        'wellbeing': {'train': ['สงบ', 'เบิกบาน', 'ตื่นเต้น', 'โล่งใจ', 'สดชื่น', 'เศร้า', 'ขุ่นใจ', 'กระปรี้กระเปร่า'],
                      'valid': ['อิ่มเอม', 'กระตือรือร้น'], 'test': ['ปลอดโปร่ง', 'สบายอารมณ์', 'จิตใจเบาสบาย']},
    }
    templates = {
        'train': ['ช่วยจดรายการเป็น{}', 'บันทึกแค่ชื่อ{}', 'เพิ่ง{}เสร็จ', 'ชื่อรายการที่ต้องการเก็บคือ{}', 'ขอเก็บ{}ไว้'],
        'valid': ['รายการที่ได้ทำไปชื่อ{}', 'เพิ่มรายการชื่อ{}ให้ด้วย'],
        'test': ['สิ่งที่อยากให้บันทึกคือ{}', 'ขอจดไว้เฉพาะรายการ{}นะ'],
    }
    for kind, by_split in names.items():
        field = 'note' if kind == 'wellbeing' else 'name'
        for split, values in by_split.items():
            for ti, template in enumerate(templates[split]):
                for value in values:
                    text = template.format(value)
                    data = dict.fromkeys(FIELDS[kind]); data[field] = value
                    add(split, 'extract', f'{kind}/{ti}', [{'role': 'system', 'content': extraction_prompt(kind)}, {'role': 'user', 'content': text}],
                        {'data': data, 'evidence': {field: value}}, kind=kind)
    for split, tokens in {'train': ['64.3', '81.7', '95.2', '60.8', '73.1', '88.4'], 'valid': ['62.9', '79.6'], 'test': ['69.7', '84.1', '57.2']}.items():
        for value in tokens:
            text = {'train': f'จดค่าน้ำหนัก {value} กิโลกรัม', 'valid': f'น้ำหนักที่ต้องบันทึกคือ {value} kg', 'test': f'ช่วยเก็บค่าน้ำหนักเป็น {value} กก.'}[split]
            data = dict.fromkeys(FIELDS['measurement']); data.update(name='weight', value=float(value), unit='kg')
            add(split, 'extract', 'measurement', [{'role': 'system', 'content': extraction_prompt('measurement')}, {'role': 'user', 'content': text}],
                {'data': data, 'evidence': {'name': 'น้ำหนัก', 'value': value, 'unit': text.split()[-1]}}, kind='measurement')
    for split, queries in {
        'train': ['จดว่านอนตอนสามทุ่ม', 'เข้านอนตีหนึ่ง', 'เก็บรายการนอนกลางคืน', 'นอนหลังเที่ยงคืน', 'งีบไปแล้ว', 'นอนตั้งแต่ 21:00 ถึง 05:30'],
        'valid': ['ขอจดเวลานอนตอนห้าทุ่ม', 'เข้านอนเวลา 20.30'],
        'test': ['เก็บการนอนเมื่อคืนช่วงสี่ทุ่ม', 'จดไว้ว่าฉันงีบช่วงเที่ยง', 'นอนตั้งแต่ 20:45 ถึง 04:15'],
    }.items():
        for i, text in enumerate(queries):
            add(split, 'extract', f'sleep/{i}', [{'role': 'system', 'content': extraction_prompt('sleep')}, {'role': 'user', 'content': text}],
                {'data': dict.fromkeys(FIELDS['sleep']), 'evidence': {}}, kind='sleep')
    routes = {
        'train': [('สร้างเกมเกี่ยวกับเบาหวาน', None), ('ช่วยแต่งนิยายโรงพยาบาล', None), ('ราคาหุ้นบริษัทขายยา', None), ('เขียนโค้ดคำนวณสุขภาพ', None), ('ทำเว็บไซต์ลดน้ำหนัก', None), ('เขียนเพลงชื่อโรคหัวใจ', None),
                  ('สุขภาพคืออะไร', 'health'), ('ปวดหัวเกิดจากอะไร', 'headache'), ('ช่วยอธิบายเรื่องการนอน', 'sleep'), ('ขอความรู้เรื่องอาหาร', 'nutrition'), ('โรคเบาหวานเกี่ยวกับอะไร', 'diabetes'), ('ค่าน้ำตาลในเลือดคืออะไร', 'blood glucose')],
        'valid': [('สอนเขียนแอปเบาหวาน', None), ('แต่งบทละครแพทย์ให้หน่อย', None), ('อาการเจ็บหัวเกิดจากอะไร', 'headache'), ('นอนหลับช่วยอะไรบ้าง', 'sleep')],
        'test': [('ช่วยเขียนโปรแกรมจัดอาหารสำหรับเบาหวาน', None), ('ขอเรื่องสั้นเกี่ยวกับหมอ', None), ('ลงทุนในโรงพยาบาลไหนดี', None), ('ดอกกุหลาบมีกี่สี', None),
                 ('อธิบายประโยชน์ของการนอนหลับ', 'sleep'), ('อาหารประเภทใดมีคาร์บ', 'nutrition'), ('ทำไมน้ำตาลในเลือดจึงสำคัญ', 'blood glucose'), ('เบาหวานชนิดที่สองเกิดจากอะไร', 'diabetes')],
    }
    for split, queries in routes.items():
        for i, (query, topic) in enumerate(queries):
            add(split, 'route', str(i), classification_messages(query), {'route': 'health' if topic else 'out_of_scope', 'topic': topic})
    tokenizer = AutoTokenizer.from_pretrained(ROOT / 'models/typhoon-4bit', local_files_only=True)
    out.mkdir()
    files = {}
    for split, rows in splits.items():
        random.Random(912).shuffle(rows)
        for row in rows:
            row['provenance']['tokens'] = len(tokenizer.apply_chat_template(row['messages'], tokenize=True, return_dict=False))
            assert row['provenance']['tokens'] <= 1024
        path = out / f'{split}.jsonl'
        path.write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in rows) + '\n')
        files[split] = {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    audit = {'counts': {s: len(rs) for s, rs in splits.items()}, 'files': files,
             'tasks': {s: dict(collections.Counter(r['provenance']['task'] for r in rs)) for s, rs in splits.items()},
             'origin': 'authorized_synthetic_commands_only',
             'split_policy': 'v2 command train/valid/test now ALL development training; v3 validation/test use newly authored phrasings and lexical fillers. Never describe v2 test as held-out for v3.',
             'max_context': 1024, 'truncated_answers': 0,
             'limitations': ['Synthetic command evaluation only; no clinical/real-user accuracy.', 'Measurement supports literal weight examples, not a representative medical measurements dataset.']}
    (out / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    (ROOT / 'reports/finetune-v3-data-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    print(json.dumps(audit['counts']))


if __name__ == '__main__': main()
