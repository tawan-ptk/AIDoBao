"""Copy ONLY the cloud record service into dist/cloud-core for `vercel --prod`.

Never copies models, adapters, .env, .secrets, SQLite files or any health data.
    .venv/bin/python scripts/stage_cloud.py && cd dist/cloud-core && vercel --prod
"""
import pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/cloud-core'
KEEP = ['api/index.py', 'requirements.txt', 'vercel.json',
        'data/rule_registry.json', 'data/source_manifest.json']
TREES = ['app', 'services', 'data/knowledge', 'data/catalog']
link = OUT / '.vercel'
saved = None
if link.exists():  # keep the Vercel project link between stagings
    saved = ROOT / 'dist/.cloud-core-vercel'
    shutil.rmtree(saved, ignore_errors=True)
    shutil.move(str(link), str(saved))
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
for rel in KEEP:
    (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / rel, OUT / rel)
for rel in TREES:
    shutil.copytree(ROOT / rel, OUT / rel,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.sqlite*', '.env*'))
if saved:
    shutil.move(str(saved), str(link))
(OUT / '.vercelignore').write_text('.env*\n**/__pycache__\n')
files = [p for p in OUT.rglob('*') if p.is_file() and '.vercel' not in p.parts]
bad = [p for p in files if p.suffix in ('.sqlite', '.sqlite3', '.safetensors') or p.name.startswith('.env') or 'secrets' in p.parts]
assert not bad, bad
print(f'staged {len(files)} files, {sum(p.stat().st_size for p in files)//1024} KB -> {OUT}')
