"""SOFTWARE TEST ONLY: quick answers for presets, identity and bare record commands."""
from datetime import datetime
import pytest
from services.chat_presets import preset_request, ZONE

NOW = datetime(2026, 11, 13, 12, 10, tzinfo=ZONE)


def rec(kind, data, day='2026-11-13', clock=None, text='SOFTWARE TEST'):
    return {'id': kind + str(len(str(data))), 'version': 1, 'kind': kind, 'data': data, 'text': text,
            'journal': {'date': day, 'clock': clock, 'period': 'noon'}, 'created_at': day + 'T05:00:00Z'}


ROWS = [rec('meal', {'name': 'ข้าวหมูกรอบ'}, clock='12:00:00'),
        rec('medication', {'name': 'เมทฟอร์มิน', 'dose': 500, 'unit': 'mg'}, clock='08:00:00'),
        rec('measurement', {'name': 'glucose', 'value': 126, 'unit': 'mg/dL', 'context': 'before-meal'})]


@pytest.mark.parametrize('q', ['คุณคือใคร', 'แนะนำตัวหน่อย', 'Baobuddy คืออะไร', 'เป็นใครครับ'])
def test_identity_introduces_baobuddy(q):
    r = preset_request(q, [], NOW)
    assert r['status'] == 'identity' and 'Baobuddy' in r['answer'] and 'ผม' in r['answer'] and 'ฉัน' not in r['answer']


def test_daily_summary_groups_today_by_category():
    r = preset_request('สรุปวันนี้', ROWS, NOW)
    assert r['status'] == 'daily_summary' and 'วันนี้ (13 พ.ย.)' in r['answer']
    assert '08:00 น. · เมทฟอร์มิน 500 mg' in r['answer'] and '12:00 น. · ข้าวหมูกรอบ' in r['answer']
    assert 'ยังไม่มีบันทึกกิจกรรม' in r['answer'] and len(r['record_sources']) == 3


def test_medicine_today_and_empty_category_offers_page():
    assert 'เมทฟอร์มิน' in preset_request('ยาวันนี้', ROWS, NOW)['answer']
    empty = preset_request('กิจกรรมวันนี้', ROWS, NOW)
    assert empty['status'] == 'no_records' and empty['actions'][0]['page'] == 'exercise'


def test_tracking_lists_latest_measurement():
    r = preset_request('ติดตามสุขภาพ', ROWS, NOW)
    assert 'น้ำตาล 126 mg/dL · 13 พ.ย. · ก่อนอาหาร' in r['answer']


def test_bare_record_command_guides_instead_of_saving_the_word():
    r = preset_request('บันทึกอาหาร', [], NOW)
    assert r['status'] == 'record_help' and r['actions'][0]['page'] == 'food'
    assert preset_request('บันทึกเช้ากินโจ๊ก', [], NOW) is None  # real content goes to the record flow
    assert preset_request('บันทึกยอดขายวันนี้', [], NOW) is None
