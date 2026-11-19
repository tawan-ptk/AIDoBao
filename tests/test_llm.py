"""SOFTWARE TEST ONLY: OpenRouter client contract. No network, fake key."""
import json
import threading
import httpx
import pytest
from fastapi import HTTPException
from services import llm, chat_model
from services.extraction import extraction_prompt
from services.chat_routing import classification_messages


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-or-SOFTWARE-TEST')
    monkeypatch.delenv('OPENROUTER_ALLOW_DATA_COLLECTION', raising=False)
    monkeypatch.setattr(llm.time, 'sleep', lambda s: None)


def client_returning(content, sent, status=200, finish='stop'):
    def handler(request):
        sent.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, json={'error': {'message': 'PRIVATE PROMPT ECHO'}})
        return httpx.Response(200, json={'model': 'software/model', 'choices': [
            {'message': {'content': content}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'cost': 0.00001}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_route_uses_task_model_schema_fewshot_and_private_providers():
    sent = []
    out = llm.generate(classification_messages('ปวดหัวบ่อย'), max_tokens=120,
                       client=client_returning('{"route":"health","topic":null}', sent))
    body = sent[0]
    assert body['model'] == llm.DEFAULT_TASK_MODEL
    assert body['response_format']['json_schema']['strict'] is True
    assert body['provider'] == {'require_parameters': True, 'data_collection': 'deny'}
    # system, worked examples, then the real question last
    assert body['messages'][0]['role'] == 'system' and body['messages'][-1]['content'] == 'ปวดหัวบ่อย'
    assert len(body['messages']) > 3 and body['messages'][1]['role'] == 'user'
    assert json.loads(out['output']) == {'route': 'health', 'topic': None}
    assert out['metrics']['provider'] == 'openrouter' and out['metrics']['cost_usd'] == 0.00001


def test_health_chat_is_zero_shot_plain_text_on_chat_model():
    sent = []
    messages = [{'role': 'system', 'content': 'คุณคือผู้ช่วยความรู้สุขภาพ'}, {'role': 'user', 'content': 'เบาหวานคืออะไร'}]
    out = llm.generate(messages, client=client_returning('เบาหวานคือ… ครับ', sent))
    assert sent[0]['model'] == llm.DEFAULT_CHAT_MODEL and 'response_format' not in sent[0]
    assert len(sent[0]['messages']) == 2 and out['output'] == 'เบาหวานคือ… ครับ'


def test_extraction_cleans_fence_and_keeps_only_quoted_fields(monkeypatch):
    text = 'กินข้าวมันไก่ 1 จาน'
    reply = '```json\n{"data":{"name":"ข้าวมันไก่","quantity":1,"unit":"จาน","occurred_at":null,"food_state":"cooked"},' \
            '"evidence":{"name":"ข้าวมันไก่","quantity":"1","unit":"จาน","occurred_at":null,"food_state":null}}\n```'
    sent = []
    fake = client_returning(reply, sent)
    monkeypatch.setattr(llm.httpx, 'Client', lambda **k: fake)
    out = llm.extract_record('meal', text)
    assert sent[0]['messages'][0]['content'] == extraction_prompt('meal')
    data = out['record']['data']
    assert data['name'] == 'ข้าวมันไก่' and data['quantity'] == 1 and data['unit'] == 'จาน'
    assert data['food_state'] is None  # no supporting span, so it is not accepted
    assert out['metrics']['extraction_status'] == 'proposal'


@pytest.mark.parametrize('status,code', [(401, 503), (402, 503), (429, 429), (500, 503)])
def test_provider_errors_never_echo_provider_text(status, code):
    with pytest.raises(HTTPException) as exc:
        llm.generate([{'role': 'user', 'content': 'x'}], client=client_returning('', [], status=status))
    assert exc.value.status_code == code and 'PRIVATE' not in exc.value.detail


def test_truncated_answer_is_reported_as_length():
    out = llm.generate([{'role': 'user', 'content': 'x'}], client=client_returning('ครึ่ง', [], finish='length'))
    assert out['finish_reason'] == 'length'


def test_generate_chat_prefers_api_and_skips_local_lock(monkeypatch):
    monkeypatch.setattr(llm, 'generate', lambda messages, max_tokens: {'output': 'ok', 'metrics': {}})
    lock = threading.Lock(); lock.acquire()  # busy local model does not matter
    try:
        assert chat_model.generate_chat([{'role': 'user', 'content': 'x'}], lock)['output'] == 'ok'
    finally:
        lock.release()


def test_without_key_local_model_path_is_unchanged(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY')
    assert not llm.available()


def test_web_answer_limits_sites_and_returns_named_sources(monkeypatch):
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'model': 'software/model', 'choices': [{'finish_reason': 'stop', 'message': {
            'content': '**สรุป** ล้างมือบ่อย ๆ ([ddc.moph.go.th](https://ddc.moph.go.th/a))\n* ฉีดวัคซีน',
            'annotations': [{'type': 'url_citation', 'url_citation': {'url': 'https://ddc.moph.go.th/a', 'title': 'Home | กรมควบคุมโรค'}},
                            {'type': 'url_citation', 'url_citation': {'url': 'http://insecure.example/b', 'title': 'x'}}]}}]})
    fake = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm.httpx, 'Client', lambda **k: fake)
    out = llm.web_answer([{'role': 'user', 'content': 'ป้องกันไข้หวัดใหญ่ยังไง'}])
    plugin = sent[0]['plugins'][0]
    assert plugin['id'] == 'web' and 'medlineplus.gov' in plugin['include_domains']
    assert out['output'] == 'สรุป ล้างมือบ่อย ๆ\n• ฉีดวัคซีน'
    assert out['citations'] == [{'publisher': 'กรมควบคุมโรค', 'heading': 'กรมควบคุมโรค', 'url': 'https://ddc.moph.go.th/a',
                                 'retrieval': 'web', 'content_type': 'web_search'}]
