"""Sequential fresh-process evaluation after the main training finishes.

Only the finalizer can enable the adapter; no test outcomes change training.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'reports/finetune-v2-evaluation-progress.json'


def run(label, command):
    PROGRESS.write_text(json.dumps({'status': 'running', 'stage': label,
                                   'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}, indent=2))
    print(label, flush=True)
    with (ROOT / f'logs/{label}.log').open('x') as log:
        subprocess.run([sys.executable, *command], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--after-training', action='store_true'); a = ap.parse_args()
    if a.after_training:
        deadline = time.monotonic() + 7200
        while True:
            report = ROOT / 'reports/finetune-v2-training.json'
            if report.exists():
                try:
                    if json.loads(report.read_text()).get('status') == 'completed': break
                except ValueError: pass
            if time.monotonic() > deadline: raise TimeoutError('Training did not complete')
            time.sleep(5)
        # Allow the training process to release its model before evaluation.
        time.sleep(2)
    run('finetune-v2-stage', ['scripts/finalize_finetune.py', 'stage'])
    worker = ['scripts/finetune_worker.py', 'evaluate', '--split', 'valid', '--generation-limit', '12']
    run('finetune-v2-valid-base', [*worker, '--output', 'reports/finetune-v2-valid-base.json'])
    for step in (302, 604):
        run(f'finetune-v2-valid-step{step}', [*worker, '--adapter', f'adapters/finetune-v2-step{step}', '--output', f'reports/finetune-v2-valid-step{step}.json'])
    run('finetune-v2-select', ['scripts/finalize_finetune.py', 'select'])
    worker = ['scripts/finetune_worker.py', 'evaluate', '--split', 'test', '--generation-limit', '24', '--all-commands']
    run('finetune-v2-test-base', [*worker, '--output', 'reports/finetune-v2-test-base.json'])
    run('finetune-v2-test-adapter', [*worker, '--adapter', 'adapters/finetune-v2-selected', '--output', 'reports/finetune-v2-test-adapter.json'])
    run('finetune-v2-publish', ['scripts/finalize_finetune.py', 'publish'])
    PROGRESS.write_text(json.dumps({'status': 'completed', 'stage': 'rollout_written',
                                   'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}, indent=2))
    print('Evaluation and gated rollout completed', flush=True)


if __name__ == '__main__': main()
