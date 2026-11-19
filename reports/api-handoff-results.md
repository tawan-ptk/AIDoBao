# เวลาอัตโนมัติและ API ส่งต่อ — 0.10.0

วันที่13ตุลาคม2026 เปลี่ยนตามข้อกำหนดใหม่: ไม่ระบุเวลา/ช่วงเวลาใช้เวลาไทยที่พิมพ์ ระดับนาที เก็บ clock_source=capture_time และแสดงป้ายให้แก้ได้ ถ้าระบุช่วงเช้า/บ่าย/ฯลฯ ไม่สร้างเวลาเป๊ะ ถ้าระบุ16.00 ใช้เวลานั้น เวลาผิดไม่แทนเป็นเวลาปัจจุบัน การเติมค่าเริ่มต้นทำหลังสืบทอดวัน/ช่วงเวลาจากหัวข้อความ จึงไม่ทับ period ที่บอกไว้ ไม่เพิ่ม end/ระยะเวลาและไม่เปลี่ยนรายการเก่าย้อนหลัง

chat และ journal รับ captured_at ที่ต้องมี timezone หน้าเว็บส่ง timestamp พร้อมข้อความ และ action แก้รายละเอียดเก็บ timestamp เดิมต่อไป การแก้เวลาเองเปลี่ยน clock_source=user_edited ข้อมูลเวลาอัตโนมัติไม่อ้างว่ามี source span ในข้อความผู้ใช้ ไม่ใช้เป็นหลักฐานกินยาแล้ว

เพิ่ม server integration: Bearer RUAMWAN_API_KEY + X-Ruamwan-User จาก verified backend, owner แยกถาวรใน integration_accounts พร้อม key rotation โดยไม่เปลี่ยนเจ้าของ ข้อมูล ID ภายนอกเก็บ hash กุญแจผิดไม่ถอยใช้คุกกี้เดโม run_api.py สร้าง credential ใน .secrets/api-key สิทธิ์600 ไม่พิมพ์ออกและไม่ส่งไป browser ยัง bind loopback เดิม ไม่เปิด public service

ส่งมอบ OpenAPI จากโค้ดจริง, Node backend client พร้อม allowlist และพรอมป์ต์ให้ AI ตรวจ/map โค้ดเว็บไซต์จริงโดยไม่รื้อ layout/navigation Client ไม่ auto-confirm หรือ auto-retry งานเขียนและยังใช้ consent/preview/owner/idempotency เดิม ไม่มีการแก้เว็บไซต์ปลายทางหรือทดสอบ host ปลายทางเพราะไม่ได้มีโค้ดนั้นในงานนี้

ผลที่รันจริง:

- Python293ข้อผ่าน รวม defaultเวลา7หมวด period inheritance timezone ข้ามเที่ยงคืน ยืนยันซ้ำ แยก owner และ rotation ดู [log](api-handoff-python-tests.txt)
- Node/UI19ข้อผ่าน รวมหน้าจอเติม/แก้เวลาและ backend client ดู [log](api-handoff-ui-tests.txt)
- live server API8กรณีผ่าน โดยใช้ Node client จริงและโมเดลจริงสำหรับเลือกเมนู engine=local_ai_validated_selection ไม่มีการยืนยัน/บันทึกสุขภาพ ดู [ผล](api-handoff-live.json)
- ตรวจเว็บจริงด้วยข้อความตัวอย่าง “กินข้าว” ทั้งหน้าบันทึกและแชต แสดงเวลาที่พิมพ์00:17/00:18ในวันที่13ตุลาคม ไม่กดยืนยัน ดู [หน้าบันทึก](capture-time-ui.png) และ [แชต](capture-time-chat-ui.png)
- ชุดส่งต่อ dist/ruamwan-ai-macos-0.10.0 ตรวจ SHA256ครบ61ไฟล์ รวม2,304,432,693bytes เปิด MLXจากชุดนี้ใน fresh process ได้ intent=usage_help และตรวจ backend/composite calories/capture default/question guard ผ่าน ดู [ผลเปิดชุดส่งต่อ](export-model-smoke-v0.10.0.json)

ชุดไม่รวมฐานข้อมูลผู้ใช้ sessions mappingบัญชี APIkey environment secrets หรือข้อมูลฝึก โมเดลและการเปิด adapter intent/menu ไม่เปลี่ยน ไม่ได้ fine-tune เพิ่มในรอบนี้ รุ่นเก่ายังอยู่ครบ

312ข้อเป็นการตรวจซอฟต์แวร์ ไม่ใช่คะแนน clinical/ผู้ใช้จริงหรือรับประกันไม่มีข้อผิดพลาด Runtime ยังต้องใช้ Mac Apple Silicon ส่วน TLS gateway, auth/authorization ของเว็บ, rate limits, backup/restore และการติดตั้งบนเครื่องปลายทางต้องตั้งตามระบบจริงก่อนเปิดสาธารณะ

เริ่มส่งต่อจาก [พรอมป์ต์](../docs/website-handoff-prompt.md), [คู่มือ API](../docs/ai-integration.md), [OpenAPI](../docs/openapi.json), [client](../integration/ruamwan-client.mjs)
