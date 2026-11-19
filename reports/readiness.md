# ความพร้อมของต้นแบบ

สถานะส่งมอบ: local engineering/research prototype การผ่านโปรแกรมไม่ได้แปลว่าเหมาะสมทางคลินิก ไม่มีผู้เชี่ยวชาญตรวจ ไม่มี production deploy ไม่มี Supabase write และไม่มีผู้ป่วยสมมติในเดโม

| ส่วน | ทำได้และหลักฐานทดสอบ | สิ่งที่ขาด / ผู้ตรวจที่ต้องมี |
|---|---|---|
| บันทึก 7 ด้าน | พิมพ์หลายหมวดพร้อมกัน วันที่พิมพ์อัตโนมัติ ช่วงเวลาที่ยังไม่เป๊ะ batch confirmation/rollback และเติมเวลาภายหลัง; pytest/API/jsdom ดู journal-update.md | annotated ข้อความไทยจากผู้ใช้ที่มีสิทธิ; UX ผู้ใช้จริง |
| โมเดลแยกข้อความ | แก้ prompt/object contract และสถานะ UI แล้ว; fixture เดิมผ่านครบ 6 ช่อง ดู extraction-fix.md; คืน unknown เมื่อรูปแบบไม่ผ่าน | ยังไม่มี accuracy benchmark ข้อความไทยจริง; ผู้ใช้ต้องตรวจทุกช่องและใช้ฟอร์มแก้ไข |
| อาหาร | importer, portion/basis/raw-cooked, missing, allergen unknown, recipe yield และ conversion เป็น service ที่ทดสอบ | catalog ไทย 0 แถว; permission, ingredient/portion/yield จริง; นักกำหนดอาหารตรวจ ก่อนเปิดแผนอาหาร/เป้าสารอาหาร |
| กิจกรรม | บันทึกเวลา/วิธีวัด จัดเวลาเฉพาะกิจกรรมยืนยัน แยกค่าจากอุปกรณ์; catalog ข้อความตัวอย่าง NIDDK ปิด recommendation | ความหนัก/contraindications/ความพร้อมรายคน; ผู้เชี่ยวชาญการออกกำลังกาย ไม่สร้างแคลอรีขึ้นเอง |
| นอน | ข้ามเที่ยงคืน, main/nap, time-in-bed แยก actual/device estimate | การให้คำแนะนำเฉพาะบุคคล/กะงานต้องมี evidence และ review; ไม่มีการวินิจฉัยการนอน |
| ยาและนัด | บันทึกและล็อกเวลา แหล่งคำสั่งยา; before/after meal relation ตรวจใน scheduler | ไม่ปรับยาเอง; เงื่อนไข with-meal ยังไม่รองรับกิจกรรมร่วมเวลาและปฏิเสธ; เภสัชกร/ผู้รักษาตรวจ |
| ค่าตรวจ | แยกหน่วย บริบท เวลา วิธีวัด และ origin; แสดงแนวโน้มในกลุ่มที่เทียบได้ | ไม่ตีความโรค/ตั้งเป้ารักษา; เป้าหมายผู้ดูแลที่มี provenance และผู้ตรวจ |
| พฤติกรรม/ความเป็นอยู่ | บันทึก เป้าหมายและ feedback ของผู้ใช้; ปรับเวลาโดย preview diff | HAI ไม่ผ่านสิทธิ จึงยังไม่ฝึก coaching; ไม่ใช่บริการสุขภาพจิตหรือประเมินความเสี่ยง |
| RAG | 5 หัวข้อ NIDDK ข้อความจริงพร้อม citation; Thai keyword aliases; unsupported topic คืน unknown | corpus ไทยและ retrieval benchmark; lexical heading matching มีข้อจำกัด ไม่ครอบคลุมทุกคำถาม |
| แผนรวม 7 วัน | 7 domains, hard blocks, no overlap, immutable medication times, bounded backtracking, revision recheck, before/after, atomic confirm | grid 15 นาที; ไม่มี optimizer ความเหมาะสมทางคลินิก/งบอาหาร; constraints ที่ไม่มีโครงสร้างต้องให้ผู้ใช้แปลงเป็นข้อจำกัดยืนยันก่อน |
| กฎ | registry แยก program กับ health draft; health recommendation ปิดจนมีผู้ตรวจ | แพทย์/เภสัชกร/นักกำหนดอาหาร/ผู้เชี่ยวชาญกิจกรรมพร้อมชื่อ วัน รุ่น ขอบเขต |
| ฝึกและประเมิน | MLX 4-bit LoRA 6 steps; adapter จริง, fresh-process base/adapter, resume weights จริง | 6/1/1 QA อังกฤษเล็กมาก ไม่อ้าง generalization; ไม่มี optimizer/RNG resume หรือ clinical benchmark |
| ฐานข้อมูล local | SQLite transaction, append-only, session persist 7 วัน, CSRF, export/delete; integration | app-level encryption, permanent auth/recovery, load/security review ก่อนข้อมูลจริงหลายผู้ใช้ |
| Supabase | migration/RLS/RPC/interface/payload; SQL parser ผ่าน | ยังไม่ execute PostgreSQL, RLS adversarial/concurrency tests, Auth และ backend trusted proposal writer |
| UI | Thai static app, API flow และ actual HTML/scripts ผ่าน jsdom multi-record/edit tests | jsdom ไม่ใช่ visual/browser QA: Computer Use permissions ไม่ได้รับอนุญาต; ไม่อ้าง visual QA ผ่าน |

ผลจริงอ่าน [delivery-verification.json](delivery-verification.json), [tests.txt](tests.txt), [model-evaluation.md](model-evaluation.md), [model-extraction-software-test.json](model-extraction-software-test.json) ข้อมูลทดสอบอยู่ temporary DB แยกจากเดโมและ training

เริ่มงาน 2026-10-11 10:04 Bangkok ตาม workplan; pilot ใช้ 14.09 วินาที ไม่ใช่ฝึกต่อเนื่องทั้งคืน ช่วงต่อเนื่องบนปฏิทินรวมการหยุดและกลับมาทำต่อจึงไม่ใช่ชั่วโมงทำงานจริงเต็มจำนวน Resume smoke 1 step วันที่ 12 เวลา 08:26 ใช้ 4.22 วินาทีเป็นการตรวจโหลด weights ไม่ใช่การเลือก checkpoint ใหม่; base/adapter evaluation ทำไว้ก่อนหน้าแล้ว ไม่มีการปรับ configuration ตาม test

ควรทดลองในเครื่องด้วยข้อมูลที่ผู้ใช้ยินยอมเท่านั้น ส่วนที่ยังไม่ควรเปิดเป็นบริการคือการแนะนำการรักษา/ยา/แผนสารอาหารเฉพาะบุคคล การวางแผนสำหรับเด็ก ตั้งครรภ์ หรือกลุ่มซับซ้อน และการเปิด public/multiuser production
