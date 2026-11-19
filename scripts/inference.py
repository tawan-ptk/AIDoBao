"""Local MLX worker; communicates JSON via stdin/stdout, no health-content logs."""
import argparse, json, pathlib, sys, time, os, re
from datetime import datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['MLX_MPI_LIBNAME']=str(ROOT/'models/MPI_DISABLED_LOCAL_ONLY.dylib')
os.environ['HF_HUB_OFFLINE']='1'

from services.extraction import FIELDS,extraction_prompt,parse_extraction

def run(messages,adapter=None,max_tokens=512,task=None):
    import mlx.core as mx
    from mlx_lm import load,generate
    from mlx_lm.sample_utils import make_sampler
    from services.model_tasks import model_task
    from services.model_runtime import adapter_for
    task=task or model_task(messages)
    adapter=adapter or adapter_for(task)
    started=time.monotonic();mx.random.seed(42)
    model,tok=load(str(ROOT/'models/typhoon-4bit'),adapter_path=adapter)
    loaded=time.monotonic()
    prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    response=generate(model,tok,prompt=prompt,max_tokens=max_tokens,sampler=make_sampler(temp=0),verbose=False)
    return response,{'load_seconds':loaded-started,'generation_seconds':time.monotonic()-loaded,'peak_memory_gb':mx.get_peak_memory()/1e9,'model_task':task,'adapter':pathlib.Path(adapter).name if adapter else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--task',choices=['extract','generate'],default='generate');ap.add_argument('--adapter');ap.add_argument('--max-tokens',type=int,default=512);a=ap.parse_args()
    body=json.load(sys.stdin)
    if a.task=='extract':
        kind=body['kind'];text=body['text']
        system=extraction_prompt(kind)
        output,metrics=run([{'role':'system','content':system},{'role':'user','content':text}],a.adapter,a.max_tokens,task='extract')
        try:
            data,evidence=parse_extraction(output,kind,text)
            record={'kind':kind,'text':text,'data':data,'evidence':evidence,'source':'ข้อความผู้ใช้; โมเดลเสนอการแยกข้อมูล','origin':'model_proposal'}
            metrics['extraction_status']='proposal' if any(v is not None for v in data.values()) else 'no_supported_fields'
        except (ValueError,KeyError,TypeError):
            record={'kind':kind,'text':text,'data':{k:None for k in FIELDS[kind]},'evidence':{},'source':'แยกข้อความไม่ผ่าน กรุณากรอกฟอร์ม','origin':'model_proposal'}
            metrics['extraction_status']='invalid_model_output'
        print(json.dumps({'record':record,'metrics':metrics},ensure_ascii=False))
    else:
        output,metrics=run(body['messages'],a.adapter,a.max_tokens)
        print(json.dumps({'output':output,'metrics':metrics},ensure_ascii=False))
if __name__=='__main__':main()
