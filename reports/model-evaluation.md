# ผลทดลองจริง — 12 ตุลาคม 2026

**รายงานนี้เป็น pilot เดิม 6 steps** ปัจจุบันฝึกเพิ่มเติมจริงแล้ว: [v2 หลายงาน 604 steps](finetune-v2-results.md) และ [v3 แก้จุดอ่อน 914 steps](finetune-v3-results.md) เปิด adapter เฉพาะ intent/menu ที่ตรวจผ่านเว็บ ส่วน journal ปิดหลังพบข้อผิดพลาดผ่านเว็บ และ extract/route ยังไม่ผ่านเกณฑ์ รายละเอียดด้านล่างเก็บผล pilot เดิมตามจริง

ฝึก Typhoon2.5-Qwen3-4B revision `ce0a7416fe82d4404b2b4a253ce3ac095ab1252c` ด้วย MLX-LM 0.32.0 / MLX 0.32.3, 4-bit affine group 64, LoRA rank 8 ใน 4 layers, batch 1, LR 1e-5, seed 42, assistant-only loss, context 1024 ไม่มีการตัดคำตอบฝึก ความยาวมากที่สุด 304 tokens

ข้อมูลฝึกคือ Question/Answer ต้นฉบับภาษาอังกฤษจาก MedQuAD โดย Asma Ben Abacha และ Dina Demner-Fushman, CC BY 4.0 จำนวน 6 คู่ Validation 1 คู่ และ test 1 คู่ ไม่ใช้ HAI-Coaching, ข้อมูลผู้ใช้, ข้อมูลสร้างใหม่ หรือ software fixtures ฝึก แบ่งตามเอกสารและรวมเอกสารหัวข้อเบาหวานไว้ฝั่งเดียวเพื่อลดการรั่วไหล ตรวจ cross-split similarity ด้วย SequenceMatcher และ word Jaccard; ไม่ใช่การรับรองว่าไม่มี semantic leakage หรือ pretraining contamination

Pilot 6 steps (หนึ่งรอบของข้อมูล 6 คู่) สำเร็จใน 14.09 วินาทีรวมเริ่ม process หลังแก้ปัญหา MPICH; throughput ที่แสดงหลัง step แรก 222–252 tokens/s จำนวนข้อมูลเล็กเกินกว่าจะมีเหตุผลฝึกยาวหรือปรับหลาย configuration จึงหยุดที่ pilot และส่งมอบเป็น engineering adapter เท่านั้น เลือก checkpoint step 6 จาก validation loss 2.060 เทียบ step 3 ที่ 2.106 ก่อนเปิด test

| การวัด | ฐาน 4-bit | ฐาน + adapter |
|---|---:|---:|
| Assistant-only held-out loss | 2.036880 | 1.947290 |
| จำนวน test QA | 1 | 1 |
| เวลาโหลด (วินาที) | 1.651 | 1.396 |
| MLX peak memory ของ process ประเมิน (GB decimal) | 2.992 | 3.203 |
| เวลา process ประเมิน รวม loss และ 3 generations (วินาที) | 28.173 | 29.185 |

Loss ลดลงบนข้อเดียวนี้ ไม่เพียงพอให้กล่าวว่าโมเดลดีขึ้นสำหรับงานสุขภาพหรือภาษาไทย Test เป็นหัวข้อ sleep disorders ต่างจากข้อมูลฝึกส่วนใหญ่ และไม่มีช่วงความเชื่อมั่นที่มีความหมายจาก n=1 เวลาโหลดได้รับผลจาก OS cache ไม่ใช่ benchmark ที่ควบคุม cold cache

ผลตรวจข้อความจริงโดยผู้ช่วยเขียนโปรแกรม (ไม่ใช่ผู้เชี่ยวชาญทางคลินิก):

- ฐานและ adapter เพิ่มชื่อ/รายละเอียด เช่น circadian rhythm disorders และ breathing subtypes ที่ไม่ได้อยู่ในคำตอบ MedQuAD อ้างอิงที่ให้ไว้ การไม่อยู่ในหลักฐานไม่ได้แปลว่าข้อความนั้นเป็นเท็จ แต่ไม่ผ่านเงื่อนไขตอบเฉพาะหลักฐาน
- ทั้งคู่สร้างถึงเพดาน 384 tokens และจบกลางข้อความ จึงไม่ถือเป็นคำตอบสมบูรณ์ ไม่มีการตัดคำตอบฝึก แต่มีการจำกัด generation ในการประเมินและรายงานตามจริง
- ใน open-book RAG smoke test ใช้คำถามหัวข้อ mental health จริงจาก NIDDK ทั้งคู่ให้คำตอบสั้นลงและใกล้ข้อความหลักฐานมากกว่าแบบไม่แนบ RAG แต่ไม่ใส่ chunk ID แม้สั่งไว้ จึงยังไม่ผ่านข้อกำหนด citation ของการสร้างคำตอบแบบอิสระ
- ตัวเลข `new_numeric_strings` ใน JSON เป็นเพียงสัญญาณตรวจเพิ่ม รวมเลขลำดับรายการด้วย ไม่ใช่คะแนนความถูกต้องทางคลินิก

เดโมเลือกโมเดลฐานสำหรับช่วยแยกข้อความ และใช้ **extractive RAG** แสดงข้อความต้นฉบับกับ citation จาก metadata โดยตรง ไม่ใช้คำตอบ generative ข้างต้นเป็นคำแนะนำผู้ใช้ การอธิบายแผนใช้ค่าจาก scheduler โดยตรงเพื่อไม่ให้ข้อความเปลี่ยนเวลา/ตัวเลข

เปิด process ใหม่แยกสำหรับฐานและ adapter สำเร็จทั้งสองรายการ (PID และคำตอบเต็มใน `evaluation-base.json`, `evaluation-adapter.json`) ตรวจ resume จาก weights เดิมอีก 1 step ไปยัง `adapters/resume-check` สำเร็จ 4.22 วินาที MLX peak 2.796 GB ไม่คืน optimizer state/RNG และไม่ใช้ผล resume เลือก adapter หรือเปลี่ยนผล test

เก็บข้อผิดพลาดเริ่มต้นไว้ใน `logs/pilot-mpich-failure.log` และ `logs/pilot-ring-failure.log` การแก้ใช้ environment `MLX_MPI_LIBNAME` ชี้ไป library ที่ไม่มี เพื่อไม่โหลด MPICH ของ Anaconda; MLX ใช้กลุ่มเครื่องเดียว ไม่แก้ weights/optimizer หรืออ้างว่า MLX quantized LoRA เหมือน CUDA QLoRA ทุกประการ

การตรวจความเหมาะสมของข้อมูลฝึกเป็นการเทียบข้อความกับแหล่งปัจจุบัน ไม่ใช่การอนุมัติโดยแพทย์ ข้อมูลคู่คำถามไทยจากมนุษย์ การประเมินเงื่อนไขทางคลินิก และชุดทดสอบขนาดเพียงพอยังขาดอยู่
# ผล smoke test การแยกข้อความ

วันที่ 12 ตุลาคม เรียก base model จริงกับ software fixture 1 ข้อใน process ใหม่ โหลด 1.63 วินาที generate 5.27 วินาที peak MLX 2.62 GB ได้ผลที่ไม่ผ่าน JSON contract (`invalid_model_output`) ระบบคืนทุกช่องเป็น null และ schema status unknown โดยไม่มีการบันทึก จึงยังไม่ผ่านความสามารถ extraction และไม่มี accuracy ผู้ใช้จริง รายงานอยู่ `model-extraction-software-test.json` ใช้ฟอร์มกรอกเป็นทางหลัก; การฝึก QA อังกฤษไม่ได้ฝึก schema extraction
