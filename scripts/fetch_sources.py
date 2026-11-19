"""Read-only source acquisition. No website crawling, no private data upload."""
import datetime, hashlib, json, pathlib, subprocess, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
RAW.mkdir(parents=True, exist_ok=True)

def fetch(url, name):
    p = RAW / name
    req = urllib.request.Request(url, headers={'User-Agent': 'RoutineResearchPrototype/0.1'})
    with urllib.request.urlopen(req, timeout=90) as r:
        p.write_bytes(r.read())
    return {'url': url, 'file': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size, 'accessed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}

def main():
    inventory = []
    urls = {
        'mlx-LORA.md': 'https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/LORA.md',
        'mlx-README.md': 'https://raw.githubusercontent.com/ml-explore/mlx-lm/main/README.md',
        'model-api.json': 'https://huggingface.co/api/models/typhoon-ai/typhoon2.5-qwen3-4b',
        'medquad-api.json': 'https://api.github.com/repos/abachaa/MedQuAD/commits/master',
        'hai-api.json': 'https://api.github.com/repos/uccollab/hai-coaching/commits/main',
        'figshare-data.json': 'https://api.figshare.com/v2/articles/8246780',
        'figshare-questionnaire.json': 'https://api.figshare.com/v2/articles/8298689',
        'zenodo.json': 'https://zenodo.org/api/records/6325536',
        'f1000.html': 'https://f1000research.com/articles/8-1030/v3',
        'thaifcd.html': 'https://inmu.mahidol.ac.th/thaifcd/home',
        'nhes.html': 'https://opendata.hsri.or.th/dataset/nhes7-summary',
        'niddk.html': 'https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes',
        'niddk-copyright.html': 'https://www.niddk.nih.gov/about-niddk/research-areas/digestive-diseases/weight-control-information-network/copyright',
        'who-activity.html': 'https://www.who.int/news-room/fact-sheets/detail/physical-activity',
        'cdc-sleep.html': 'https://www.cdc.gov/sleep/about/index.html',
        'dmthai.html': 'https://dmthai.org/new/index.php/activities-and-news/news-pr/naewthang-wech-ptibati-sahrab-rokh-bea-hwan-2566-chbab-prabprung-kph-67',
    }
    for name, url in urls.items():
        try:
            record = fetch(url, name)
            print(name, record['bytes'], flush=True)
        except Exception as e:
            record = {'url': url, 'file': name, 'error': str(e)}
            print(name, str(e), flush=True)
        inventory.append(record)
    for repo, branch, label in [('abachaa/MedQuAD','master','medquad'), ('uccollab/hai-coaching','main','hai')]:
        api = RAW / (label + '-api.json')
        if not api.exists(): continue
        rev = json.loads(api.read_text())['sha']
        for fname in (['README.md','LICENSE.txt'] if label == 'medquad' else ['README.md','LICENSE']):
            try: inventory.append(fetch(f'https://raw.githubusercontent.com/{repo}/{rev}/{fname}', label + '-' + fname))
            except Exception as e: print(e)
        if label == 'medquad':
            inventory.append(fetch(f'https://api.github.com/repos/{repo}/tarball/{rev}', 'medquad.tar.gz'))
    for label in ['figshare-data','figshare-questionnaire','zenodo']:
        p = RAW / (label + '.json')
        if not p.exists(): continue
        info = json.loads(p.read_text())
        for f in info.get('files', []):
            name = f.get('name', f.get('key'))
            url = f.get('download_url') or f.get('links',{}).get('self')
            if url and f.get('size', 0) < 50_000_000:
                try: inventory.append(fetch(url, label + '-' + pathlib.Path(name).name))
                except Exception as e: print(name, e)
    (ROOT/'reports/downloads.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
