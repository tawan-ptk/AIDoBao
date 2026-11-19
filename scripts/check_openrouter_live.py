"""Live check of the OpenRouter model on a few synthetic questions (costs < 1 baht).

    .venv/bin/python scripts/check_openrouter_live.py

Uses only made-up example text. Prints answers, timing and cost; never the key.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.env_file import load_env  # noqa: E402

load_env(ROOT / '.env')
from services import llm  # noqa: E402
from services.chat import model_messages  # noqa: E402
from services.chat_routing import classification_messages  # noqa: E402
from services.model_tasks import intent_messages, parse_intent  # noqa: E402
from services.rag import Retriever  # noqa: E402

if not llm.available():
    sys.exit('OPENROUTER_API_KEY is not set in .env')

total = 0.0


def show(label, result):
    global total
    m = result['metrics']
    total += m.get('cost_usd') or 0
    print(f"\n== {label} · {m['model']} · {m['generation_seconds']}s · ${m.get('cost_usd')}")
    print(result['output'] if isinstance(result.get('output'), str) else json.dumps(result, ensure_ascii=False)[:600])


question = 'เป็นเบาหวานควรกินอะไร'
evidence = Retriever(ROOT / 'data/knowledge/chunks.jsonl').answer(question)['citations'][:2]
show('health chat', llm.generate(model_messages([{'role': 'user', 'content': question}], evidence)))
show('route', llm.generate(classification_messages('ปวดหัวบ่อยตอนเช้าเกิดจากอะไร'), max_tokens=120))
intent = llm.generate(intent_messages('ช่วยเปิดหน้าบันทึกอาหารให้หน่อย'), max_tokens=80)
show('intent', intent)
parse_intent(intent['output'])
for kind, text in [('meal', 'เที่ยงนี้กินข้าวมันไก่ 1 จาน'), ('measurement', 'น้ำตาลก่อนอาหารเช้าวัดได้ 126 mg/dL')]:
    out = llm.extract_record(kind, text)
    out['metrics'].setdefault('model', llm.model_for('extract'))
    print(f"\n== extract {kind} · {out['metrics'].get('model')} · {out['metrics'].get('generation_seconds')}s · ${out['metrics'].get('cost_usd')}")
    total += out['metrics'].get('cost_usd') or 0
    print(out['metrics']['extraction_status'], json.dumps(out['record']['data'], ensure_ascii=False))
print(f'\nTotal cost: ${total:.5f}')
