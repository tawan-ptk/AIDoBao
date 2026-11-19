# HTTPS gateway — 13 ตุลาคม 2026

เปิด Cloudflare Quick Tunnel ชั่วคราวผ่าน HTTPS ที่ `https://liked-logistics-identifier-urls.trycloudflare.com` เข้า gateway loopback127.0.0.1:8766 แล้วส่ง API allowlist ไป127.0.0.1:8765 เป็น URL ทดสอบ ไม่ใช่ hostname production ถาวร ไม่ติดตั้ง autorun และไม่รับประกัน uptime

Gateway ตรวจ Bearer API key และ X-Ruamwan-User ทุก request ปฏิเสธ browser Origin/cookie bypass ไม่เผยแพร่หน้าเดโม/docs/openapi/session/static/direct-delete คงการตรวจ owner/consent/preview/confirmation ของ API เดิม จำกัด body100KB/4 upstream requests และไม่ตาม upstream redirect ไม่มีการพิมพ์ API key ลง log/prompt หรือใส่ใน URL

Client เพิ่ม gatewayUrl จาก trusted server config แบบ HTTPS โดยคง loopback default สำหรับการรันบน Mac ไม่อนุญาต HTTP remote, credentials ในURL, path/query/hash หรือปลายทางจาก browser/model

ผลตรวจ:

- Python296ข้อผ่าน ดู [log](gateway-python-tests.txt)
- Node/UI20ข้อผ่าน รวม HTTPS client ดู [log](gateway-ui-tests.txt)
- HTTPS live8กรณีผ่าน ดู [ผล](gateway-live.json): ไม่มี key401, keyผิด401, ไม่มีบัญชี422, docs/session404, authenticated readiness ไปถึง origin, ข้าว+ไข่พะโล้เป็นร่างมื้อเดียว2componentsพร้อมเวลาเริ่มต้น, เลือกเมนูด้วยโมเดลจริง engine=local_ai_validated_selection, ไม่มี health record ถูกยืนยันเขียน
- ชุดส่งต่อ `dist/ruamwan-ai-macos-0.10.0-gateway` ตรวจ SHA256ครบ65ไฟล์ รวม2,304,446,432bytes ไม่รวม .secrets, database, session, integration_accounts หรือข้อมูลฝึก โมเดล/adapterและAPIversion0.10.0ไม่เปลี่ยน เป็นการเพิ่ม gateway/client/docs โดยเก็บ bundle0.10.0เดิมไว้

cloudflared มี connectivity precheck เตือนช่วงเริ่มต้น ต่อมา registered QUIC connection สำเร็จ และทดสอบ request ผ่าน HTTPS จริงครบตามข้างต้น ไม่ถือ log การสร้าง URL เพียงอย่างเดียวเป็นหลักฐานว่าสำเร็จ

การตรวจจาก Node client บนเครื่องผ่าน public HTTPS ไม่ใช่การ deploy Vercel เว็บไซต์ปลายทางยังต้องตั้ง server environment/login/CSRF/rate limits แล้ว redeploy และทดสอบ route จริง บัญชีทดสอบใช้ ID สังเคราะห์ ไม่ใช้ข้อมูลสุขภาพจริง ไม่กดยืนยันบันทึก/แก้/ลบ ไม่ใช่การประเมินทางคลินิก

วิธีส่งต่อ: [Vercel guide](../docs/vercel-gateway.md), [client](../integration/ruamwan-client.mjs), [URL metadata ไม่มี secret](../integration/gateway.json), [พรอมป์ต์เว็บไซต์ที่อัปเดตแล้ว](../docs/website-handoff-prompt.md)
