"""Bounded backtracking across confirmed choices. Does not prescribe treatment."""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from services.schemas import Routine, Profile, Constraint, DOMAINS

def overlap(a,b):return a['start']<b['end'] and b['start']<a['end']

def build_plan(profile, routines, constraints, start_date, input_revision, max_nodes=50000, general_time_only=False):
    p=Profile.model_validate(profile);start=date.fromisoformat(start_date);stop=start+timedelta(days=7);zone=ZoneInfo(p.timezone)
    base={'start_date':start_date,'end_date':str(stop),'input_revision':input_revision,'items':[],'checks':[],'missing':[],'clinical_status':'not_reviewed','proposal_status':'program_generated','user_status':'unconfirmed','reviewer':None}
    base['general_time_only']=general_time_only
    if not general_time_only and (p.pregnant or p.complex_care or not p.reported_type2 or p.age is None or p.age<18):
        return base|{'status':'unknown','missing':['โปรไฟล์อยู่นอกขอบเขตการจัดแผนต้นแบบ']}
    blocks=[]
    for r in constraints:
        c=Constraint.model_validate(r['data']);blocks.append({'id':r['id'],'label':c.label,'start':c.start,'end':c.end})
    block_conflicts=[(a['id'],b['id']) for i,a in enumerate(blocks) for b in blocks[i+1:] if overlap(a,b)]
    if block_conflicts:return base|{'status':'infeasible','conflicts':block_conflicts,'missing':['ช่วงเวลาที่ล็อกไว้ขัดกัน กรุณาตรวจงาน การเดินทาง และนัดหมาย']}
    jobs=[];domains=set()
    for r in routines:
        t=Routine.model_validate(r['data']);domains.add(t.domain)
        if t.catalog_id and t.catalog_id in p.prohibited_catalog_ids:
            return base|{'status':'infeasible','missing':['รายการขัดกับข้อห้ามที่ยืนยัน: '+r['id']]}
        if t.domain=='activity' and p.mobility_limits:
            base['missing'].append(f'{r["id"]}: มีข้อจำกัดการเคลื่อนไหวที่ยังแปลงเป็นกฎตรวจไม่ได้ ต้องให้ผู้ดูแลตรวจ');continue
        if not general_time_only and t.goal not in p.goals:
            base['missing'].append(f'{r["id"]}: เป้าหมายยังไม่อยู่ในโปรไฟล์ที่ยืนยัน');continue
        if t.meal_relation=='unknown' or (t.meal_relation!='none' and (not t.related_routine_id or t.relation_minutes is None)):
            base['missing'].append(f'{r["id"]}: เงื่อนไขยากับอาหารไม่ครบ');continue
        for day in t.dates:
            if not start<=day<stop:continue
            lo=datetime.combine(day,t.earliest,zone);hi=datetime.combine(day,t.latest,zone)
            if hi<lo:hi+=timedelta(days=1)
            choices=[lo] if t.fixed else [lo+timedelta(minutes=m) for m in range(0,int((hi-lo).total_seconds()/60)+1,15)]
            jobs.append({'id':f'{r["id"]}:{day}','routine_id':r['id'],'domain':t.domain,'label':t.label,'goal':t.goal,'duration_minutes':t.duration_minutes,'input_ids':[r['id']],'source_ids':['user_record:'+r['id']],'source_description':r['source'],'rule_ids':['schedule.no_overlap.v1','schedule.locked_time.v1'],'data':t,'choices':choices})
    base['readiness']={d:('พร้อมจัดเวลารายการที่ยืนยัน' if d in domains else 'ยังไม่มีรายการที่ยืนยัน') for d in DOMAINS}
    if base['missing'] or not jobs:return base|{'status':'unknown','missing':base['missing'] or ['ยังไม่มีกิจกรรมในช่วง 7 วันนี้']}
    jobs.sort(key=lambda j:(len(j['choices']),-j['duration_minutes'],j['id']))
    nodes=0;conflicts=set()
    def relations(items,final=False):
        for x in items:
            d=x['data']
            if d.meal_relation=='none':continue
            others=[y for y in items if y['routine_id']==d.related_routine_id and y['start'].date()==x['start'].date()]
            if not others:
                if final:return False
                continue
            m=others[0]
            if m['domain']!='meal':return False
            delta=timedelta(minutes=d.relation_minutes)
            if d.meal_relation=='before' and x['end']+delta!=m['start']:return False
            if d.meal_relation=='after' and m['end']+delta!=x['start']:return False
            # With-meal simultaneous occupancy needs a composite activity; no silent overlap exemption.
            if d.meal_relation=='with':return False
        return True
    def search(i,chosen):
        nonlocal nodes
        nodes+=1
        if nodes>max_nodes:return None
        if i==len(jobs):return chosen if relations(chosen,True) else None
        j=jobs[i]
        for s in j['choices']:
            v=j|{'start':s,'end':s+timedelta(minutes=j['duration_minutes'])}
            collisions=[o for o in blocks+chosen if overlap(v,o)]
            if collisions:
                conflicts.update((j['id'],o['id']) for o in collisions);continue
            if relations(chosen+[v]):
                found=search(i+1,chosen+[v])
                if found is not None:return found
        return None
    result=search(0,[])
    if result is None:return base|{'status':'unknown' if nodes>max_nodes else 'infeasible','search_nodes':nodes,'conflicts':sorted(conflicts),'missing':['ค้นหาไม่ครบภายในขอบเขต' if nodes>max_nodes else 'เวลา/เงื่อนไขไม่ลงตัว ต้องให้ผู้ใช้แก้ข้อจำกัดหรือรายการที่ยืนยัน'],'alternatives':['ขยายช่วงเวลาที่เลือกได้','เลือกวันอื่นสำหรับกิจกรรมที่ย้ายได้','ตรวจคำสั่งยากับผู้ดูแล; ระบบไม่ย้ายยาเอง'],'resolution_minutes':15}
    base['items']=[{k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in x.items() if k not in ('choices','data')}|{'check':'pass','clinical_check':'unknown','confirmation':'unconfirmed'} for x in sorted(result,key=lambda j:j['start'])]
    return base|{'status':'pass','search_nodes':nodes,'resolution_minutes':15,'checks':[{'rule_id':'schedule.no_overlap.v1','status':'pass'},{'rule_id':'health.suitability.v1','status':'unknown'}]}

def diff_plans(before,after,reason):
    old={x['id']:x for x in before['items']};new={x['id']:x for x in after['items']}
    return {'reason':reason,'before_status':before['status'],'after_status':after['status'],'changes':[{'item_id':k,'before':old.get(k),'after':new.get(k)} for k in sorted(old.keys()|new.keys()) if old.get(k)!=new.get(k)],'requires_confirmation':True}
