"""Software contract tests; not patient or clinical evaluation data."""
import hashlib
import json

import pytest

from scripts.fetch_finetune_sources import summary_pairs
from services.model_runtime import adapter_for
from services.model_tasks import intent_messages, model_task, parse_intent
from services.chat_routing import classification_messages
from services.journal import classification_prompt
from services.learned_assistant import learned_request


def test_download_extractor_uses_only_source_summary_and_adjacent_answer_blocks():
    html = '<h3>Outside?</h3><p>Exclude</p><div id="topic-summary"><h3>What is this?</h3><p>Original <a>answer</a>.</p><ul><li>First</li><li>Second</li></ul><h3>Other?</h3><p>Another.</p></div><p>Copyrighted linked material</p>'
    pairs = summary_pairs(html)
    assert pairs == [{'question': 'What is this?', 'answer': 'Original answer .\n\nFirst Second'}, {'question': 'Other?', 'answer': 'Another.'}]
    with pytest.raises(ValueError): summary_pairs('<p>No summary</p>')


def test_model_intents_are_exact_allowlisted_descriptions_only():
    assert parse_intent('{"intent":"usage_help"}') == {'intent': 'usage_help'}
    for value in ['{"intent":"execute_sql"}', '{"intent":"delete_record","sql":"DROP"}', '[]', 'null']:
        with pytest.raises((ValueError, TypeError)): parse_intent(value)


def test_task_identification_does_not_grant_health_chat_an_adapter():
    assert model_task(intent_messages('SOFTWARE TEST ONLY')) == 'intent'
    assert model_task(classification_messages('SOFTWARE TEST ONLY')) == 'route'
    assert model_task([{'role': 'system', 'content': classification_prompt(['SOFTWARE TEST ONLY'])}]) == 'journal'
    assert model_task([{'role': 'user', 'content': 'Choose up to 3 meal IDs from eligible only.'}]) == 'health_chat'


def registry(tmp_path, **extra):
    adapter = tmp_path / 'adapters/reviewed'; adapter.mkdir(parents=True)
    weights = adapter / 'adapters.safetensors'; weights.write_bytes(b'SOFTWARE TEST ONLY')
    (adapter / 'adapter_config.json').write_text('{}')
    (tmp_path / 'models').mkdir()
    data = {'status': 'evaluated', 'adapter': 'adapters/reviewed', 'enabled_tasks': ['extract'], 'sha256': hashlib.sha256(weights.read_bytes()).hexdigest(), **extra}
    (tmp_path / 'models/runtime-adapter.json').write_text(json.dumps(data))
    return adapter


def test_only_enabled_task_with_matching_weights_can_load(tmp_path):
    adapter = registry(tmp_path)
    assert adapter_for('extract', tmp_path) == str(adapter)
    assert adapter_for('intent', tmp_path) is None
    assert adapter_for('health_chat', tmp_path) is None
    (adapter / 'adapters.safetensors').write_bytes(b'CHANGED')
    assert adapter_for('extract', tmp_path) is None


@pytest.mark.parametrize('override', [{'status': 'training'}, {'adapter': '../outside'}, {'sha256': 'incorrect'}])
def test_runtime_fail_closed_for_unapproved_or_changed_artifacts(tmp_path, override):
    registry(tmp_path, **override)
    assert adapter_for('extract', tmp_path) is None


def test_learned_help_is_concise_and_does_not_propose_writes():
    reply = learned_request('คุยกับคุณเรื่องไหนได้บ้าง', lambda m: {'output': '{"intent":"usage_help"}'})
    assert reply['status'] == 'usage_help'
    assert not reply.get('actions')
    assert len(reply['answer']) < 500


def test_learned_intent_cannot_make_unrelated_text_eligible_or_execute_delete():
    calls = []
    def model(messages):
        calls.append(messages)
        return {'output': '{"intent":"delete_record"}'}
    assert learned_request('ดอกไม้คืออะไร', model) is None
    assert learned_request('เขียนเว็บสุขภาพ', model) is None
    assert not calls
    reply = learned_request('เอาบันทึกที่ผิดออก', model)
    assert reply['actions'] == []
    assert 'ยืนยัน' in reply['answer']
    assert learned_request('ช่วยดูบันทึก', lambda m: {'output': '{"intent":"health"}'}) is None


def test_learned_navigation_uses_only_known_pages_and_malformed_output_falls_back():
    reply = learned_request('พาไปหน้าโปรไฟล์', lambda m: {'output': '{"intent":"navigate"}'})
    assert reply['actions'] == [{'type': 'navigate', 'page': 'profile', 'label': 'เปิดโปรไฟล์'}]
    assert learned_request('พาไปเว็บอื่น', lambda m: {'output': '{"intent":"navigate"}'}) is None
    assert learned_request('คุยกับคุณเรื่องไหนได้บ้าง', lambda m: {'output': 'invalid'}) is None


def test_specialist_task_does_not_replace_other_task_adapters(tmp_path):
    common = registry(tmp_path, enabled_tasks=['extract', 'intent'])
    specialist = tmp_path / 'adapters/specialist'; specialist.mkdir()
    (specialist / 'adapter_config.json').write_text('{}')
    weights = specialist / 'adapters.safetensors'; weights.write_bytes(b'SPECIALIST SOFTWARE TEST')
    path = tmp_path / 'models/runtime-adapter.json'
    data = json.loads(path.read_text())
    data['task_adapters'] = {'extract': {'adapter': 'adapters/specialist', 'sha256': hashlib.sha256(weights.read_bytes()).hexdigest()}}
    path.write_text(json.dumps(data))
    assert adapter_for('extract', tmp_path) == str(specialist)
    assert adapter_for('intent', tmp_path) == str(common)
    weights.write_bytes(b'CHANGED')
    assert adapter_for('extract', tmp_path) is None
    assert adapter_for('intent', tmp_path) == str(common)


def test_invalid_registry_shape_falls_back(tmp_path):
    registry(tmp_path)
    (tmp_path / 'models/runtime-adapter.json').write_text('[]')
    assert adapter_for('extract', tmp_path) is None
