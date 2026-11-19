"""Local adapter rollout, enabled per task only after recorded comparisons."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TASKS = frozenset(('extract', 'intent', 'route', 'journal', 'menu'))


def adapter_for(task, root=None):
    root = Path(root or ROOT)
    path = root / 'models/runtime-adapter.json'
    if task not in ALLOWED_TASKS or not path.exists():
        return None
    try:
        registry = json.loads(path.read_text())
        if registry.get('status') != 'evaluated' or task not in registry.get('enabled_tasks', []):
            return None
        entry = registry.get('task_adapters', {}).get(task, registry)
        adapter = (root / entry['adapter']).resolve()
        if not adapter.is_relative_to((root / 'adapters').resolve()):
            return None
        if not (adapter / 'adapter_config.json').is_file():
            return None
        weights = adapter / 'adapters.safetensors'
        if hashlib.sha256(weights.read_bytes()).hexdigest() != entry['sha256']:
            return None
        return str(adapter)
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        return None


def runtime_status(root=None):
    enabled = [task for task in sorted(ALLOWED_TASKS) if adapter_for(task, root)]
    return {'enabled_tasks': enabled, 'health_chat': 'base_with_retrieved_evidence',
            'adapter_active': bool(enabled), 'clinical_validation': False}
