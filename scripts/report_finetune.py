"""Render a Thai report/card/manifest strictly from completed run artifacts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(name): return json.loads((ROOT / name).read_text())


def main():
    training = read('reports/finetune-v2-training.json')
    audit = read('reports/finetune-v2-data-audit.json')
    selection = read('reports/finetune-v2-selection.json')
    base = read('reports/finetune-v2-test-base.json')
    adapter = read('reports/finetune-v2-test-adapter.json')
    rollout = read('reports/finetune-v2-rollout.json')
    assert all(r.get('status') == 'completed' for r in (training, base, adapter))
    from scripts.inference import parse_extraction
    field_scores = {}
    for label, report in [('base', base), ('adapter', adapter)]:
        cases = [g for g in report['generations'] if g['task'] == 'extract']
        correct_records = 0; correct_fields = 0; total_fields = 0; invalid = 0
        for case in cases:
            target = json.loads(case['reference'])['data']
            try:
                actual, _ = parse_extraction(case['answer'], case['kind'], case['messages'][-1]['content'])
                correct_records += actual == target
                correct_fields += sum(actual[key] == value for key, value in target.items())
            except (ValueError, TypeError, KeyError): invalid += 1
            total_fields += len(target)
        field_scores[label] = {'cases': len(cases), 'all_data_fields_match_after_validation': correct_records,
                               'correct_fields': correct_fields, 'total_fields': total_fields,
                               'invalid_envelope': invalid, 'scope': 'Synthetic command test only; includes null fields; not clinical accuracy'}
    (ROOT / 'reports/finetune-v2-extraction-fields.json').write_text(json.dumps(field_scores, indent=2))
    labels = {'extract': 'แยกข้อมูล 7 หมวด', 'intent': 'เข้าใจคำสั่งใช้เว็บ', 'route': 'แยกสุขภาพ/นอกประเด็น',
              'journal': 'จำแนกบันทึกหลายหมวด', 'menu': 'เลือก ID เมนูที่อนุญาต', 'health_qa': 'คำตอบสุขภาพอังกฤษต้นฉบับ'}
    lines = ['# ผล fine-tuning หลายงาน — 12 ตุลาคม 2026', '',
             f'ฝึกจริงเสร็จ {training["config"]["iters"]} steps (2 passes) จาก {audit["counts"]["train"]} ตัวอย่างใน {training["elapsed_seconds"] / 60:.2f} นาที เฉพาะ process การฝึกหลัก; peak MLX {training["peak_memory_gb"]:.3f} GB.', '',
             'โมเดล Typhoon2.5-Qwen3-4B ฐาน 4-bit เดิม, MLX-LM 0.32.0, LoRA rank 16 ใน 8 layers, batch 1, LR 5e-5, assistant-only loss, seed 42. เปลี่ยนพารามิเตอร์ LoRA 7.340 ล้านตัว ไม่ใช่ full-parameter training. เก็บโมเดลฐานและ pilot เดิมไว้ครบ.', '',
             'ชุดฝึก 302 = original English MedlinePlus QA 53 + synthetic website/extraction command examples 249 ที่ผู้ใช้อนุญาตอย่างชัดเจน. Validation 77, test 86; test คำสั่งสังเคราะห์ 79 ตัวอย่างสร้างคำตอบครบทุกข้อ ส่วน English QA ทั้ง 7 ข้อใช้วัด loss และเลือกบางข้อด้วย seed คงที่เพื่อดูข้อความจริง ไม่มีคำตอบสุขภาพ/ประวัติผู้ป่วยที่ AI แต่ง ไม่มี app records หรือ software fixtures ในชุดฝึก.', '',
             f'เลือก checkpoint step {selection["selected_step"]} จาก validation ก่อนเปิด test. เกณฑ์และค่าผู้สมัครอยู่ใน [selection](finetune-v2-selection.json). ประเมิน checkpoint หลังบันทึกใน process ใหม่; ไม่ใช้ validation ที่ trainer แสดงก่อน optimizer step แทนผล checkpoint.', '',
             '| งาน | ตัวอย่าง test ที่สร้างคำตอบ | Exact JSON ฐาน | Exact JSON หลังฝึก | Loss ฐาน → หลังฝึก | เปิดใช้ adapter |',
             '|---|---:|---:|---:|---:|---|']
    for task in ('extract', 'intent', 'route', 'journal', 'menu', 'health_qa'):
        b = base['metrics'][task]; a = adapter['metrics'][task]
        exact_b = f'{b["exact"]}/{b["generated_count"]}' if task != 'health_qa' else 'ไม่วัดด้วย JSON'
        exact_a = f'{a["exact"]}/{a["generated_count"]}' if task != 'health_qa' else 'ไม่วัดด้วย JSON'
        lines.append(f'| {labels[task]} | {a["generated_count"]} | {exact_b} | {exact_a} | {b["assistant_loss"]:.4f} → {a["assistant_loss"]:.4f} | {"เปิด" if task in rollout["enabled_tasks"] else "ใช้ฐานต่อ"} |')
    health = [g for g in adapter['generations'] if g['task'] == 'health_qa']
    lines += ['', '**คะแนนคำสั่งเป็นการวัดตัวอย่างสังเคราะห์ที่แยกไว้ ไม่ใช่ความแม่นยำผู้ใช้จริงหรือความถูกต้องทางคลินิก** จำนวนตัวอย่างแต่ละงานยังเล็ก โดยเฉพาะ journal/menu/route. Exact หมายถึง JSON ทุกช่องตรง target โดยไม่คิดลำดับ key. Loss เป็นค่า assistant token loss ไม่ใช่อัตราตอบถูก.', '',
              f'เมื่อตรวจด้วยตัวรับข้อมูลจริงและวัดเฉพาะ data ทุกช่อง โดยไม่บังคับ evidence ต้องมีรูปข้อความเหมือน target: ฐานตรงครบ {field_scores["base"]["all_data_fields_match_after_validation"]}/{field_scores["base"]["cases"]}, หลังฝึก {field_scores["adapter"]["all_data_fields_match_after_validation"]}/{field_scores["adapter"]["cases"]}. เป็นการวิเคราะห์เพิ่มเติม ไม่ใช้เลือก checkpoint หรือเปลี่ยนเกณฑ์เปิด adapter ดู [field scores](finetune-v2-extraction-fields.json).', '',
              f'คำตอบสุขภาพอังกฤษที่สร้างจริง {len(health)} ข้อ มี {sum(g["finish_reason"] == "length" for g in health)} ข้อชนเพดาน 384 tokens. เก็บคำตอบเต็มและ finish_reason ทุกข้อไว้ใน [ผล adapter](finetune-v2-test-adapter.json) และ [ผลฐาน](finetune-v2-test-base.json). ยังรอมนุษย์/ผู้เชี่ยวชาญประเมินเนื้อหา ไม่ใช้ค่า loss ตัดสินทางคลินิก.', '',
              'เปิด adapter เฉพาะงานที่ผ่านเกณฑ์ที่กำหนดก่อน test (JSON ครบ, จบสมบูรณ์, exact >=90%, ไม่ต่ำกว่าฐาน) ใน [rollout](finetune-v2-rollout.json). runtime ตรวจ SHA256 ของ weights และจำกัดชนิดงาน; health_chat ยังใช้ base + หลักฐานค้นได้ + การตรวจคำตอบเดิม. เจตนาที่โมเดลจำแนกได้ไม่ให้สิทธิขยายขอบเขตสุขภาพ/รัน SQL/ลบข้อมูลเอง.', '',
              'เวลาบันทึกช่วงเช้า/บ่าย/วันที่พิมพ์ใช้ journal calendar ของโปรแกรม; legacy extraction เว้นวันเวลาที่ไม่ระบุไว้เป็น null. เพิ่มตัวตรวจชื่อ/ค่าตัวเลข/วันเวลาให้ตรงหลักฐานเพื่อกันโมเดลใช้ substring ที่ไม่เกี่ยวข้องรองรับค่าที่แต่งขึ้น. Scheduler, allergy filter, consent และการยืนยันแก้/ลบยังทำด้วยโปรแกรมเดิม.', '',
              'ข้อจำกัด: ไม่มีชุดคำตอบสุขภาพภาษาไทยที่มนุษย์ตรวจสำหรับการฝึก; ยังไม่ผ่าน clinical validation; public-source pretraining overlap ไม่ทราบ; ตัวอย่าง ISO date ใช้รูปประโยคร่วมข้าม split โดยเปลี่ยนวันตามที่ระบุในแผน จึงวัดการคัดลอก slot ไม่ใช่รูปประโยคใหม่ทั้งหมด. การฝึกไม่ได้สอนให้โมเดลคำนวณตาราง/แคลอรีหรือเปลี่ยนการรักษาเอง.', '',
              'ที่มา: [MedlinePlus health-topic summaries และนโยบายใช้เนื้อหา](https://medlineplus.gov/about/using/usingcontent/). Source: MedlinePlus, National Library of Medicine. ใช้เฉพาะ summary text ไม่รวม Encyclopedia, Drug Monographs, รูป หรือเนื้อหาภายนอก. เก็บ source HTML/URL/hash/location ใน provenance ทุกแถว.', '',
              'ข้อมูล: [audit](finetune-v2-data-audit.json), [แผนก่อนฝึก/เกณฑ์ก่อนทดสอบ](finetune-v2-plan.md), [บันทึกฝึกจริง](finetune-v2-training.json). Adapter ที่เลือก: `adapters/finetune-v2-selected/adapters.safetensors`. Rollback: ตั้ง `models/runtime-adapter.json` ให้ `enabled_tasks: []`; worker ใหม่จะใช้ฐานทันที.', '']
    (ROOT / 'reports/finetune-v2-results.md').write_text('\n'.join(lines))
    selected = ROOT / selection['adapter']
    card = '\n'.join(['# ร่วมวัน multitask LoRA v2', '', 'Engineering adapter, not a clinically validated medical model.',
                      'Base: typhoon-ai/typhoon2.5-qwen3-4b revision ce0a7416fe82d4404b2b4a253ce3ac095ab1252c; original model terms apply.',
                      'Source: MedlinePlus, National Library of Medicine. Public-domain health-topic summaries only.',
                      '249 synthetic command examples authorized by the user; 53 original English source QA. No app records or synthetic medical advice.',
                      f'Selected checkpoint: {selection["selected_step"]}; SHA256: {selection["sha256"]}.',
                      'Runtime tasks enabled: ' + ', '.join(rollout['enabled_tasks']),
                      'Free-form health_chat adapter disabled pending adequate Thai and clinical evaluation.',
                      'See reports/finetune-v2-results.md and reports/finetune-v2-data-audit.json for metrics and limits.', ''])
    (selected / 'README.md').write_text(card)
    (selected / 'source-policy.html').write_bytes((ROOT / 'data/raw/finetune-v1/usingcontent-policy.html').read_bytes())
    manifest = read('data/source_manifest.json')
    manifest['sources'] = [s for s in manifest['sources'] if s['id'] not in ('medlineplus-finetune-v2', 'synthetic-commands-finetune-v2')]
    manifest['sources'].extend([
        {'id': 'medlineplus-finetune-v2', 'name': 'MedlinePlus current summary original QA',
         'creator': 'National Library of Medicine / source federal agencies', 'url': 'https://medlineplus.gov/',
         'revision': 'SHA256 snapshots in data/raw/finetune-v1/downloads.json', 'status': 'used',
         'license': 'US federal public-domain health-topic summaries only',
         'permissions': {'download_process': True, 'training': True, 'rag': True, 'redistribute_data': 'with source acknowledgement', 'redistribute_adapter': 'retain base terms and source acknowledgement'},
         'role': 'Original English QA, no AI translation/paraphrase',
         'counts': {'training_used': 53, 'validation': 12, 'test': 7},
         'limitations': ['Not clinician reviewed; no Thai medical paired answers; no real-user accuracy claim'],
         'files': [v for v in read('data/raw/finetune-v1/downloads.json').values()]},
        {'id': 'synthetic-commands-finetune-v2', 'name': 'Authorized Thai website/extraction command examples',
         'creator': 'Coding assistant with explicit user authorization 2026-10-12', 'url': None, 'status': 'used',
         'revision': audit['files'], 'license': 'Project-authored synthetic commands; no third-party patient data',
         'permissions': {'download_process': True, 'training': True, 'rag': False, 'redistribute_data': True, 'redistribute_adapter': 'base terms apply'},
         'counts': {'training_used': 249, 'validation': 65, 'test': 79},
         'role': 'Literal extraction and intent/catalog labels only; no synthetic medical advice',
         'limitations': ['Not real patients; not evidence of clinical accuracy; held-out date templates share structure'],
         'files': list(audit['files'].values())}])
    (ROOT / 'data/source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('Wrote results, adapter card, and source manifest from completed runs')


if __name__ == '__main__': main()
