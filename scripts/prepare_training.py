"""A deliberately small, provenance-preserving MedQuAD engineering experiment.
No paraphrases, synthetic responses, user records, or fixtures enter this path.
"""
import difflib, hashlib, json, pathlib, random, re
from transformers import AutoTokenizer
ROOT=pathlib.Path(__file__).resolve().parents[1]
SELECT={
 '4_MPlus_Health_Topics_QA/0000266/1':('train','https://medlineplus.gov/diabetes.html','Summary: definitions, symptoms and management; no prescribed targets'),
 '4_MPlus_Health_Topics_QA/0000273/1':('train','https://medlineplus.gov/diabetestype2.html','Summary: type 2 definition, symptoms, lifestyle and prescribed medicines'),
 '7_SeniorHealth_QA/0000015/10':('train','https://medlineplus.gov/diabetes.html','What is diabetes?: glucose and insulin definition'),
 '7_SeniorHealth_QA/0000015/15':('train','https://medlineplus.gov/diabetes.html','What are the symptoms?: symptoms and possible absence'),
 '7_SeniorHealth_QA/0000015/16':('train','https://medlineplus.gov/diabetes.html','What causes diabetes?: type 1 immune process and type 2 insulin resistance'),
 '7_SeniorHealth_QA/0000015/17':('train','https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes','Healthy living introduction and smoking: complication prevention, no treatment dose'),
 '4_MPlus_Health_Topics_QA/0000339/1':('valid','https://medlineplus.gov/exerciseandphysicalfitness.html','Summary: benefits, matching ability; ten minutes is permitted, not treated as a minimum'),
 '4_MPlus_Health_Topics_QA/0000824/1':('test','https://medlineplus.gov/sleepdisorders.html','Summary: educational sleep disorder categories only; not diagnosis'),
}
def main():
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'models/typhoon-original',local_files_only=True,trust_remote_code=False)
    rows=[json.loads(s) for s in (ROOT/'data/prepared/medquad-candidates.jsonl').read_text().splitlines()]
    splits={k:[] for k in ['train','valid','test']};audit=[];excluded=[]
    for r in rows:
        if r['id'] not in SELECT:
            excluded.append({'id':r['id'],'reason':'not positively audited: out-of-scope topic, malformed QA alignment, outdated statistics/contacts/targets, or current corroboration not established'});continue
        split,url,location=SELECT[r['id']]
        messages=[{'role':'user','content':r['question']},{'role':'assistant','content':r['answer']}]
        tokens=tokenizer.apply_chat_template(messages,tokenize=True,return_dict=False)
        if len(tokens)>1024:
            excluded.append({'id':r['id'],'reason':'over_context_not_truncated','tokens':len(tokens)});continue
        provenance={k:r[k] for k in ['id','document_id','question_id','file','file_sha256','source_url','revision']}
        provenance|={'license':'CC-BY-4.0','creators':['Asma Ben Abacha','Dina Demner-Fushman'],'current_corroboration_url':url,'current_corroboration_location':location,'review_kind':'source comparison by coding assistant, not clinician review','origin':'original_source_answer','answer_sha256':hashlib.sha256(r['answer'].encode()).hexdigest(),'tokens':len(tokens)}
        splits[split].append({'messages':messages,'provenance':provenance});audit.append(provenance|{'split':split})
    # Same source documents and very similar answer passages must not cross splits.
    pairs=[]
    for left in splits:
        for right in splits:
            if left>=right:continue
            for a in splits[left]:
                for b in splits[right]:
                    assert a['provenance']['document_id']!=b['provenance']['document_id']
                    ta=re.sub(r'\s+',' ',a['messages'][-1]['content'].lower())
                    tb=re.sub(r'\s+',' ',b['messages'][-1]['content'].lower())
                    ratio=difflib.SequenceMatcher(None,ta,tb,autojunk=False).ratio()
                    wa=set(re.findall(r'\w+',ta));wb=set(re.findall(r'\w+',tb));jacc=len(wa&wb)/len(wa|wb)
                    pairs.append({'a':a['provenance']['id'],'b':b['provenance']['id'],'sequence_ratio':ratio,'word_jaccard':jacc})
                    assert ratio<0.8 and jacc<0.75,'near-duplicate crosses split'
    out=ROOT/'data/prepared/training';out.mkdir(exist_ok=True)
    for k,v in splits.items():
        assert v,f'empty {k}'
        random.Random(42).shuffle(v)
        (out/(k+'.jsonl')).write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in v)+'\n')
    report={'seed':42,'split_method':'document/topic grouped, explicitly fixed before pilot; diabetes-related documents grouped together to prevent overlap','counts':{k:len(v) for k,v in splits.items()},'records':audit,'exclusions':excluded,'cross_split_checks':pairs,'context':1024,'truncated_answers':0,'limitations':['Engineering pilot only: six training pairs, one validation topic and one held-out test topic cannot establish general health accuracy.','No Thai human-reference evaluation set.','No plan/extraction/replanning paired labels.','Pretraining overlap unknown.','Source audit is not clinical approval.']}
    (ROOT/'reports/training-data-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (ROOT/'reports/chat-template.txt').write_text(tokenizer.chat_template)
    print(json.dumps(report['counts']), 'max tokens',max(x['tokens'] for x in audit))
if __name__=='__main__':main()
