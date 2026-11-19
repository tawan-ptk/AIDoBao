# รอบฝึกแก้จุดอ่อนหลังประเมิน v2 — กำหนดก่อนฝึก v3

v2 ได้ exact extraction 24/31 และ route 5/6 บน test ของ v2 ซึ่งต่ำกว่าเกณฑ์ 90% จึงไม่เปิดสองงานนี้ ส่วน intent 36/36, menu 4/4, journal 2/2 เปิด engineering adapter v2. ไม่อ้างว่าคะแนนเหล่านี้คือ clinical/real-user accuracy

รอบ v3 ฝึกเฉพาะ extraction/route โดยใช้ v2 train/validation/test ของสองงานนี้เป็น **development training data** แล้ว ข้อมูล test v2 จึงไม่ใช่ held-out สำหรับ v3 อีกต่อไป เก็บผล v2 เดิมไว้ครบ ไม่มีการแก้ตัวเลขเดิม สร้าง phrasings และ lexical fillers ใหม่สำหรับ validation/test v3 โดยแช่แข็งก่อนเริ่มฝึก ไม่ใช้ software fixtures หรือข้อมูลผู้ใช้

ชุด v3: train 457 (419 extract, 38 route), validation 28, test 44 (36 extract/8 route). ทั้งหมดเป็น synthetic website/extraction commands ที่ผู้ใช้อนุญาต ไม่ใช่ประวัติผู้ป่วยหรือคำตอบทางการแพทย์. เน้นชื่อสั้นที่คัดลอกจากข้อความครบ การไม่เติมข้อมูลที่หาย และการแยกคำขอเขียนโปรแกรม/แต่งเรื่องที่พูดถึงสุขภาพออกจากคำถามสุขภาพ

เริ่มจาก weights adapter v2 ที่เลือกไว้ ไม่ใช่คืน optimizer/RNG. LoRA rank16 8layers batch1 LR2e-5 914steps = 2passes; candidate457/914. ทั้งสองประเมิน validation ใหม่เต็มชุดใน process ใหม่ และ generation validation สุ่มแบบเดิมตาม seed724 เลือก exact มากกว่า แล้ว mean task loss ต่ำกว่า ไม่ใช้ test v3 เลือก

หลังเลือกจึงประเมิน base/selected specialist บน test v3 ทั้ง 44 command generations. เกณฑ์เปิดแต่ละงานเหมือนเดิม: JSON ครบทุกข้อ, generations จบครบ, exact>=90%, ไม่ต่ำกว่าฐาน, extraction ครบ7หมวด. หากไม่ผ่านคงฐานต่อ ไม่ลดเกณฑ์ตามผล test

เปิด specialist แยก path เฉพาะ extract/route ที่ผ่าน ส่วน intent/menu/journal ใช้ v2 ต่อ. health_chat ไม่เปิด adapter ทั้งสองรุ่นเพราะยังไม่มี adequate Thai medical paired-answer/clinical evaluation. Scheduler/allergy/owner consent/confirmation เป็นโปรแกรมเดิม

ผล v3 ใหม่ใช้วัดกับ test v3 เท่านั้น ห้ามรายงานว่าเป็นผลบน independent real-user data หรือเทียบเปอร์เซ็นต์ตรงกับ test v2 ซึ่งคนละชุด
