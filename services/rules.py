"""Health rules require actual review metadata before activation."""
REGISTRY=[
 {'rule_id':'schedule.no_overlap.v1','kind':'program','status':'reviewed','reviewer':'software tests','required_fields':['start','end'],'missing':'unknown','scope':'all scheduled intervals','units':'ISO8601 with timezone','source':'services/scheduler.py'},
 {'rule_id':'schedule.locked_time.v1','kind':'program','status':'reviewed','reviewer':'software tests','required_fields':['fixed','earliest'],'missing':'unknown','scope':'medication and appointments','units':'local time','source':'services/schemas.py'},
 {'rule_id':'health.suitability.v1','kind':'health','status':'draft','reviewer':None,'reviewed_at':None,'required_fields':['individual assessment'],'missing':'unknown','scope':'adult type 2 diabetes','units':None,'source':'niddk-healthy','location':'How can physical activity help manage my diabetes?','condition':'Individual activity suitability must be reviewed; no automatic thresholds','enabled':False},
]
def health_rule_enabled(rule):
    return rule.get('kind')=='health' and rule.get('status')=='reviewed' and bool(rule.get('reviewer')) and bool(rule.get('reviewed_at')) and rule.get('enabled') is True
