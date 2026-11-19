"""Export integrity and privacy tests with tiny software-only model files."""
import json
import pytest
from scripts.export_runtime import export,verify,FILES

def test_bundle_contains_allowlisted_runtime_only_and_detects_tampering(tmp_path):
    root=tmp_path/'source';root.mkdir()
    for name in FILES:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
    for name in ['app/main.py','services/nutrition.py','demo/app.js','models/typhoon-4bit/model.safetensors','adapters/finetune-v2-selected/adapters.safetensors']:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('SOFTWARE FIXTURE')
    private=['data/local.sqlite3','data/exports/private.json','app/.env','services/private.sqlite3','models/typhoon-4bit/private.json','adapters/finetune-v2-selected/train.jsonl']
    for name in private:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('PRIVATE SOFTWARE SENTINEL')
    destination=tmp_path/'bundle';r=export(destination,root)
    assert r['verified'] and not any((destination/name).exists() for name in private)
    assert json.loads((destination/'manifest.json').read_text())['enabled_adapter_tasks']==['intent','menu']
    (destination/'app/main.py').write_text('CHANGED')
    with pytest.raises(ValueError,match='Integrity failed'):verify(destination)

def test_existing_destination_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='Destination exists'):export(tmp_path,tmp_path)

def test_symlink_to_private_file_is_rejected(tmp_path):
    root=tmp_path/'source';root.mkdir()
    for name in FILES:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
    secret=tmp_path/'private';secret.write_text('SOFTWARE PRIVATE SENTINEL')
    (root/'app').mkdir();(root/'app/main.py').symlink_to(secret)
    with pytest.raises(ValueError,match='Symlink'):export(tmp_path/'bundle',root)
