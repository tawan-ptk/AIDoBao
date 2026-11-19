"""Download only public-domain MedlinePlus health-topic summaries for this run.

No encyclopedia, drug monographs, linked pages, images or user records.
Original questions are headings within the summary; answers are adjacent blocks.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    'diabetes': 'train', 'diabetestype2': 'train', 'diabeticdiet': 'train',
    'carbohydrates': 'train', 'nutrition': 'train', 'cholesterol': 'train',
    'exerciseandphysicalfitness': 'train', 'healthyliving': 'train',
    'metabolicsyndrome': 'train', 'foodallergy': 'valid',
    'dehydration': 'valid', 'mentalhealth': 'test', 'sleepapnea': 'test',
}
POLICY = 'https://medlineplus.gov/about/using/usingcontent/'


def summary_pairs(html):
    soup = BeautifulSoup(html, 'html.parser')
    summary = soup.select_one('#topic-summary')
    if summary is None:
        raise ValueError('Expected public-domain health topic summary missing')
    pairs = []
    for heading in summary.find_all('h3'):
        question = heading.get_text(' ', strip=True)
        if not question.endswith('?'):
            continue
        blocks = []
        for el in heading.next_siblings:
            if getattr(el, 'name', None) in ('h2', 'h3'):
                break
            if getattr(el, 'name', None) in ('p', 'ul', 'ol'):
                # Text from the source, whitespace normalized; no paraphrasing.
                value = el.get_text(' ', strip=True)
                if value:
                    blocks.append(value)
        if blocks:
            pairs.append({'question': question, 'answer': '\n\n'.join(blocks)})
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    raw = ROOT / 'data/raw/finetune-v1'
    raw.mkdir(parents=True, exist_ok=True)
    manifest_file = raw / 'downloads.json'
    existing = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    all_pairs = []
    for slug in [*PAGES, 'usingcontent-policy']:
        url = POLICY if slug == 'usingcontent-policy' else f'https://medlineplus.gov/{slug}.html'
        path = raw / f'{slug}.html'
        if args.refresh or not path.exists():
            with urlopen(Request(url, headers={'User-Agent': 'HealthAppResearch/1.0'}), timeout=45) as response:
                final_url = response.url
                if urlparse(final_url).hostname != 'medlineplus.gov':
                    raise ValueError('Unexpected source redirect')
                content = response.read()
            path.write_bytes(content)
            existing[slug] = {'requested_url': url, 'url': final_url,
                              'accessed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            manifest_file.write_text(json.dumps(existing, indent=2))
            time.sleep(0.2)
        info = existing[slug]
        info.update(file=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if slug == 'usingcontent-policy':
            continue
        pairs = summary_pairs(path.read_text())
        for index, pair in enumerate(pairs):
            all_pairs.append({**pair, 'id': f'medlineplus-current/{slug}/{index}',
                              'group': f'medlineplus-current/{slug}', 'split': PAGES[slug],
                              'source': dict(info), 'source_location': f'#topic-summary h3[{index + 1}]',
                              'origin': 'original_source_qa', 'language': 'en',
                              'license': 'US federal public-domain health-topic summary',
                              'attribution': 'Source: MedlinePlus, National Library of Medicine.'})
        print(slug, len(pairs), flush=True)
    manifest_file.write_text(json.dumps(existing, indent=2))
    (ROOT / 'data/prepared/finetune-source-qa.jsonl').write_text(
        '\n'.join(json.dumps(row, ensure_ascii=False) for row in all_pairs) + '\n')


if __name__ == '__main__':
    main()
