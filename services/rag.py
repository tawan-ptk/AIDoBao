"""Small lexical retriever. Return exact sections; no fabricated citations."""
import json, math, pathlib, re
ALIASES={'อาหาร':'food meal diet eat drink','กิน':'eat meal','ออกกำลัง':'physical activity exercise','เดิน':'walking activity','นอน':'sleep','ยา':'medicine insulin','เครียด':'mental stress','น้ำตาล':'glucose','บุหรี่':'smoking quit','น้ำหนัก':'weight','อ้วน':'obesity overweight','อวบ':'obesity overweight','ผอม':'weight loss','น้ำหนักลด':'weight loss','หนักเท่า':'weight','เวลา':'time schedule','หายจากเบาหวาน':'remission','เบาหวานหาย':'remission','หายขาด':'remission','ภาวะสงบ':'remission','รักษาเบาหวาน':'remission','หายจากโรคเบาหวาน':'remission'}
def tokens(s):
    lower=s.lower()
    if 'เบาหวาน' in lower and re.search(r'หาย|สงบ|remission',lower):lower+=' remission'
    for th,en in ALIASES.items():
        if th in lower:lower+=' '+en
    return set(re.findall(r'[a-z]{3,}|[\u0e00-\u0e7f]+',lower))-{'the','and','for','with','what','how','can','have','your','you','diabetes'}

class Retriever:
    def __init__(self,path='data/knowledge/chunks.jsonl'):
        p=pathlib.Path(path);self.chunks=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
        supplement=p.parent/'chat_guidance.jsonl'
        if supplement.exists():self.chunks.extend(json.loads(x) for x in supplement.read_text().splitlines() if x.strip())
    def search(self,query,k=3):
        q=tokens(query)
        scores=[]
        for c in self.chunks:
            ct=tokens(c['text']+' '+c['heading']);heading=tokens(c['heading']);matched=q&ct
            # A passing mention in an unrelated section is not enough evidence.
            if not matched or not q&heading:continue
            score=sum(math.log(1+len(self.chunks)/(1+sum(t in tokens(x['text']) for x in self.chunks))) for t in matched)+2*len(q&heading)
            if c.get('content_type')=='editorial_summary':score+=10
            scores.append((score,c))
        return [c|{'score':s} for s,c in sorted(scores,key=lambda x:(-x[0],x[1]['chunk_id']))[:k]]
    def answer(self,query):
        found=self.search(query)
        return {'status':'evidence_found' if found else 'unknown','mode':'extractive','answer':'พบหลักฐานที่เกี่ยวข้อง โปรดอ่านเงื่อนไขและแหล่งที่มา รายการที่ระบุ editorial_summary เป็นสรุปสาระโดยผู้พัฒนา ไม่ใช่ข้อความอ้างตรง' if found else 'ยังไม่พบหลักฐานเพียงพอในฐานข้อมูลนี้ กรุณาระบุหัวข้อเพิ่มเติม','citations':found,'clinical_review':'not_reviewed','language_note':'มีหลักฐานภาษาอังกฤษและสรุปภาษาไทยโดยผู้พัฒนา ยังไม่ผ่านการประเมินคำตอบทางคลินิก'}
