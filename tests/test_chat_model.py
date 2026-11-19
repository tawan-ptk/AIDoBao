"""SOFTWARE TEST ONLY: worker failures expose no prompt or stderr."""
import subprocess
import threading
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from services import chat_model

@pytest.fixture(autouse=True)
def software_model_path(tmp_path,monkeypatch):
    config=tmp_path/'models/typhoon-4bit/config.json'
    config.parent.mkdir(parents=True);config.write_text('{}')
    monkeypatch.setattr(chat_model,'ROOT',tmp_path)

@pytest.mark.parametrize('failure,code', [('timeout',504),('process',503),('json',503),('empty',503)])
def test_worker_releases_model_lock_and_reports_actionable_error(monkeypatch,failure,code):
    lock=threading.Lock()
    def run(*args,**kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired('software',1)
        return SimpleNamespace(returncode=1 if failure=='process' else 0,
                               stdout='invalid' if failure=='json' else '{"output":""}',stderr='PRIVATE TEST CONTENT')
    monkeypatch.setattr(chat_model.subprocess,'run',run)
    with pytest.raises(HTTPException) as exc:chat_model.generate_chat([{'role':'user','content':'SOFTWARE TEST ONLY'}],lock)
    assert exc.value.status_code==code and 'PRIVATE TEST CONTENT' not in exc.value.detail
    assert not lock.locked()

def test_busy_model_does_not_start_second_worker(monkeypatch):
    lock=threading.Lock();lock.acquire()
    def forbidden(*a,**k):raise AssertionError('second worker must not start')
    monkeypatch.setattr(chat_model.subprocess,'run',forbidden)
    try:
        with pytest.raises(HTTPException) as exc:chat_model.generate_chat([],lock)
        assert exc.value.status_code==429 and lock.locked()
    finally:lock.release()
