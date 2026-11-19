"""Use installed official MLX-LM trainer, with immutable data and telemetry.

Training/checkpoint validation/test are separate process invocations. This
worker cannot read app stores and does not deploy its output automatically.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MLX_MPI_LIBNAME'] = str(ROOT / 'models/MPI_DISABLED_LOCAL_ONLY.dylib')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'


def load_rows(data, split):
    audit = json.loads((data / 'audit.json').read_text())
    path = data / f'{split}.jsonl'
    if hashlib.sha256(path.read_bytes()).hexdigest() != audit['files'][split]['sha256']:
        raise ValueError('Frozen data checksum mismatch')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != audit['counts'][split]: raise ValueError('Data count mismatch')
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['train', 'evaluate'])
    ap.add_argument('--data', default='data/prepared/finetune-v2')
    ap.add_argument('--config')
    ap.add_argument('--adapter')
    ap.add_argument('--split', choices=['valid', 'test'], default='valid')
    ap.add_argument('--output', required=True)
    ap.add_argument('--generation-limit', type=int, default=24)
    ap.add_argument('--all-commands', action='store_true')
    args = ap.parse_args()
    data = ROOT / args.data
    output = ROOT / args.output
    if output.exists(): raise ValueError('Refusing to overwrite experiment report')
    output.parent.mkdir(parents=True, exist_ok=True)
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from mlx_lm.tuner.datasets import ChatDataset, CacheDataset
    from mlx_lm.tuner.trainer import evaluate
    mx.distributed.init(backend='ring'); mx.random.seed(42)
    started = time.monotonic()
    if args.mode == 'train':
        import yaml
        from mlx_lm.lora import CONFIG_DEFAULTS, train_model
        from mlx_lm.tuner.callbacks import TrainingCallback
        config = {**CONFIG_DEFAULTS, **yaml.safe_load((ROOT / args.config).read_text())}
        if (ROOT / config['data']).resolve() != data.resolve(): raise ValueError('Config/data mismatch')
        config['model'] = str(ROOT / config['model'])
        config['adapter_path'] = str(ROOT / config['adapter_path'])
        if (Path(config['adapter_path']) / 'adapters.safetensors').exists():
            raise ValueError('Refusing to overwrite existing adapter')
        train_rows = load_rows(data, 'train'); valid_rows = load_rows(data, 'valid')
        model, tokenizer = load(config['model'], tokenizer_config={'trust_remote_code': False})
        for row in train_rows + valid_rows:
            length = len(tokenizer.apply_chat_template(row['messages'], tokenize=True, return_dict=False))
            if length > config['max_seq_length']: raise ValueError('Would truncate training/validation answer')
        events = []

        class Callback(TrainingCallback):
            def on_train_loss_report(self, info):
                events.append({'event': 'train', **info})
                output.write_text(json.dumps({'status': 'running', 'events': events}, indent=2))

            def on_val_loss_report(self, info):
                events.append({'event': 'validation_before_step', **info})
                output.write_text(json.dumps({'status': 'running', 'events': events}, indent=2))

        train_model(SimpleNamespace(**config), model, ChatDataset(train_rows, tokenizer, mask_prompt=True),
                    ChatDataset(valid_rows, tokenizer, mask_prompt=True), Callback())
        result = {'status': 'completed', 'mode': 'train', 'config': config,
                  'train_count': len(train_rows), 'valid_count': len(valid_rows), 'events': events,
                  'selection_policy': 'Training validation occurs before optimizer step. Rescore saved checkpoints in fresh processes before selection; never choose from test.'}
    else:
        rows = load_rows(data, args.split)
        model, tokenizer = load(str(ROOT / 'models/typhoon-4bit'), adapter_path=str(ROOT / args.adapter) if args.adapter else None)
        model.eval()
        # Loss on ALL records, individually by task as well as token weighted.
        by_task = {}
        for task in sorted({row['provenance']['task'] for row in rows}):
            subset = [row for row in rows if row['provenance']['task'] == task]
            by_task[task] = {'count': len(subset), 'assistant_loss': float(evaluate(model, CacheDataset(ChatDataset(subset, tokenizer, mask_prompt=True)), batch_size=1, num_batches=-1, max_seq_length=1536))}
        # Balanced deterministic subset locked by ID, never chosen by outputs.
        rng = random.Random(724)
        candidates = []
        for task in sorted(by_task):
            subset = sorted([row for row in rows if row['provenance']['task'] == task], key=lambda r: r['provenance']['id'])
            rng.shuffle(subset)
            quota = max(1, args.generation_limit // len(by_task))
            if args.all_commands and task != 'health_qa':
                candidates.extend(subset)
            elif task == 'extract':
                # Cover every domain including explicit date examples.
                for kind in sorted({r['provenance']['kind'] for r in subset}):
                    candidates.append(next(r for r in subset if r['provenance']['kind'] == kind))
            else:
                candidates.extend(subset[:quota])
        generations = []
        for index, row in enumerate(candidates):
            messages = row['messages'][:-1]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            start = time.monotonic(); parts = []; finish = None; generated = 0
            for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=384, sampler=make_sampler(temp=0)):
                parts.append(response.text); finish = response.finish_reason; generated = response.generation_tokens
            answer = ''.join(parts); reference = row['messages'][-1]['content']; task = row['provenance']['task']
            exact = None; valid_json = None
            if task != 'health_qa':
                try:
                    actual = json.loads(answer); expected = json.loads(reference)
                    valid_json = True; exact = actual == expected
                except (ValueError, TypeError): valid_json = False; exact = False
            generations.append({'id': row['provenance']['id'], 'task': task, 'origin': row['provenance']['origin'],
                                'kind': row['provenance'].get('kind'), 'messages': messages, 'reference': reference,
                                'answer': answer, 'valid_json': valid_json, 'exact_match': exact,
                                'finish_reason': finish, 'output_tokens': generated,
                                'seconds': time.monotonic() - start, 'human_review': 'pending'})
            print(f'{index+1}/{len(candidates)} {task} exact={exact} finish={finish}', flush=True)
            output.write_text(json.dumps({'status': 'running', 'generations': generations}, ensure_ascii=False, indent=2))
        metrics = {}
        for task in by_task:
            selected = [g for g in generations if g['task'] == task]
            metrics[task] = {**by_task[task], 'generated_count': len(selected),
                             'json_valid': sum(g['valid_json'] is True for g in selected),
                             'exact': sum(g['exact_match'] is True for g in selected)}
        result = {'status': 'completed', 'mode': 'evaluate', 'split': args.split,
                  'adapter': args.adapter, 'fresh_process_pid': os.getpid(),
                  'metrics': metrics, 'generations': generations, 'temperature': 0,
                  'generation_limit_requested': args.generation_limit,
                  'all_commands': args.all_commands,
                  'evaluation_kind': 'Synthetic command generalization + original English source QA; not clinical or real-user accuracy'}
    result.update(elapsed_seconds=time.monotonic()-started, peak_memory_gb=mx.get_peak_memory()/1e9,
                  finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ('events', 'generations', 'config')}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__': main()
