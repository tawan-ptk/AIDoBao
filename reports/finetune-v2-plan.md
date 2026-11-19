# แผนการฝึกที่กำหนดก่อนเปิดผลทดสอบ

เริ่มเตรียมรอบนี้ 12 ตุลาคม 2026 ใช้โมเดล Typhoon2.5-Qwen3-4B ฐาน 4-bit เดิม MLX-LM 0.32.0 บน Mac เครื่องนี้ ไม่เริ่มจาก adapter pilot เก่า

ผู้ใช้อนุญาตในแชตให้สร้างตัวอย่างสำหรับงานใช้เว็บและแยกบันทึก ตัวอย่างเหล่านี้เป็นคำสั่งสังเคราะห์ ไม่ใช่ข้อมูลผู้ป่วย ไม่ใช่คำตอบสุขภาพจากแพทย์ ไม่ใช้บันทึกส่วนตัวหรือ software fixtures ฝึก คำตอบสุขภาพมาจากหัวข้อ Summary ของ MedlinePlus ต้นฉบับภาษาอังกฤษ ใช้เฉพาะคำถาม h3 และคำตอบที่ตามติดในหัวข้อเดียวกัน ไม่แปล ไม่ paraphrase ไม่ใช้ Encyclopedia/Drug Monographs/รูปภาพ/ลิงก์ภายนอก

แหล่งและสิทธิ: [MedlinePlus public-domain health-topic summaries](https://medlineplus.gov/about/using/usingcontent/) ระบุเครดิต Source: MedlinePlus, National Library of Medicine. เก็บ HTML, URL, วันเข้าถึง, SHA256 และตำแหน่งคำถามไว้ใน data/raw/finetune-v1 และ provenance ทุกแถว การจับคู่กับข้อความต้นฉบับเป็นการตรวจที่มาของข้อมูล ไม่ใช่การทบทวนทางคลินิก

ชุดฝึก 302 ตัวอย่าง ชุด validation 77 และ test 86 งาน: extraction 7 หมวด, intent 12 แบบ, health/out-of-scope route, multi-category journal classification, constrained menu selection และ original English health QA. ชุดฝึกประกอบด้วย original QA 53 + synthetic command examples 249 รายการ ไม่อ้างว่ามี 302 ตัวอย่างข้อมูลทางการแพทย์จริง

แยก original QA ตามหน้าเอกสาร แยกประโยคคำสั่งและชื่อรายการสำหรับงาน extraction ส่วนกรณี timestamp ISO ใช้โครงประโยคเดียวข้าม split โดยเปลี่ยนวันเพื่อทดสอบการคัดลอก literal date โดยเจตนา จึงไม่ใช่การทดสอบรูปประโยคใหม่ทั้งหมด มีทั้งกรณีข้อมูลขาดและกรณีระบุวันเวลา/ปริมาณครบ ไม่ตัดคำตอบเกิน context ตัวอย่างยาวสุด 405 tokens; train context 1024

Pilot ใหม่ 20 steps, LoRA rank 16, 8 layers, batch 1, LR 5e-5 สำเร็จ 133.60 วินาที peak MLX 3.602 GB. validation ทั้งหมดสองครั้งใช้เวลารวมประมาณ 108 วินาที ส่วนการฝึกประมาณ 26 วินาที จึงกำหนดรอบหลัก 604 steps = 2 passes ของข้อมูล 302 แถว ใช้ monitoring validation 16 batches ระหว่างฝึก แต่ประเมิน candidate บน validation ทั้งหมดภายหลัง ผล pilot ไม่เป็น candidate สำหรับ deployment

Candidate ที่กำหนดล่วงหน้า: checkpoint 302 และ 604. ประเมินทั้งสองและ base ใน process ใหม่ด้วย validation เท่านั้น เลือกจากจำนวน structured exact matches ในชุด validation ที่กำหนดด้วย seed 724 ก่อน หากเท่ากันเลือกค่าเฉลี่ย assistant loss รายงานของงานต่าง ๆ ต่ำกว่า ไม่ใช้ test เลือก checkpoint การวัด validation ใน trainer อยู่ก่อน optimizer step จึงไม่จับ loss ที่พิมพ์ระหว่างฝึกไปอ้างว่าเป็น loss ของ checkpoint หลัง step

หลังเลือกแล้วจึงประเมิน base และ selected adapter บน test: loss ทุกแถว, generation ทุกตัวอย่างคำสั่งสังเคราะห์, generation English QA บางข้อที่กำหนดด้วย seed เดิม คะแนน exact JSON เป็นความสามารถบนตัวอย่างสังเคราะห์ ไม่ใช่ความแม่นยำผู้ใช้จริง/ทางการแพทย์

เกณฑ์เปิด adapter แยกงาน: ทุก command generation ต้องจบสมบูรณ์ JSON ถูกต้อง, exact match >= 90%, และไม่ด้อยกว่า base ในงานเดียวกัน งาน extraction ต้องครบอย่างน้อย 7 หมวด; งาน intent ต้องมีอย่างน้อย 20 ตัวอย่าง; route อย่างน้อย 6; menu อย่างน้อย 4; journal อย่างน้อย 2. จำนวนนี้ยังเล็กสำหรับ production และรายงานตามจริง การเปิดเป็น engineering rollout พร้อม fallback ไม่ใช่การรับรองทั่วไป

ไม่เปิด adapter สำหรับ free-form health_chat จากคะแนนภาษาอังกฤษหรือ loss เพียงอย่างเดียว งานสุขภาพภาษาไทยยังใช้ base + RAG + โปรแกรมตรวจหลักฐาน งานจัดตารางคำนวณโดย scheduler; การคัดรายการแพ้และการเขียน/ลบข้อมูลใช้ระบบเดิมที่ตรวจสิทธิและขอยืนยัน ไม่มี model-generated SQL หรือการแก้ข้อมูลเอง

ย้อนกลับได้โดยตั้ง models/runtime-adapter.json ให้ enabled_tasks เป็น [] แล้วรีสตาร์ตเว็บ ไม่แก้ฐาน 4-bit หรือทับ adapter ทดลองเดิม เก็บ run artifacts และรายงานแยกทุกครั้ง
