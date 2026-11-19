"""Explicit-allowlist private runtime export; never bundles owner data/secrets."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES=('app','services','demo','models/typhoon-4bit','adapters/finetune-v2-selected')
MODEL_FILES={'config.json','tokenizer.json','tokenizer_config.json','model.safetensors','model.safetensors.index.json','chat_template.jinja','README.md'}
FILES=('models/runtime-adapter.json','data/knowledge/chunks.jsonl','data/knowledge/chat_guidance.jsonl',
       'data/rule_registry.json','data/catalog/activities.json','data/source_manifest.json',
       'scripts/run_demo.py','scripts/run_api.py','scripts/run_gateway.py','scripts/inference.py','scripts/export_runtime.py','requirements.runtime.txt',
       'docs/ai-integration.md','docs/website-handoff-prompt.md','docs/openapi.json','docs/vercel-gateway.md','integration/ruamwan-client.mjs','integration/gateway.json',
       'licenses/Apache-2.0.txt','reports/finetune-v2-results.md','reports/finetune-v3-results.md')

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def export(destination,root=ROOT):
    destination=Path(destination).resolve();root=Path(root).resolve()
    if destination.exists():raise ValueError('Destination exists; choose a new directory to preserve previous exports')
    paths=[root/p for p in FILES]
    for directory in DIRECTORIES:
        for p in (root/directory).rglob('*'):
            if not p.is_file() or any(part.startswith('.') or part=='__pycache__' for part in p.relative_to(root).parts):continue
            if directory in ('app','services') and p.suffix=='.py':paths.append(p)
            elif directory=='demo' and p.suffix in ('.html','.css','.js'):paths.append(p)
            elif directory=='models/typhoon-4bit' and p.name in MODEL_FILES:paths.append(p)
            elif directory=='adapters/finetune-v2-selected' and p.name in ('adapter_config.json','adapters.safetensors'):paths.append(p)
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Symlink/outside-root file rejected')
        if not path.is_file():raise ValueError('Missing runtime file: '+str(path.relative_to(root)))
    destination.mkdir(parents=True)
    manifest=[]
    for source in sorted(set(paths)):
        relative=source.relative_to(root);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);manifest.append({'path':str(relative),'bytes':target.stat().st_size,'sha256':sha(target)})
    # Retain upstream attribution without copying the original 8GB weights.
    card=root/'models/typhoon-original/README.md'
    if card.exists():
        if card.is_symlink() or not card.resolve().is_relative_to(root):raise ValueError('Symlink/outside-root model card rejected')
        target=destination/'models/typhoon-4bit/UPSTREAM_MODEL_CARD.md';shutil.copy2(card,target)
        manifest.append({'path':str(target.relative_to(destination)),'bytes':target.stat().st_size,'sha256':sha(target)})
    (destination/'manifest.json').write_text(json.dumps({'format':1,'platform':'macOS Apple Silicon MLX',
        'enabled_adapter_tasks':['intent','menu'],'owner_data_included':False,'clinical_validation':False,'files':manifest},indent=2))
    return verify(destination)

def verify(destination):
    destination=Path(destination).resolve();manifest=json.loads((destination/'manifest.json').read_text())
    for entry in manifest['files']:
        p=destination/entry['path']
        if not p.resolve().is_relative_to(destination) or p.is_symlink() or not p.is_file() or sha(p)!=entry['sha256']:raise ValueError('Integrity failed: '+entry['path'])
    expected={e['path'] for e in manifest['files']}|{'manifest.json'}
    actual={str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual!=expected:raise ValueError('Unexpected or missing files')
    return {'verified':True,'files':len(manifest['files']),'bytes':sum(e['bytes'] for e in manifest['files']),'path':str(destination)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'dist/ruamwan-ai-macos-0.10.0'));p.add_argument('--verify');args=p.parse_args()
    print(json.dumps(verify(args.verify) if args.verify else export(args.output),ensure_ascii=False))
