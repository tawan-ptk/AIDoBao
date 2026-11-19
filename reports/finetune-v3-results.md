# ผลรอบแก้จุดอ่อน fine-tuning v3

ฝึกจริงครบ 914 steps จาก 457 ตัวอย่าง 2passes ใช้ 17.66 นาที peak MLX 3.817 GB. เริ่มจาก adapter v2 ที่เลือกไว้ (เฉพาะ weights; optimizer/RNG ใหม่) ด้วย LoRA rank16 8layers LR2e-5 batch1 seed42 assistant-only loss.

เลือก checkpoint step 914 จาก validation ใหม่ 28 ตัวอย่าง ก่อนเปิด test ใหม่ 44 ตัวอย่าง. ทุก command test สร้างคำตอบจริงใน fresh process เทียบฐาน. เก็บคำตอบและ finish_reason เต็มใน JSON.

| งาน | Exact JSON ฐาน | Exact JSON specialist | Loss ฐาน → specialist | เปิดใช้ specialist |
|---|---:|---:|---:|---|
| แยกข้อมูล 7 หมวด | 0/36 | 29/36 | 0.6231 → 0.0356 | ใช้ฐานต่อ |
| แยกสุขภาพ/นอกประเด็น | 6/8 | 7/8 | 1.0684 → 0.0235 | ใช้ฐานต่อ |

คะแนนเป็น exact JSON บน **synthetic command examples** ไม่ใช่ clinical accuracy หรือความแม่นยำผู้ใช้จริง. เกณฑ์เดิม >=90%, JSON/finish ครบ, ไม่ด้อยกว่าฐาน. จำนวนตัวอย่างยังเล็ก โดยเฉพาะ route และรูปแบบค่าตรวจมีเพียงน้ำหนักแบบ literal.

**การใช้ข้อมูลเดิมอย่างโปร่งใส:** v2 validation/test ของ extract และ route ถูกนำมาเป็น development training สำหรับ v3 แล้ว จึงห้ามเรียกชุด v2 ว่า held-out สำหรับ v3. ผล v2 เดิมยังเป็น 24/31 extraction และ 5/6 route ตาม [รายงาน v2](finetune-v2-results.md); ไม่แก้คะแนนเดิมและไม่เทียบเปอร์เซ็นต์ข้ามชุดโดยตรง. ตัวอย่าง v3 test เป็นประโยคและชื่อรายการใหม่ที่แช่แข็งก่อนฝึก.

หลังตรวจผ่านเว็บจริงเปิด adapter v2 เฉพาะ intent/menu. journal ได้ 2/2 ในชุดทดสอบเล็ก แต่จัด “รำไทเก๊ก” เป็น meal ผ่านเว็บผิด จึงปิด adapter journal แล้ว ดู [หลักฐาน](finetune-live-smoke-with-journal-adapter.json) และ [สถานะหลังตรวจเว็บ](finetune-operational-rollout.json). extract/route ของ v3 ไม่ผ่านเกณฑ์ จึงไม่เปิดใช้. health_chat ยังใช้โมเดลฐาน+RAG+การตรวจหลักฐาน ไม่เปิดคำตอบแพทย์อิสระจาก adapter เพราะยังไม่มีชุดคำตอบสุขภาพภาษาไทยและการทบทวนทางคลินิกที่เพียงพอ. ไม่เปลี่ยน scheduler/allergy filter/owner/consent/confirmation.

ตรวจเว็บพบโมเดลฐานแยกวันเวลา ISO แบบละเอียดไม่สำเร็จและคืนทุกช่องเป็น null; ไม่ได้บันทึกข้อมูลผิดเอง. ตัวอย่าง “เดิน 16.00” และทางบันทึกหลายรายการตามวันที่พิมพ์/ช่วงเช้า–เที่ยงทำงาน. การขอวิธีใช้/เปิดโปรไฟล์ผ่าน learned intent และการเลือกเมนูจาก catalog เรียก adapter จริง. ผลตรวจนี้เป็น software smoke check ไม่ใช่คะแนน held-out/clinical ดู [ผลเว็บ](finetune-live-smoke.json).

ตรวจหลังปิด journal adapter แล้ว โมเดลฐานจัด “รำไทเก๊ก” เป็น activity ได้ถูกต้อง จึงคงใช้ฐานสำหรับ fallback งานนี้. ตรวจเซสชันใหม่ผ่านเว็บ 10 กรณี โดยไม่ได้ยืนยันบันทึก/แก้/ลบข้อมูลใด ๆ. การทดสอบอัตโนมัติ Python ผ่าน 161 และส่วนหน้าเว็บผ่าน 14 รวม 175 ข้อ; การทดสอบโปรแกรมไม่ลบล้างข้อผิดพลาดโมเดลที่รายงานไว้.

ตัวอย่างใหม่เป็นคำสั่งจับชื่อ/ค่า/ช่วงเวลา ไม่ใช่ผู้ป่วยหรือผลลัพธ์ทางสุขภาพ และไม่ใช้แต่งคำแนะนำแพทย์. ตัวรับข้อมูลตรวจว่าชื่อและตัวเลขมีหลักฐานตรงข้อความเดิม วันเวลาที่ไม่ระบุไม่ให้โมเดลสร้างเอง; journal calendar ยังใช้วันที่พิมพ์/ช่วงเวลาที่บอกตามเดิม.

หลักฐาน: [data audit](finetune-v3-data-audit.json), [แผนก่อนฝึกและเกณฑ์ก่อน test](finetune-v3-plan.md), [training](finetune-v3-training.json), [selection](finetune-v3-selection.json), [base test](finetune-v3-test-base.json), [specialist test](finetune-v3-test-adapter.json), [runtime rollout](finetune-v3-rollout.json).

Adapter: `adapters/finetune-v3-selected/adapters.safetensors`, SHA256 `b6c80b3b5f19106490201e7f503b03f24986a78d1096369c58f13140533e0027`. ย้อนกลับได้โดยตั้ง enabled_tasks เป็น [] ใน models/runtime-adapter.json. โมเดลฐาน/pilot/v2 checkpoints ยังอยู่ครบ.
