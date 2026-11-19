"""Pick a few worked examples per task for API prompting (replaces fine-tuning).

    .venv/bin/python scripts/build_fewshot.py

Source: data/prepared/finetune-v3/train.jsonl. Every row there is an authorized
synthetic command example (see audit.json). No real user text is used.
Writes data/knowledge/fewshot.json, which ships with the cloud service.
"""
import json
import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.llm import example_key  # noqa: E402

PER_KEY = {'route': 6}  # extraction kinds get 4 each


def score(example):
    """Prefer rows that fill several fields, then keep one with nothing to fill."""
    try:
        out = json.loads(example['assistant'])
    except ValueError:
        return -1
    data = out.get('data') if isinstance(out, dict) else None
    return sum(v is not None for v in data.values()) if isinstance(data, dict) else 0


def main():
    pools = {}
    for line in (ROOT / 'data/prepared/finetune-v3/train.jsonl').open():
        messages = json.loads(line)['messages']
        key = example_key(messages)
        if not key or len(messages) != 3:
            continue
        pools.setdefault(key, []).append({'user': messages[1]['content'], 'assistant': messages[2]['content']})
    chosen = {}
    for key, rows in sorted(pools.items()):
        limit = PER_KEY.get(key, 4)
        if key == 'route':
            # Balance in-scope and out-of-scope labels.
            health = [r for r in rows if '"health"' in r['assistant']]
            other = [r for r in rows if '"health"' not in r['assistant']]
            picks = health[: limit // 2] + other[: limit - limit // 2]
        else:
            ranked = sorted(rows, key=score, reverse=True)
            picks = ranked[: limit - 1] + [min(rows, key=score)]
            # Fill from the rest of the pool when two picks only differ by a date.
            picks += ranked
        seen, unique = set(), []
        for row in picks:
            shape = re.sub(r'[\d:+\-T.]+', '#', row['user'])
            if shape not in seen:
                seen.add(shape)
                unique.append(row)
        chosen[key] = unique[:limit]
    out = ROOT / 'data/knowledge/fewshot.json'
    out.write_text(json.dumps({'source': 'finetune-v3 train (synthetic)', 'examples': chosen},
                              ensure_ascii=False, indent=1) + '\n')
    print({k: len(v) for k, v in chosen.items()}, '->', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
