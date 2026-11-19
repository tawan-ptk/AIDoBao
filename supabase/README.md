# Interface สำหรับรอบเชื่อมต่อ Supabase

ยังไม่เชื่อมต่อหรือรัน SQL กับบริการจริง ตั้ง environment ตาม `.env.example` หลังเตรียม Auth และ backend ที่เชื่อถือได้ อ่าน `services/supabase.py` สำหรับ payload และ user-JWT calls

`migrations/001_initial.sql` ใช้ `auth.uid()` และ Supabase roles ต้องรันใน Supabase-compatible PostgreSQL parser ผ่านไม่ได้พิสูจน์ RLS หรือ transaction concurrency ใช้ staging และทดสอบผู้ใช้ A/B, anonymous, retry, stale revisions และ rollback ก่อน production

ตัวอย่าง envelope ต่อไปนี้เป็นคำอธิบาย schema ไม่มีข้อมูลผู้ป่วย:

```json
{
  "owner_id": "<authenticated user UUID>",
  "payload": {},
  "origin": "user_reported",
  "provenance": {"source": "<original source>", "evidence": {}},
  "previous_id": null,
  "program_status": "pass",
  "user_status": "confirmed",
  "idempotency_key": "<unique confirmation key>"
}
```

ใช้ `record_payload` เพื่อสร้างค่าจริงตาม contract แทนคัดลอก placeholder นี้ ข้อเสนอแผนต้องมาจาก backend ที่รัน scheduler/rules แล้วเท่านั้น RPC ยืนยันใช้ revision และ idempotency key ไม่ให้ client ตั้ง program status แล้วถือว่า valid โมเดล 4B อยู่บน Mac ไม่อยู่ใน Edge Functions
