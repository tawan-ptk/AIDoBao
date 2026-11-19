# Training task matrix — ก่อนฝึก

| งาน | ข้อมูลจริงที่เลือก | input → target | จำนวนที่ตั้งใจใช้ก่อนวัด token | ประเมิน |
|---|---|---|---:|---|
| QA ภาษาอังกฤษเชิงความรู้ทั่วไป | MedQuAD / Ben Abacha และ Demner-Fushman / CC BY 4.0 | Question → Answer เดิมแบบไม่แก้ข้อความ | train 6 / valid 1 / test 1 | assistant loss, คำตอบจริง, latency, หน่วยความจำ |
| สนับสนุนพฤติกรรม | HAI-Coaching | struggle_original → suggestion_from_expert | 0: สิทธิข้อมูล/adapter ยังไม่ชัด | ไม่ฝึก |
| แยกบันทึก/ถามเพิ่ม | ไม่มี annotated paired labels ที่ผ่านเกณฑ์ | prompt → schema + validation | 0 | software tests แยกจากความแม่นยำจริง |
| วางแผน/ปรับแผน | ไม่มีแผนจากผู้เชี่ยวชาญที่มีสิทธิ | confirmed inputs → scheduler | 0 | constraint tests ไม่ใช่ clinical validation |

การคัด QA ขนาดเล็กเป็นข้อจำกัดด้านคุณภาพข้อมูล ไม่ใช่ข้อจำกัดจำนวนที่โมเดลรับได้: MedQuAD มีคำถามที่ชื่อหัวข้อไม่ตรงย่อหน้าคำตอบ สถิติเก่า เบอร์ติดต่อสหรัฐฯ และคำแนะนำที่ต้องตรวจเพิ่ม จึงไม่เติมจำนวนด้วยข้อมูลสร้างใหม่

ผลจำนวนสุดท้ายและ token lengths อยู่ใน training-data-audit.json เมื่อ script รันจริง ห้ามตีความ pilot ขนาดนี้ว่าพิสูจน์ว่า fine-tuning ดีขึ้นสำหรับแอป เปรียบเทียบ held-out sleep topic เป็นเพียง smoke evaluation ที่มี distribution shift; test ไม่ใช้เลือก checkpoint
