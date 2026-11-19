"""Final v3 report from actual completed artifacts; retain v2 failures."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path): return json.loads((ROOT / path).read_text())


def main():
    train = read('reports/finetune-v3-training.json')
    audit = read('reports/finetune-v3-data-audit.json')
    selected = read('reports/finetune-v3-selection.json')
    base = read('reports/finetune-v3-test-base.json')
    adapted = read('reports/finetune-v3-test-adapter.json')
    registry = read('reports/finetune-v3-rollout.json')
    assert all(r['status'] == 'completed' for r in (train, base, adapted))
    labels = {'extract': 'แยกข้อมูล 7 หมวด', 'route': 'แยกสุขภาพ/นอกประเด็น'}
    lines = ['# ผลรอบแก้จุดอ่อน fine-tuning v3', '',
             f'ฝึกจริงครบ {train["config"]["iters"]} steps จาก {audit["counts"]["train"]} ตัวอย่าง 2passes ใช้ {train["elapsed_seconds"]/60:.2f} นาที peak MLX {train["peak_memory_gb"]:.3f} GB. เริ่มจาก adapter v2 ที่เลือกไว้ (เฉพาะ weights; optimizer/RNG ใหม่) ด้วย LoRA rank16 8layers LR2e-5 batch1 seed42 assistant-only loss.', '',
             f'เลือก checkpoint step {selected["selected_step"]} จาก validation ใหม่ {audit["counts"]["valid"]} ตัวอย่าง ก่อนเปิด test ใหม่ {audit["counts"]["test"]} ตัวอย่าง. ทุก command test สร้างคำตอบจริงใน fresh process เทียบฐาน. เก็บคำตอบและ finish_reason เต็มใน JSON.', '',
             '| งาน | Exact JSON ฐาน | Exact JSON specialist | Loss ฐาน → specialist | เปิดใช้ specialist |',
             '|---|---:|---:|---:|---|']
    for task in ('extract', 'route'):
        b = base['metrics'][task]; a = adapted['metrics'][task]
        gate = registry['specialist_gates'][task]
        lines.append(f'| {labels[task]} | {b["exact"]}/{b["generated_count"]} | {a["exact"]}/{a["generated_count"]} | {b["assistant_loss"]:.4f} → {a["assistant_loss"]:.4f} | {"เปิด" if gate["passed"] else "ใช้ฐานต่อ"} |')
    lines += ['', 'คะแนนเป็น exact JSON บน **synthetic command examples** ไม่ใช่ clinical accuracy หรือความแม่นยำผู้ใช้จริง. เกณฑ์เดิม >=90%, JSON/finish ครบ, ไม่ด้อยกว่าฐาน. จำนวนตัวอย่างยังเล็ก โดยเฉพาะ route และรูปแบบค่าตรวจมีเพียงน้ำหนักแบบ literal.', '',
              '**การใช้ข้อมูลเดิมอย่างโปร่งใส:** v2 validation/test ของ extract และ route ถูกนำมาเป็น development training สำหรับ v3 แล้ว จึงห้ามเรียกชุด v2 ว่า held-out สำหรับ v3. ผล v2 เดิมยังเป็น 24/31 extraction และ 5/6 route ตาม [รายงาน v2](finetune-v2-results.md); ไม่แก้คะแนนเดิมและไม่เทียบเปอร์เซ็นต์ข้ามชุดโดยตรง. ตัวอย่าง v3 test เป็นประโยคและชื่อรายการใหม่ที่แช่แข็งก่อนฝึก.', '',
              'หลังตรวจผ่านเว็บจริงเปิด adapter v2 เฉพาะ intent/menu. journal ได้ 2/2 ในชุดทดสอบเล็ก แต่จัด “รำไทเก๊ก” เป็น meal ผ่านเว็บผิด จึงปิด adapter journal แล้ว ดู [หลักฐาน](finetune-live-smoke-with-journal-adapter.json) และ [สถานะหลังตรวจเว็บ](finetune-operational-rollout.json). extract/route ของ v3 ไม่ผ่านเกณฑ์ จึงไม่เปิดใช้. health_chat ยังใช้โมเดลฐาน+RAG+การตรวจหลักฐาน ไม่เปิดคำตอบแพทย์อิสระจาก adapter เพราะยังไม่มีชุดคำตอบสุขภาพภาษาไทยและการทบทวนทางคลินิกที่เพียงพอ. ไม่เปลี่ยน scheduler/allergy filter/owner/consent/confirmation.', '',
              'ตรวจเว็บพบโมเดลฐานแยกวันเวลา ISO แบบละเอียดไม่สำเร็จและคืนทุกช่องเป็น null; ไม่ได้บันทึกข้อมูลผิดเอง. ตัวอย่าง “เดิน 16.00” และทางบันทึกหลายรายการตามวันที่พิมพ์/ช่วงเช้า–เที่ยงทำงาน. การขอวิธีใช้/เปิดโปรไฟล์ผ่าน learned intent และการเลือกเมนูจาก catalog เรียก adapter จริง. ผลตรวจนี้เป็น software smoke check ไม่ใช่คะแนน held-out/clinical ดู [ผลเว็บ](finetune-live-smoke.json).', '',
              'ตรวจหลังปิด journal adapter แล้ว โมเดลฐานจัด “รำไทเก๊ก” เป็น activity ได้ถูกต้อง จึงคงใช้ฐานสำหรับ fallback งานนี้. ตรวจเซสชันใหม่ผ่านเว็บ 10 กรณี โดยไม่ได้ยืนยันบันทึก/แก้/ลบข้อมูลใด ๆ. การทดสอบอัตโนมัติ Python ผ่าน 161 และส่วนหน้าเว็บผ่าน 14 รวม 175 ข้อ; การทดสอบโปรแกรมไม่ลบล้างข้อผิดพลาดโมเดลที่รายงานไว้.', '',
              'ตัวอย่างใหม่เป็นคำสั่งจับชื่อ/ค่า/ช่วงเวลา ไม่ใช่ผู้ป่วยหรือผลลัพธ์ทางสุขภาพ และไม่ใช้แต่งคำแนะนำแพทย์. ตัวรับข้อมูลตรวจว่าชื่อและตัวเลขมีหลักฐานตรงข้อความเดิม วันเวลาที่ไม่ระบุไม่ให้โมเดลสร้างเอง; journal calendar ยังใช้วันที่พิมพ์/ช่วงเวลาที่บอกตามเดิม.', '',
              'หลักฐาน: [data audit](finetune-v3-data-audit.json), [แผนก่อนฝึกและเกณฑ์ก่อน test](finetune-v3-plan.md), [training](finetune-v3-training.json), [selection](finetune-v3-selection.json), [base test](finetune-v3-test-base.json), [specialist test](finetune-v3-test-adapter.json), [runtime rollout](finetune-v3-rollout.json).', '',
              f'Adapter: `{selected["adapter"]}/adapters.safetensors`, SHA256 `{selected["sha256"]}`. ย้อนกลับได้โดยตั้ง enabled_tasks เป็น [] ใน models/runtime-adapter.json. โมเดลฐาน/pilot/v2 checkpoints ยังอยู่ครบ.', '']
    (ROOT / 'reports/finetune-v3-results.md').write_text('\n'.join(lines))
    folder = ROOT / selected['adapter']
    (folder / 'README.md').write_text('\n'.join(['# ร่วมวัน extraction/route specialist v3', '',
        'Base: typhoon-ai/typhoon2.5-qwen3-4b, quantized 4-bit MLX LoRA. Original model terms apply.',
        'Warm start: selected v2 adapter weights; optimizer/RNG not resumed.',
        'Warm-start v2 used public-domain summaries: Source: MedlinePlus, National Library of Medicine.',
        'Authorized synthetic website/extraction command examples only; no patient records or synthetic medical advice.',
        'v2 extraction/route evaluation data are now training development data. v3 evaluation uses a newly frozen synthetic split.',
        'Not a clinically validated model. Free-form medical chat adapter remains disabled.',
        'Full metrics/limits: reports/finetune-v3-results.md. SHA256: ' + selected['sha256'], '']))
    manifest = read('data/source_manifest.json')
    manifest['sources'] = [s for s in manifest['sources'] if s['id'] != 'synthetic-commands-finetune-v3']
    manifest['sources'].append({'id': 'synthetic-commands-finetune-v3', 'name': 'Authorized extraction/route specialist command examples',
        'creator': 'Coding assistant; user explicitly permitted website/extraction synthetic examples 2026-10-12',
        'url': None, 'status': 'used', 'revision': audit['files'], 'license': 'Project-authored synthetic command labels; base terms apply to adapter',
        'counts': {'training_used': audit['counts']['train'], 'validation': audit['counts']['valid'], 'test': audit['counts']['test']}, 'role': 'Literal extraction and scope classification only',
        'limitations': audit['limitations'] + [audit['split_policy']], 'files': list(audit['files'].values())})
    (ROOT / 'data/source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('Wrote v3 report, adapter card and manifest from completed artifacts')


if __name__ == '__main__': main()
