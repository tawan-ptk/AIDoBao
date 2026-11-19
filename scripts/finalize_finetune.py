"""Validation-only selection and task-specific rollout after held-out comparison."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    result = json.loads((ROOT / name).read_text())
    if result.get('status') != 'completed': raise ValueError('Incomplete experiment report')
    return result


def mean_loss(result):
    return sum(m['assistant_loss'] for m in result['metrics'].values()) / len(result['metrics'])


def select():
    path = ROOT / 'reports/finetune-v2-selection.json'
    if path.exists(): raise ValueError('Checkpoint selection already frozen')
    candidates = []
    for step in (302, 604):
        report_path = f'reports/finetune-v2-valid-step{step}.json'
        result = read(report_path)
        if result['split'] != 'valid': raise ValueError('Only validation may choose checkpoints')
        candidates.append({'step': step, 'report': report_path,
                           'structured_exact': sum(m['exact'] for task, m in result['metrics'].items() if task != 'health_qa'),
                           'mean_task_loss': mean_loss(result)})
    winner = min(candidates, key=lambda r: (-r['structured_exact'], r['mean_task_loss'], r['step']))
    selected = ROOT / 'adapters/finetune-v2-selected'
    if selected.exists(): raise ValueError('Selected adapter path already exists')
    selected.mkdir()
    shutil.copyfile(ROOT / 'adapters/finetune-v2/adapter_config.json', selected / 'adapter_config.json')
    shutil.copyfile(ROOT / f'adapters/finetune-v2/{winner["step"]:07}_adapters.safetensors', selected / 'adapters.safetensors')
    result = {'status': 'selected_before_test', 'candidates': candidates, 'selected_step': winner['step'],
              'adapter': str(selected.relative_to(ROOT)), 'sha256': hashlib.sha256((selected / 'adapters.safetensors').read_bytes()).hexdigest(),
              'criterion': 'most exact structured validation generations, then lowest mean task validation loss, then earlier step',
              'test_used_for_selection': False, 'selected_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


def publish():
    selection = json.loads((ROOT / 'reports/finetune-v2-selection.json').read_text())
    base = read('reports/finetune-v2-test-base.json')
    adapted = read('reports/finetune-v2-test-adapter.json')
    if base['split'] != 'test' or adapted['split'] != 'test': raise ValueError('Missing held-out comparison')
    if {g['id'] for g in base['generations']} != {g['id'] for g in adapted['generations']}: raise ValueError('Unequal evaluation cases')
    if adapted['adapter'] != selection['adapter']: raise ValueError('Different adapter evaluated')
    if not base['all_commands'] or not adapted['all_commands']: raise ValueError('Every command test must be generated')
    weights = ROOT / selection['adapter'] / 'adapters.safetensors'
    if hashlib.sha256(weights.read_bytes()).hexdigest() != selection['sha256']: raise ValueError('Selected weights changed')
    minimum = {'extract': 7, 'intent': 20, 'route': 6, 'menu': 4, 'journal': 2}
    gates = {}; enabled = []
    for task, min_count in minimum.items():
        score = adapted['metrics'][task]; before = base['metrics'][task]
        cases = [g for g in adapted['generations'] if g['task'] == task]
        n = score['generated_count']
        passed = n >= min_count and n == score['count'] and score['json_valid'] == n and score['exact'] / n >= .9 and score['exact'] >= before['exact'] and all(g['finish_reason'] == 'stop' for g in cases)
        if task == 'extract': passed = passed and len({g['kind'] for g in cases}) == 7
        gates[task] = {'passed': passed, 'generated_count': n, 'adapter_exact': score['exact'],
                       'base_exact': before['exact'], 'all_json_valid': score['json_valid'] == n,
                       'complete_generations': sum(g['finish_reason'] == 'stop' for g in cases)}
        if passed: enabled.append(task)
    registry = {'status': 'evaluated', 'adapter': selection['adapter'], 'sha256': selection['sha256'],
                'enabled_tasks': enabled, 'gates': gates, 'health_chat_enabled': False,
                'scope': 'Engineering rollout based on synthetic command tests; not real-user or clinical validation',
                'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (ROOT / 'models/runtime-adapter.json').write_text(json.dumps(registry, indent=2))
    (ROOT / 'reports/finetune-v2-rollout.json').write_text(json.dumps(registry, indent=2))
    print(json.dumps(registry, indent=2))


def stage():
    # Stage only the two candidates declared before test evaluation.
    for step in (302, 604):
        target = ROOT / f'adapters/finetune-v2-step{step}'
        if target.exists(): raise ValueError('Candidate already staged')
        target.mkdir()
        shutil.copyfile(ROOT / 'adapters/finetune-v2/adapter_config.json', target / 'adapter_config.json')
        shutil.copyfile(ROOT / f'adapters/finetune-v2/{step:07}_adapters.safetensors', target / 'adapters.safetensors')
    print('Staged checkpoints 302 and 604; no test results read')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('action', choices=['stage', 'select', 'publish']); a = ap.parse_args()
    {'stage': stage, 'select': select, 'publish': publish}[a.action]()
