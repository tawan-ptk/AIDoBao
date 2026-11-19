# แก้กรณีแจ้งว่าโมเดลเสนอข้อมูล แต่ฟอร์มว่าง

พบจากการรัน `scripts/diagnose_extraction.py` กับ SOFTWARE TEST ONLY fixture เดิม: model output มี `data` เป็น array สองรายการ และ evidence keys ไม่ตรง field names จึงถูกปฏิเสธตาม contract แต่ UI แจ้งสำเร็จโดยไม่ตรวจค่าที่เติมจริง

แก้ prompt ให้แสดงโครงสร้าง object เดียว, key ของ evidence และ enum ที่ฟอร์มรับ เพิ่ม parser ตรวจชนิดและหลักฐาน API คืนสถานะ failure/no fields/proposal ตามจริง UI แสดงจำนวนช่องที่เติมได้และช่องที่ต้องเพิ่ม ไม่แจ้งสำเร็จเมื่อไม่มีข้อมูล และป้องกันผลลัพธ์เก่าหากเปลี่ยนข้อความหรือชนิดระหว่างรอ

หลังแก้ รันโมเดลฐานจริงด้วย fixture เดิมได้ name=glucose, value=120, unit=mg/dL, occurred_at=2026-10-12T07:00:00+07:00, context=fasting, method=fingerstick พร้อม evidence ตรง input ทั้งหกช่อง เวลา load 1.325 วินาที generation 4.701 วินาที MLX peak 2.768 GB ไม่เขียนฐานข้อมูลหรือใช้ฝึก

ผล regression: pytest 22 passed (0.26s); Node click-handler tests 3 passed รวม failure, partial และ all-null responses การทดสอบ DOM ใช้ stand-ins ไม่ใช่ visual/browser QA

ผลนี้แก้ formatting smoke test เดิมได้ ไม่ใช่การรับรอง extraction accuracy ทุกข้อความหรือภาษาไทย รายงานความล้มเหลวเดิมเก็บไว้ที่ `model-extraction-software-test.json` โดยไม่เขียนทับ

## ข้อความสั้น “เดิน 16.00”

ทดสอบจริงเพิ่ม: เมื่อเลือก meal โมเดลคืนทุกช่อง null; เมื่อเลือก activity โมเดลคืนชื่อ “เดิน” และเวลาเริ่ม “16.00” ซึ่งไม่ใช่วันเวลาครบถ้วน จึงเพิ่มคำแนะนำเปลี่ยนประเภทเป็นกิจกรรมโดยให้ผู้ใช้กดเอง และแจ้งวันที่/เวลาเริ่ม/สิ้นสุดที่ยังขาด Parser เก็บเฉพาะช่องที่มีหลักฐานและวันเวลาครบพร้อม timezone; ช่องที่ไม่ผ่านไม่ทำให้ช่องอื่นหาย ไม่เดาว่าเป็นวันนี้

Regression ล่าสุด pytest 23 passed; Node handler 3 passed; JS syntax ผ่าน การทดสอบภาษาไทยเพิ่มเป็นการตรวจบั๊ก ไม่ใช่ข้อมูลฝึกหรือ benchmark ความแม่นยำ
