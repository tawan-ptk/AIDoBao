"""Fresh v3 validation/selection/test; preserve v2 results and task adapters."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'reports/finetune-v3-evaluation-progress.json'


def read(path): return json.loads((ROOT / path).read_text())


def command(label, *args):
    PROGRESS.write_text(json.dumps({'status': 'running', 'stage': label}, indent=2))
    print(label, flush=True)
    with (ROOT / f'logs/{label}.log').open('x') as log:
        subprocess.run([sys.executable, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)


def stage(step, selected=False):
    target = ROOT / ('adapters/finetune-v3-selected' if selected else f'adapters/finetune-v3-step{step}')
    if target.exists(): raise ValueError('Adapter path already exists')
    target.mkdir()
    shutil.copyfile(ROOT / 'adapters/finetune-v3/adapter_config.json', target / 'adapter_config.json')
    shutil.copyfile(ROOT / f'adapters/finetune-v3/{step:07}_adapters.safetensors', target / 'adapters.safetensors')
    return str(target.relative_to(ROOT))


def main():
    deadline = time.monotonic() + 7200
    while True:
        try:
            if read('reports/finetune-v3-training.json')['status'] == 'completed': break
        except (OSError, ValueError): pass
        if time.monotonic() > deadline: raise TimeoutError('Training did not complete')
        time.sleep(5)
    time.sleep(2)
    candidates = []
    worker = ['scripts/finetune_worker.py', 'evaluate', '--data', 'data/prepared/finetune-v3', '--split', 'valid', '--generation-limit', '12']
    for step in (457, 914):
        path = stage(step)
        output = f'reports/finetune-v3-valid-step{step}.json'
        command(f'finetune-v3-valid-step{step}', *worker, '--adapter', path, '--output', output)
        result = read(output)
        assert result['status'] == 'completed' and result['split'] == 'valid'
        candidates.append({'step': step, 'structured_exact': sum(m['exact'] for m in result['metrics'].values()),
                           'mean_task_loss': sum(m['assistant_loss'] for m in result['metrics'].values()) / len(result['metrics'])})
    winner = min(candidates, key=lambda c: (-c['structured_exact'], c['mean_task_loss'], c['step']))
    selected = stage(winner['step'], selected=True)
    weights = ROOT / selected / 'adapters.safetensors'
    selection = {'status': 'selected_before_test', 'adapter': selected, 'sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
                  'selected_step': winner['step'], 'candidates': candidates, 'test_used_for_selection': False,
                  'selected_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (ROOT / 'reports/finetune-v3-selection.json').write_text(json.dumps(selection, indent=2))
    worker = ['scripts/finetune_worker.py', 'evaluate', '--data', 'data/prepared/finetune-v3', '--split', 'test', '--all-commands']
    for mode in ('base', 'adapter'):
        extra = ['--adapter', selected] if mode == 'adapter' else []
        command(f'finetune-v3-test-{mode}', *worker, *extra, '--output', f'reports/finetune-v3-test-{mode}.json')
    before = read('reports/finetune-v3-test-base.json'); after = read('reports/finetune-v3-test-adapter.json')
    assert before['status'] == after['status'] == 'completed'
    assert {g['id'] for g in before['generations']} == {g['id'] for g in after['generations']}
    registry = read('models/runtime-adapter.json')
    gates = {}
    for task in ('extract', 'route'):
        a = after['metrics'][task]; b = before['metrics'][task]
        cases = [g for g in after['generations'] if g['task'] == task]
        n = a['generated_count']
        passed = n == a['count'] and n > 0 and a['json_valid'] == n and a['exact'] / n >= .9 and a['exact'] >= b['exact'] and all(g['finish_reason'] == 'stop' for g in cases)
        if task == 'extract': passed = passed and len({g['kind'] for g in cases}) == 7
        gates[task] = {'passed': passed, 'base_exact': b['exact'], 'adapter_exact': a['exact'], 'generated_count': n}
        if passed:
            registry.setdefault('task_adapters', {})[task] = {'adapter': selected, 'sha256': selection['sha256']}
            if task not in registry['enabled_tasks']: registry['enabled_tasks'].append(task)
    registry['specialist_gates'] = gates
    registry['specialist_evaluation'] = 'reports/finetune-v3-test-adapter.json'
    (ROOT / 'models/runtime-adapter.json').write_text(json.dumps(registry, indent=2))
    (ROOT / 'reports/finetune-v3-rollout.json').write_text(json.dumps(registry, indent=2))
    PROGRESS.write_text(json.dumps({'status': 'completed', 'stage': 'rollout_written'}, indent=2))
    print(json.dumps(gates, indent=2), flush=True)


if __name__ == '__main__': main()
