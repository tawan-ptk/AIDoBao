"""Read-only live smoke checks; never confirm a write or use real user data."""
import datetime
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=180) as client:
        session = client.get('/api/session')
        session.raise_for_status()
        data = session.json()
        client.headers['X-CSRF-Token'] = data['csrf']
        checks = []
        before = client.get('/api/records').json()['items']
        for query, expected in [('แนะนำหน่อยว่าฉันจะถามคุณว่าอะไรได้บ้าง', 'usage_help'),
                                ('ดอกไม้คืออะไร', 'out_of_scope'),
                                ('คุยกับคุณเรื่องไหนได้บ้าง', 'usage_help'),
                                ('พาไปหน้าโปรไฟล์', None),
                                ('ลบข้อมูลทั้งหมด', 'management_proposal')]:
            response = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': query}], 'scope': 'auto'})
            response.raise_for_status(); result = response.json()
            if expected: assert result['status'] == expected, result
            if expected == 'out_of_scope': assert not result.get('citations')
            if query == 'พาไปหน้าโปรไฟล์':
                assert any(a.get('type') == 'navigate' and a.get('page') == 'profile' for a in result.get('actions', [])), result
            checks.append({'request': query, 'status': result.get('status'), 'answer': result.get('answer'),
                           'intent_engine': result.get('intent_engine'), 'actions': [a['type'] for a in result.get('actions', [])]})
        extraction = client.post('/api/extract', json={'kind': 'activity', 'text': 'เดิน 16.00'})
        extraction.raise_for_status(); result = extraction.json()
        assert result['record']['data']['name'] == 'เดิน'
        assert result['record']['data']['start'] is None
        checks.append({'request': 'เดิน 16.00', 'record': result['record'], 'model_status': result['model_status'], 'metrics': result['metrics']})
        explicit_start = '2026-05-23T08:00:00+07:00'; explicit_end = '2026-05-23T08:30:00+07:00'
        explicit = client.post('/api/extract', json={'kind': 'activity', 'text': f'เดิน เริ่ม {explicit_start} จบ {explicit_end}'})
        explicit.raise_for_status(); result = explicit.json()
        # Diagnostic of the still-disabled extraction adapter's base fallback.
        # Preserve failures in the report rather than implying all live cases pass.
        expected = {'name': 'เดิน', 'start': explicit_start, 'end': explicit_end}
        passed = all(result['record']['data'].get(k) == v for k, v in expected.items())
        checks.append({'request': 'explicit ISO time regression, synthetic software check only',
                       'passed': passed, 'expected': expected, 'record': result['record'], 'metrics': result['metrics']})
        journal = client.post('/api/journal/prepare', json={'text': 'วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง', 'use_model': False})
        journal.raise_for_status(); result = journal.json()
        assert [item['record']['text'] for item in result['items']] == ['ข้าวขาหมู', 'ต้มยำกุ้ง']
        checks.append({'request': 'multi-category journal regression', 'items': [item['record'] for item in result['items']]})
        learned_journal = client.post('/api/journal/prepare', json={'text': 'รำไทเก๊ก', 'use_model': True})
        learned_journal.raise_for_status(); result = learned_journal.json()
        passed = (len(result['items']) == 1 and result['items'][0]['record']['kind'] == 'activity'
                  and result['items'][0]['record']['text'] == 'รำไทเก๊ก')
        checks.append({'request': 'real journal model fallback, synthetic software check only',
                       'passed': passed, 'engine': result.get('engine'), 'items': result['items'],
                       'unparsed': result['unparsed'], 'metrics': result.get('model_metrics')})
        menu = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': 'ตอนเย็นกินอะไรดี'}], 'scope': 'auto'})
        menu.raise_for_status(); result = menu.json()
        assert result['status'] == 'meal_ideas' and result['menus']
        checks.append({'request': 'real menu catalog integration, not clinical evaluation', 'status': result['status'],
                       'engine': result.get('engine'), 'menu_ids': [m['id'] for m in result['menus']]})
        after = client.get('/api/records').json()['items']
        assert before == after == [], 'Smoke checks must not save/delete any records'
        readiness = client.get('/api/readiness').json()
    report = {'label': 'SOFTWARE LIVE SMOKE ONLY; not fine-tuning or clinical evaluation',
              'checks': checks, 'model_runtime': readiness.get('model_runtime'), 'records_changed': False,
              'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (ROOT / 'reports/finetune-live-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({'checks': len(checks), 'model_runtime': report['model_runtime'], 'records_changed': False}, ensure_ascii=False))


if __name__ == '__main__': main()
