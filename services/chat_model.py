"""Offline MLX chat worker; no conversation persistence or health-content logs."""
import json
import pathlib
import subprocess
import sys
from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[1]

def generate_chat(messages, model_lock, max_tokens=1400):
    # Hosted model (OpenRouter) when configured: no local weights, no single-run lock.
    from services import llm
    if llm.available():
        return llm.generate(messages, max_tokens=max_tokens)
    if not (ROOT/'models/typhoon-4bit/config.json').exists():
        raise HTTPException(503, 'โมเดลในเครื่องยังไม่พร้อม กรุณาตรวจโฟลเดอร์ models/typhoon-4bit')
    if not model_lock.acquire(blocking=False):
        raise HTTPException(429, 'โมเดลกำลังทำงาน กรุณารอสักครู่แล้วส่งคำถามอีกครั้ง')
    try:
        try:
            run = subprocess.run(
                [sys.executable, str(ROOT/'scripts/inference.py'), '--task', 'generate', '--max-tokens', str(max_tokens)],
                input=json.dumps({'messages': messages}, ensure_ascii=False),
                text=True, capture_output=True, timeout=180, cwd=ROOT,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(504, 'โมเดลใช้เวลานานเกินไป ลองถามให้สั้นลงแล้วส่งอีกครั้ง') from None
        if run.returncode:
            raise HTTPException(503, 'โหลดโมเดลไม่สำเร็จ กรุณาเปิดเซิร์ฟเวอร์ผ่าน scripts/run_demo.py และตรวจสิทธิ Metal')
        try:
            result = json.loads(run.stdout)
            if not isinstance(result['output'], str) or not result['output'].strip():
                raise ValueError('empty model answer')
            return result
        except (ValueError, KeyError, TypeError):
            raise HTTPException(503, 'โมเดลไม่ได้ส่งคำตอบที่อ่านได้ กรุณาลองส่งอีกครั้ง') from None
    finally:
        model_lock.release()
