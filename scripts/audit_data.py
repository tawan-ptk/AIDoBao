"""Inspect originals, preserve missing codes and provenance; never fabricate labels."""
import collections, csv, hashlib, json, pathlib, tarfile, xml.etree.ElementTree as ET, zipfile
import pandas as pd
import pyreadstat
from bs4 import BeautifulSoup
ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw'
OLD = pathlib.Path('/Users/tawan/Documents/Codex/2026-10-10/l')

def save(name, obj):
    (ROOT/'reports'/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str))

def main():
    f = OLD/'work/dataset-research/hai-coaching.xlsx'
    df = pd.read_excel(f, sheet_name='DATASET')
    expert = df[df.suggestion_from_expert.notna()]
    save('hai-audit.json', {'sha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'rows':len(df), 'columns':list(df.columns), 'expert_rows':len(expert), 'unique_struggles':expert.struggle_original.nunique(), 'status':'excluded', 'reason':'Repository LGPL-2.1 notice does not explicitly clarify dataset/adapter scope; dataset-specific rights pending. No candidates used.'})
    df, meta = pyreadstat.read_sav(RAW/'figshare-data-Diabete-dataset.sav', user_missing=True)
    save('thai-behavior-audit.json', {'rows':len(df), 'columns':list(df.columns), 'labels':meta.column_names_to_labels, 'value_labels':meta.variable_value_labels, 'missing_ranges':meta.missing_ranges, 'missing_counts':df.isna().sum().to_dict(), 'unique_counts':df.nunique().to_dict(), 'ranges':{c:{'min':str(df[c].min()), 'max':str(df[c].max())} for c in df.select_dtypes('number')}, 'use':'schema/import audit only; not training targets'})
    for doc in RAW.glob('*.docx'):
        with zipfile.ZipFile(doc) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
        (ROOT/'reports'/(doc.stem+'.txt')).write_text(text)
    zen = next(RAW.glob('zenodo-*.xlsx'))
    book = pd.ExcelFile(zen)
    save('zenodo-audit.json', {sheet:{'rows':len(d), 'columns':list(d.columns), 'nonmissing':d.notna().sum().to_dict(), 'first_rows':d.head(3).fillna('').to_dict('records')} for sheet in book.sheet_names for d in [pd.read_excel(book,sheet_name=sheet)]})
    for label in ['niddk','who-activity','thaifcd','nhes','f1000','dmthai']:
        p=RAW/(label+'.html')
        if not p.exists():continue
        soup=BeautifulSoup(p.read_text(), 'html.parser')
        for el in soup(['script','style','nav','footer','header']):el.decompose()
        (ROOT/'reports'/(label+'.txt')).write_text(soup.get_text('\n', strip=True))
        save(label+'-links.json',[{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in soup.find_all('a',href=True)])
    people=pd.read_csv(OLD/'outputs/nhanes-adult-health-diet-merged.csv')
    foods=pd.read_csv(OLD/'outputs/nhanes-food-records-linked.csv')
    save('nhanes-recheck.json',{'people_rows':len(people),'food_rows':len(foods),'people_columns':list(people.columns),'food_columns':list(foods.columns),'unique_people':people.SEQN.nunique(),'food_people':foods.SEQN.nunique(),'duplicate_person_ids':int(people.SEQN.duplicated().sum()),'orphan_food_rows':int((~foods.SEQN.isin(people.SEQN)).sum()), 'people_without_food':int((~people.SEQN.isin(foods.SEQN)).sum()),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OLD/'outputs').glob('*.csv')},'use':'structure validation only, no survey population inference or timeline synthesis'})
    candidates=[]; counts=collections.Counter()
    rev=json.loads((RAW/'medquad-api.json').read_text())['sha']
    with tarfile.open(RAW/'medquad.tar.gz') as tf:
        for member in tf.getmembers():
            if member.name.lower().endswith('readme.md') or member.name.endswith('readme.txt'):
                (RAW/'medquad-readme.txt').write_bytes(tf.extractfile(member).read())
            if not member.name.endswith('.xml'):continue
            folder=member.name.split('/')[1]
            if folder.startswith(('10_','11_','12_')):
                counts['excluded_removed_answer_documents']+=1;continue
            b=tf.extractfile(member).read()
            root=ET.fromstring(b)
            focus=root.findtext('Focus','')
            counts['documents_inspected']+=1
            # Selection is based on document topic, never answer-keyword matching.
            if not any(w in focus.lower() for w in ['diabetes','physical activity','sleep','exercise','healthy eating']):continue
            for qa in root.findall('.//QAPair'):
                q=qa.find('Question');a=qa.findtext('Answer','')
                if not a.strip():counts['empty_answers']+=1;continue
                candidates.append({'id':f'{folder}/{root.get("id")}/{qa.get("pid")}', 'document_id':folder+'/'+str(root.get('id')), 'question_id':q.get('qid'), 'question_type':q.get('qtype'), 'focus':focus,'question':q.text,'answer':a,'source_url':root.get('url'),'file':member.name,'file_sha256':hashlib.sha256(b).hexdigest(),'revision':rev,'status':'candidate'})
    (ROOT/'data/prepared/medquad-candidates.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in candidates)+'\n')
    save('medquad-audit.json',{'counts':dict(counts),'candidate_pairs':len(candidates),'topics':dict(collections.Counter(x['focus'] for x in candidates)), 'training_used':0})
    print('Audited HAI, SAV, DOCX, Zenodo, NHANES and MedQuAD:', len(candidates), 'candidate QA pairs')

if __name__=='__main__':main()
