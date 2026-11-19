import datetime, hashlib, importlib.metadata, json, os, pathlib, platform, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(ROOT/'.cache/huggingface')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_XET'] = '1'

def main():
    from huggingface_hub import snapshot_download
    import mlx.core as mx
    from mlx_lm.convert import convert
    info = json.loads((ROOT/'data/raw/model-api.json').read_text())
    revision = info['sha']
    started = time.monotonic()
    report = {'model_id': info['id'], 'revision': revision, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'platform': platform.platform(), 'python': platform.python_version(), 'versions': {p: importlib.metadata.version(p) for p in ['mlx','mlx-lm','transformers']}, 'device': mx.device_info(), 'memory_bytes': int(subprocess.check_output(['sysctl','-n','hw.memsize'])), 'license': info.get('cardData',{}).get('license')}
    raw = snapshot_download(info['id'], revision=revision, local_dir=ROOT/'models/typhoon-original', allow_patterns=['*.json','*.safetensors','*.model','*.txt','*.jinja','README.md','LICENSE*'], max_workers=2)
    report['download_seconds'] = time.monotonic()-started
    t = time.monotonic()
    if not (ROOT/'models/typhoon-4bit').exists():
        convert(raw, str(ROOT/'models/typhoon-4bit'), quantize=True, q_bits=4, q_group_size=64, q_mode='affine')
    report['conversion_seconds'] = time.monotonic()-t
    report['peak_memory_gb'] = mx.get_peak_memory()/1e9
    report['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'models/typhoon-4bit').iterdir() if p.is_file()}
    (ROOT/'reports/model-setup.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k:v for k,v in report.items() if k!='files'}, indent=2, default=str))

if __name__ == '__main__': main()
