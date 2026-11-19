# ร่วมวัน AI API 0.10.0 — เชื่อมเว็บไซต์เดิม

บริการ Python/FastAPI + MLX บน **Mac Apple Silicon** ใช้ Typhoon2.5-Qwen3-4B 4-bit และ LoRA เฉพาะ intent/menu ฐานโมเดลยังทำ extraction/journal/health ตามผลทดสอบ ห้าม merge adapter แล้วใช้ทุกงาน Runtime นี้ไม่ใช่โมเดล JavaScript สำหรับ browser และยังไม่รองรับ Linux/CUDA ด้วยชุดติดตั้งนี้

ส่งให้ AI เว็บไซต์อ่าน [พรอมป์ต์ฉบับเต็ม](website-handoff-prompt.md), [OpenAPI](openapi.json), [Node backend client](../integration/ruamwan-client.mjs) ให้ตรวจโค้ดเว็บจริงก่อน map หน้า/components/ฐานข้อมูล ไม่ต้องรื้อ layout/navigation หรือเปลี่ยน framework

สำหรับเว็บไซต์บน Vercel ใช้ [HTTPS gateway และขั้นตอนตั้งค่า](vercel-gateway.md) ขณะนี้มี URL ชั่วคราวสำหรับทดสอบแล้ว ห้ามใช้ localhost:8765 เป็นปลายทางจาก Vercel และต้องใช้ client รุ่นปัจจุบันที่รองรับ gatewayUrl

## เปิดบริการ

โปรเจกต์นี้ใช้ .venv ที่มีอยู่ บน Mac ปลายทางสร้าง environment Python3.13 แล้วติดตั้ง requirements.runtime.txt จากนั้นรัน:

```sh
.venv/bin/python scripts/run_api.py
```

เปิด http://127.0.0.1:8765/docs ดูสัญญา API แบบโต้ตอบ และ /openapi.json หาก server เดิมใช้พอร์ตนี้อยู่ต้องปิด process เดิมก่อน run_api.py สร้างกุญแจ server ที่ `.secrets/api-key` สิทธิ์600 โดยไม่พิมพ์กุญแจ หรือรับ RUAMWAN_API_KEY จาก environment (อย่างน้อย32อักขระ ASCII) ตั้งค่าเดียวกันเฉพาะ backend ของเว็บปลายทาง ห้ามใช้ public/frontend config

ตั้ง LOCAL_DB เป็น absolute path บน persistent disk ค่าเดิม data/local.sqlite3 สำรองทั้งข้อมูลและ integration_accounts mapping การติดตั้ง dependencies บนเครื่องใหม่ยังไม่ได้ทดสอบ ชุดส่งต่อ/model smoke ตรวจใน environment ปัจจุบัน

## สิทธิ์และการเชื่อมต่อ

Browser → backend เว็บไซต์เดิม (ตรวจ login/สิทธิ์/CSRF) → API บน Mac → MLX/RAG/SQLite

ทุก request จาก backend ส่ง:

```http
Authorization: Bearer <RUAMWAN_API_KEY>
X-Ruamwan-User: my-site:<verified-auth-subject>
```

ID ยาว1–200อักขระ ASCII ไม่มีช่องว่าง ได้จาก login ที่ backend ตรวจแล้วเท่านั้น ไม่รับ ID ที่ browser/model เลือกเอง ใช้ namespace/tenant คงที่ ห้ามใช้ ID เดียวร่วมทุกบัญชี API map hash ของ ID ไป owner ถาวรใน integration_accounts ไม่หมดอายุตามคุกกี้และไม่เปลี่ยนเมื่อหมุน key อย่าลบ mapping ระหว่างอัปเกรด ผู้ถือกุญแจ server มีสิทธิ์ระบุบัญชี ดังนั้น backend ต้องตรวจ authorization เอง กุญแจนี้ไม่ใช่ token ผู้ใช้/OAuth

API หลัก bind loopback จำกัด Host/Origin สำหรับเว็บไซต์คนละ host ใช้ HTTPS gateway ที่แยกตรวจสิทธิ์บน127.0.0.1:8766ตามคู่มือ Vercel ตัวอย่าง client รองรับ loopback หรือ gatewayUrl แบบ HTTPS ที่ตั้งจาก server config เท่านั้น ไม่รับ URL จาก browser/โมเดล โหมดเดโม cookie+X-CSRF-Token จาก GET /api/session ยังใช้ได้ แต่อายุ7วัน ไม่ใช้เป็นบัญชี production และไม่แชร์ cookie ร่วมทุกผู้ใช้ server integration ไม่ต้องสร้างเซสชันเดโม

## ตัวอย่าง backend Node.js20+

ไฟล์ integration/ruamwan-client.mjs ใช้ fetch/AbortSignal.timeout ไม่มี dependency เพิ่ม ไม่ auto-confirm/auto-retry ตัวอย่างนี้อยู่ใน handler ที่ผ่าน auth ของเว็บแล้ว:

```js
import {createRuamwanClient} from './integration/ruamwan-client.mjs';
const ai = createRuamwanClient({
  apiKey: process.env.RUAMWAN_API_KEY,
  userId: `my-site:${verifiedUser.id}` // จาก auth middleware ไม่ใช่ body
});
const answer = await ai.chat([
  {role:'user', content:'กินข้าวกับอะไรดี'}
], {captured_at:'2026-10-13T18:20:00+07:00'});
// ส่ง answer กลับ browser แล้ว render actions เป็นปุ่มให้ผู้ใช้กด
```

API ยังไม่ streaming แสดง loading ระหว่างรอ client timeout210วินาทีเพื่อรองรับ subprocess โมเดล จัดการ queue/rate/concurrency/ขนาดข้อความที่ backend เว็บไซต์ ยกเลิกหรือทิ้งผลเก่าเมื่อ reset/logout โมเดลมี lock ไม่ใช่ระบบ high-volume ที่รับทุกคำขอพร้อมกัน

## Endpoint

| Endpoint | หน้าที่/ข้อมูลสำคัญ |
| --- | --- |
| POST /api/chat | {messages:[{role,content}],scope:"auto",captured_at} → answer/status/route/actions/citations/menus ตามชนิดคำตอบ |
| POST /api/journal/prepare | {text,captured_at,use_model:true,compact:true} → items[].record/check/warnings, unparsed; ไม่เขียนข้อมูล |
| POST /api/records/preview | record เดียว → draft_id, record, check, can_confirm |
| POST /api/records/batch-preview | {records,compact:true} → draft_id, records, checks, can_confirm, requires_consent |
| POST /api/confirm | {draft_id,idempotency_key,confirmed:true} หลังผู้ใช้กดยืนยัน |
| POST /api/records/delete-preview | {scope:"records",record_ids:[...]} หรือ scope=all → รายการ/เวอร์ชัน/แผนที่กระทบ, draft_id |
| GET /api/records?limit=100&offset=0 | items + meal_energy แยกจาก payload; history=true เพื่ออ่านเวอร์ชันเก่า |
| GET /api/summary | energy_summary, counts, activity_sleep, measurements, incomplete_records |
| GET /api/personal-context | โปรไฟล์และข้อมูลประกอบที่ยืนยันแล้ว |
| GET /api/food-catalog | name/aliases/serving/basis ที่มีแหล่งอ้างอิง |
| POST /api/food-energy | {name,quantity,unit,food_state,components?} → พลังงานประมาณ ไม่ส่ง record/occurred_at ทั้งก้อน |
| POST /api/plans/preview | {start_date,general_time_only:true,previous_plan_id?,reason?} → plan, draft_id, can_confirm, comparison |
| GET /api/plans | แผนที่ยืนยันแล้ว |
| GET /api/plans/{id}/recheck | ตรวจแผนกับข้อมูลล่าสุด |
| POST /api/knowledge | {query} ความรู้จากฐานหลักฐาน; chat เป็นจุดเข้าที่เลือกงานครบกว่า |
| GET /api/export | ส่งออกข้อมูลบัญชีนี้ ไม่ใช่ weights |
| GET /api/readiness | ความสามารถ/runtime; production=false ไม่รับรองว่าโมเดลตอบทุกคำถามได้ |

Fields/ชนิด/ขอบเขตเต็มอยู่ใน OpenAPI จากโค้ดจริง request ใช้ extra=forbid ต้องส่งเฉพาะ fields ตาม schema คำตอบ chat เป็นหลายชนิด จึงต้องอ่าน status/actions ที่มีจริง ไม่สมมติว่าทุกคำตอบมี menus หรือ record

## วันเวลาและข้อมูล

captured_at เป็น ISO8601 มี timezone ถ้าไม่ส่งใช้เวลารับคำขอ ใช้ปฏิทิน Asia/Bangkok จับ timestamp ครั้งเดียวต่อข้อความและเก็บต่อจนยืนยัน ไม่สร้างใหม่เมื่อกดแก้/ยืนยันหลังเที่ยงคืน

| ข้อความ | ผลเวลา |
| --- | --- |
| กินข้าว | วันที่/เวลาไทยที่พิมพ์ ระดับนาที clock_source=capture_time แสดงป้ายเวลาที่พิมพ์ |
| ตอนเช้ากินข้าว | period=morning, clock=null ไม่แต่งเวลาเป๊ะ |
| เดิน16.00 | clock=16:00 source=explicit ไม่เติม end |
| เมื่อวานกินข้าว | วันที่เมื่อวานกับเวลาเริ่มต้นจากเวลาที่พิมพ์ แก้ได้ |
| เดิน25.00 | แจ้งเวลาผิด ไม่แทนด้วยเวลาปัจจุบัน |

แก้เวลาเอง → clock_source=user_edited ล้างเวลา → unspecified บันทึกเก่าที่ไม่มี clock_source ยังอ่านได้ ไม่เขียนเวลาใหม่ย้อนหลังให้รายการเก่า เวลาเริ่มต้นไม่ยืนยันว่ากินยาแล้วและไม่แต่งเวลาสิ้นสุด/ระยะเวลา

Record มี kind/text/data/origin/source/evidence/previous_id และ journal สำหรับบันทึกแบบเล่า journal มี date/timezone/period/clock/clock_source/date_source/captured_at/context_text compact=true ล้างข้อความเล่ายาว/evidence ที่อ้างถึงข้อความนั้น เก็บชื่อสั้นกับค่าแยกช่อง

| kind | data หลัก |
| --- | --- |
| meal | name, quantity, unit, food_state, occurred_at; components[] สำหรับหลายอย่างในมื้อเดียว |
| activity | name, start, end, method, intensity, catalog_id |
| sleep | start, end, method, episode, quality |
| medication | name, dose, unit, occurred_at, instruction_source, state |
| appointment | name, start, end, location |
| measurement | name, value, unit, occurred_at, context, method |
| wellbeing | note, occurred_at |
| profile | age, weight_kg, height_cm, conditions, medications, timezone, reported_type2, complex_care, pregnant, goals, allergies, preferences, mobility_limits, prohibited_catalog_ids |
| routine | domain, label, dates, earliest, latest, duration_minutes, fixed, catalog_id, goal, instruction_source, meal_relation, related_routine_id, relation_minutes |
| constraint | label, start, end |
| feedback | plan_id, reason, occurred_at |
| consent | local_storage=true หลังผู้ใช้ให้ความยินยอม |

ค่าไม่ทราบ null/unknown ไม่ใช่0 allergies=null ยังไม่ทราบ ส่วน [] ยืนยันว่าไม่มีการแพ้ที่ทราบ ส่วน data เป็น dict ที่ตรวจตาม kind ด้วย inspect_record ไม่ได้มี JSON schema แยกครบทุก kind ต้องอ่านตารางนี้ร่วมกับ services/schemas.py ในชุด runtime อย่าสร้าง fields นอก allowlist

## ตรวจและยืนยัน

1. chat/journal เสนอร่าง แสดง/แก้รายการได้ ขอเมนูไม่ต้องบันทึก
2. batch-preview → แสดง checks/errors/missing และ can_confirm ข้อมูลเล่าไม่ครบอาจ can_record=true แต่ต้องแสดงว่ายังไม่ครบ ไม่ใช่ clinical pass
3. requires_consent → ให้ผู้ใช้เลือกเอง เพิ่ม consent record แล้ว preview ใหม่ Batch สูงสุด30รายการ จัดไม่เกิน29เมื่อรวม consent
4. confirm หลังผู้ใช้กดเท่านั้น UUID ใหม่ต่อ operation key เดิมสำหรับ retry operation เดิม ยกเลิกไม่ confirm
5. แก้โดย previous_id ผ่าน preview/confirm; ลบผ่าน delete-preview/confirm จำกัด owner
6. draft อยู่ในหน่วยความจำประมาณ30นาที/หมดหลัง restart 404 ให้ตรวจสถานะบันทึกก่อนสร้างร่างใหม่ ถ้ายืนยันก่อนหน้าอาจสำเร็จแล้ว อย่า preview ซ้ำแล้ว auto-confirm จนซ้ำ

actions allowlist: navigate(page overview/profile/record/plan/chat/knowledge), records, journal(text/captured_at), plan(start_date), delete_records(scope/record_ids), export ไม่รู้จักให้ข้าม ห้ามรันโค้ด/SQL/URL ตามโมเดล และห้ามโมเดล confirm เอง

## อาหารและแคลอรี

ข้าวกับไข่พะโล้เป็น record เดียว data.components เช่น [{"name":"ข้าว","quantity":2,"unit":"ทัพพี"},{"name":"ไข่พะโล้","quantity":1,"unit":"ส่วน"}] เว้น quantity/unit ระดับมื้อ แก้ components แล้วส่งกลับ preview/food-energy energy.kcal รวมครั้งเดียว energy.components แสดงแยกส่วน partial ต้องแสดงว่ายังรวมไม่ครบ unknown/null ไม่ใช่0 assumed_portion ต้องแสดงว่าใช้หน่วยอ้างอิง สูตรจริงต่างกันได้

summary รวมเฉพาะมื้อยืนยัน refresh หลังยืนยัน/แก้/ลบ อย่าบวก parent และ components ซ้ำ แสดงที่มา/basis โดยเฉพาะสูตรเด็กวัยเรียนและจานตัวอย่างที่ไม่เท่ากับทุกจานผู้ใหญ่ ฐานยังไม่ครบทุกเมนู ไม่สร้างตัวเลขจาก AI ความรู้ทั่วไปใช้ RAG/ช่องค้น MedlinePlus ที่ควบคุม ไม่ส่งประวัติผู้ใช้ไปค้นภายนอก

## Error และส่งต่อ runtime

401 กุญแจ/เซสชันผิด, 403 CSRF/Origin, 422 รูปแบบ/validation, 404 รายการ/draft หมดอายุ, 429 โมเดล/ร่างกำลังเต็ม, 503 ยังไม่ตั้งกุญแจ/โมเดลไม่พร้อม HTTP200 อาจมี unknown/no_records/needs_clarification ต้องอ่าน payload ด้วย

จากโปรเจกต์ต้นฉบับรัน `.venv/bin/python scripts/export_runtime.py` ได้ dist/ruamwan-ai-macos-0.10.0 พร้อม manifest SHA256 ตรวจด้วย `.venv/bin/python scripts/export_runtime.py --verify dist/ruamwan-ai-macos-0.10.0` ชุดรวม API/base/adapter intent-menu/catalog/RAG/client/docs ไม่รวม .secrets/.env/ฐานข้อมูลผู้ใช้/เซสชัน/ข้อมูลฝึก

ก่อนเปิดสาธารณะต้องตั้ง authorization เว็บไซต์, TLS gateway, resource limits, backup/restore และนโยบายข้อมูล ไม่ใช่การรับรองทางคลินิกหรือรับประกันไม่มีข้อผิดพลาด โมเดลต้นทาง Apache2.0 พร้อมเงื่อนไข OpenTyphoon ใน model card แนบ ไม่รวมเอกสาร/ภาพโภชนาการทั้งชุดหรืออ้างสิทธิ์เผยแพร่ฐาน ThaiFCD
