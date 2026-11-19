# ผล fine-tuning หลายงาน — 12 ตุลาคม 2026

**มีรอบติดตามแล้ว:** [ผล v3 จำนวน 914 steps](finetune-v3-results.md) ใช้ชุดทดสอบใหม่และยังไม่ผ่านเกณฑ์ extract/route ปัจจุบันเปิดเฉพาะ intent/menu จาก v2 ส่วน journal แม้ผ่านชุดทดสอบเล็กด้านล่าง แต่ปิดหลังตรวจผ่านเว็บพบว่า “รำไทเก๊ก” ถูกจัดเป็นอาหาร ดู [หลักฐานจริง](finetune-live-smoke-with-journal-adapter.json) และ [สถานะหลังตรวจเว็บ](finetune-operational-rollout.json) ผลด้านล่างเป็นผล v2 เดิม ไม่เปลี่ยนคะแนนย้อนหลัง

ฝึกจริงเสร็จ 604 steps (2 passes) จาก 302 ตัวอย่างใน 10.99 นาที เฉพาะ process การฝึกหลัก; peak MLX 3.795 GB.

โมเดล Typhoon2.5-Qwen3-4B ฐาน 4-bit เดิม, MLX-LM 0.32.0, LoRA rank 16 ใน 8 layers, batch 1, LR 5e-5, assistant-only loss, seed 42. เปลี่ยนพารามิเตอร์ LoRA 7.340 ล้านตัว ไม่ใช่ full-parameter training. เก็บโมเดลฐานและ pilot เดิมไว้ครบ.

ชุดฝึก 302 = original English MedlinePlus QA 53 + synthetic website/extraction command examples 249 ที่ผู้ใช้อนุญาตอย่างชัดเจน. Validation 77, test 86; test คำสั่งสังเคราะห์ 79 ตัวอย่างสร้างคำตอบครบทุกข้อ ส่วน English QA ทั้ง 7 ข้อใช้วัด loss และเลือกบางข้อด้วย seed คงที่เพื่อดูข้อความจริง ไม่มีคำตอบสุขภาพ/ประวัติผู้ป่วยที่ AI แต่ง ไม่มี app records หรือ software fixtures ในชุดฝึก.

เลือก checkpoint step 604 จาก validation ก่อนเปิด test. เกณฑ์และค่าผู้สมัครอยู่ใน [selection](finetune-v2-selection.json). ประเมิน checkpoint หลังบันทึกใน process ใหม่; ไม่ใช้ validation ที่ trainer แสดงก่อน optimizer step แทนผล checkpoint.

| งาน | ตัวอย่าง test ที่สร้างคำตอบ | Exact JSON ฐาน | Exact JSON หลังฝึก | Loss ฐาน → หลังฝึก | เปิดใช้ adapter |
|---|---:|---:|---:|---:|---|
| แยกข้อมูล 7 หมวด | 31 | 0/31 | 24/31 | 0.4530 → 0.0263 | ใช้ฐานต่อ |
| เข้าใจคำสั่งใช้เว็บ | 36 | 36/36 | 36/36 | 1.1257 → 0.0013 | เปิด |
| แยกสุขภาพ/นอกประเด็น | 6 | 5/6 | 5/6 | 1.0613 → 0.0735 | ใช้ฐานต่อ |
| จำแนกบันทึกหลายหมวด | 2 | 2/2 | 2/2 | 0.4011 → 0.0068 | เปิด |
| เลือก ID เมนูที่อนุญาต | 4 | 4/4 | 4/4 | 1.1405 → 0.0002 | เปิด |
| คำตอบสุขภาพอังกฤษต้นฉบับ | 4 | ไม่วัดด้วย JSON | ไม่วัดด้วย JSON | 2.2811 → 1.7916 | ใช้ฐานต่อ |

**คะแนนคำสั่งเป็นการวัดตัวอย่างสังเคราะห์ที่แยกไว้ ไม่ใช่ความแม่นยำผู้ใช้จริงหรือความถูกต้องทางคลินิก** จำนวนตัวอย่างแต่ละงานยังเล็ก โดยเฉพาะ journal/menu/route. Exact หมายถึง JSON ทุกช่องตรง target โดยไม่คิดลำดับ key. Loss เป็นค่า assistant token loss ไม่ใช่อัตราตอบถูก.

เมื่อตรวจด้วยตัวรับข้อมูลจริงและวัดเฉพาะ data ทุกช่อง โดยไม่บังคับ evidence ต้องมีรูปข้อความเหมือน target: ฐานตรงครบ 8/31, หลังฝึก 24/31. เป็นการวิเคราะห์เพิ่มเติม ไม่ใช้เลือก checkpoint หรือเปลี่ยนเกณฑ์เปิด adapter ดู [field scores](finetune-v2-extraction-fields.json).

คำตอบสุขภาพอังกฤษที่สร้างจริง 4 ข้อ มี 1 ข้อชนเพดาน 384 tokens. เก็บคำตอบเต็มและ finish_reason ทุกข้อไว้ใน [ผล adapter](finetune-v2-test-adapter.json) และ [ผลฐาน](finetune-v2-test-base.json). ยังรอมนุษย์/ผู้เชี่ยวชาญประเมินเนื้อหา ไม่ใช้ค่า loss ตัดสินทางคลินิก.

เปิด adapter เฉพาะงานที่ผ่านเกณฑ์ที่กำหนดก่อน test (JSON ครบ, จบสมบูรณ์, exact >=90%, ไม่ต่ำกว่าฐาน) ใน [rollout](finetune-v2-rollout.json). runtime ตรวจ SHA256 ของ weights และจำกัดชนิดงาน; health_chat ยังใช้ base + หลักฐานค้นได้ + การตรวจคำตอบเดิม. เจตนาที่โมเดลจำแนกได้ไม่ให้สิทธิขยายขอบเขตสุขภาพ/รัน SQL/ลบข้อมูลเอง.

เวลาบันทึกช่วงเช้า/บ่าย/วันที่พิมพ์ใช้ journal calendar ของโปรแกรม; legacy extraction เว้นวันเวลาที่ไม่ระบุไว้เป็น null. เพิ่มตัวตรวจชื่อ/ค่าตัวเลข/วันเวลาให้ตรงหลักฐานเพื่อกันโมเดลใช้ substring ที่ไม่เกี่ยวข้องรองรับค่าที่แต่งขึ้น. Scheduler, allergy filter, consent และการยืนยันแก้/ลบยังทำด้วยโปรแกรมเดิม.

ข้อจำกัด: ไม่มีชุดคำตอบสุขภาพภาษาไทยที่มนุษย์ตรวจสำหรับการฝึก; ยังไม่ผ่าน clinical validation; public-source pretraining overlap ไม่ทราบ; ตัวอย่าง ISO date ใช้รูปประโยคร่วมข้าม split โดยเปลี่ยนวันตามที่ระบุในแผน จึงวัดการคัดลอก slot ไม่ใช่รูปประโยคใหม่ทั้งหมด. การฝึกไม่ได้สอนให้โมเดลคำนวณตาราง/แคลอรีหรือเปลี่ยนการรักษาเอง.

ที่มา: [MedlinePlus health-topic summaries และนโยบายใช้เนื้อหา](https://medlineplus.gov/about/using/usingcontent/). Source: MedlinePlus, National Library of Medicine. ใช้เฉพาะ summary text ไม่รวม Encyclopedia, Drug Monographs, รูป หรือเนื้อหาภายนอก. เก็บ source HTML/URL/hash/location ใน provenance ทุกแถว.

ข้อมูล: [audit](finetune-v2-data-audit.json), [แผนก่อนฝึก/เกณฑ์ก่อนทดสอบ](finetune-v2-plan.md), [บันทึกฝึกจริง](finetune-v2-training.json). Adapter ที่เลือก: `adapters/finetune-v2-selected/adapters.safetensors`. Rollback: ตั้ง `models/runtime-adapter.json` ให้ `enabled_tasks: []`; worker ใหม่จะใช้ฐานทันที.
