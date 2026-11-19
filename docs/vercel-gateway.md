# HTTPS gateway สำหรับทดสอบจาก Vercel

วันที่13ตุลาคม2026 เปิด URL ชั่วคราว:

```text
https://liked-logistics-identifier-urls.trycloudflare.com
```

นี่คือ gateway ของร่วมวันบน Mac ไม่ใช่ผลิตภัณฑ์ Vercel AI Gateway และไม่ใช่ URL production ถาวร Cloudflare Quick Tunnel ใช้ทดสอบได้ฟรี ไม่ต้องมีบัญชี/โดเมน URL เปลี่ยนเมื่อเปิด tunnel ใหม่และไม่มี uptime guarantee ดู [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## ตั้งค่าบน Vercel

ในโปรเจกต์เว็บไซต์ ตั้ง Environment Variables ฝั่ง server ตาม environment ที่จะทดสอบ แล้ว redeploy:

```text
RUAMWAN_GATEWAY_URL=https://liked-logistics-identifier-urls.trycloudflare.com
RUAMWAN_API_KEY=<ค่าจากไฟล์ .secrets/api-key บน Mac>
```

กุญแจให้เปิดไฟล์ในเครื่องและคัดลอกใส่ Vercel Environment Variables โดยตรง ห้ามใส่ใน prompt ของ AI, Git, screenshot, URL, browser หรือ environment ที่ขึ้นต้น NEXT_PUBLIC_/VITE_ ไม่ต้องสร้างกุญแจใหม่ให้แต่ละคน เว็บ backend ใช้กุญแจ server ร่วมกับ ID ของผู้ใช้ที่ login แล้วเพื่อแยกบัญชี

**ใช้ `integration/ruamwan-client.mjs` รุ่นปัจจุบันจาก repo นี้** ซึ่งเพิ่ม option gatewayUrl แล้ว client ใน bundle0.10.0เก่าจำกัด loopback และยังใช้ HTTPS ไม่ได้ ชุดส่งต่อ gateway แยกชื่อ `ruamwan-ai-macos-0.10.0-gateway` มีไฟล์ใหม่ครบโดยไม่แก้ bundle เก่า

## การเรียกจาก backend เว็บไซต์

```js
import {createRuamwanClient} from './integration/ruamwan-client.mjs';

// ใช้ auth เดิมของเว็บไซต์ตรวจ login ก่อนถึงส่วนนี้
// verifiedUser.id ต้องมาจาก session ที่ backend ยืนยัน ไม่ใช่ request body
if (!process.env.RUAMWAN_GATEWAY_URL) throw new Error('Missing AI gateway URL');
const ai = createRuamwanClient({
  gatewayUrl: process.env.RUAMWAN_GATEWAY_URL,
  apiKey: process.env.RUAMWAN_API_KEY,
  userId: `my-site:${verifiedUser.id}`
});
const result = await ai.chat(messages, {
  scope: 'auto',
  captured_at: submittedAt // ISO timestamp มี timezone จับครั้งเดียวตอนส่ง
});
// handler ของเว็บส่ง result กลับ browser ผ่าน endpoint ของเว็บเอง
```

เปลี่ยน my-site เป็น namespace คงที่ของเว็บ/tenant และคง auth/CSRF/rate limits ของเว็บไซต์เดิม ห้ามรับ owner/userId/gatewayUrl/API key จาก browser หรือโมเดล ถ้า environment ไม่ครบให้แจ้ง configuration error อย่าถอยไป localhost บน Vercel

Headers ที่ client ส่งให้ gateway:

```http
Authorization: Bearer <server API key>
X-Ruamwan-User: my-site:<verified-user-id>
Content-Type: application/json
```

ไม่ส่ง Origin, Cookie, CSRF ของเดโม หรือ Authorization ของผู้ใช้จาก browser ต่อไปโดยตรง Browser เรียก API ของเว็บบน Vercel แล้ว Vercel จึงเรียก gateway เท่านั้น Gateway จะปฏิเสธ request ที่มี Origin ไม่เปิด CORS ให้ browser เรียก AI โดยตรง

ใช้ Node.js runtime สำหรับตัวอย่าง client ถ้าเว็บเป็น Next.js App Router สามารถตั้ง `export const runtime = 'nodejs'` และกำหนด maxDuration ให้เหมาะกับเวลาตอบของโมเดลและข้อจำกัดแพ็กเกจจริง ดู [Vercel function duration](https://vercel.com/docs/functions/configuring-functions/duration) ค่า timeout client ไม่ได้ขยาย timeout ของ Vercel/Cloudflare อัตโนมัติ หาก timeout ระหว่างยืนยัน ให้ตรวจบันทึกหรือ retry คำขอเดิมด้วย idempotency key เดิม ห้ามสร้างและยืนยันร่างใหม่อัตโนมัติ

## สิ่งที่ gateway เปิดและปิด

- เปิดเฉพาะ API allowlist พร้อม Bearer key และ X-Ruamwan-User ทุก request
- ไม่เผยแพร่หน้าเดโม, /docs, /openapi.json, /api/session, static files หรือการลบตรงผ่าน /api/delete
- การลบใช้ delete-preview/confirm การเขียนและแก้ยังต้อง consent/preview/explicit confirmation เดิม
- ไม่มี key →401, ไม่มีบัญชี →422, endpoint ไม่เผยแพร่ →404, busy →429
- ชี้ upstream ตายตัวที่127.0.0.1:8765 ไม่รับ URL ปลายทางจากข้อความหรือ header
- จำกัด body100KB และคำขอ upstream พร้อมกัน4คำขอ ตัวโมเดลยังมี lock ของตัวเอง ไม่ใช่บริการหลายผู้ใช้พร้อมกันแบบไร้ขีดจำกัด

เปิด URL ใน browser แล้วเห็น401ถือว่าถูกต้อง เพราะ URL นี้สำหรับ backend ไม่ใช่หน้าสนทนา หน้าเดโมในเครื่องยังเปิด http://127.0.0.1:8765 ได้ตามเดิม

## เปิดใหม่/หยุด

ต้องให้ทั้ง3processทำงาน:

```sh
.venv/bin/python scripts/run_api.py
.venv/bin/python scripts/run_gateway.py
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8766
```

รันแต่ละคำสั่งคนละ terminal ไม่เปิดซ้ำหาก process เดิมกำลังทำงาน เมื่อเปิด tunnel ใหม่ให้นำ URL ที่ cloudflared แสดงไปเปลี่ยน RUAMWAN_GATEWAY_URL แล้ว redeploy เว็บไซต์ ห้ามใช้ hostname เก่าต่อโดยไม่ตรวจว่าเป็น tunnel ของเรา Mac ต้องเปิดอยู่ ไม่ sleep และเชื่อมอินเทอร์เน็ต ไม่ได้ติดตั้งให้เริ่มตอนเปิดเครื่องหรือรับประกัน uptime

ทดสอบจาก Node client ในเครื่องผ่าน HTTPS จริงด้วย `node scripts/check_gateway_live.mjs` ใช้ข้อความตัวอย่าง ไม่ยืนยันบันทึกสุขภาพ อ่าน URL จาก integration/gateway.json; หากเปลี่ยน tunnel ต้องอัปเดตไฟล์นี้ก่อนทดสอบ

ผลทดสอบจริงเก็บใน reports/gateway-live.json การทดสอบ HTTPS จากเครื่องนี้ไม่ใช่หลักฐานว่า deploy Vercel สำเร็จ ต้องทดสอบ route ของเว็บหลังตั้ง environment/redeploy อีกครั้ง โดยไม่เปิด key ใน logs และไม่ใช้ข้อมูลสุขภาพจริงเป็นตัวอย่าง
