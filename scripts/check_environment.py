import datetime,importlib.metadata,json,pathlib,platform,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'platform':platform.platform(),'python':sys.version,'packages':{x:importlib.metadata.version(x) for x in ['mlx','mlx-lm','transformers','fastapi','pydantic','pandas','pyreadstat','pytest']}}
    for key,cmd in [('chip',['sysctl','-n','machdep.cpu.brand_string']),('memory',['sysctl','-n','hw.memsize']),('memory_pressure',['memory_pressure','-Q'])]:
        r=subprocess.run(cmd,capture_output=True,text=True);report[key]={'exit_code':r.returncode,'output':r.stdout.strip(),'error':r.stderr.strip()}
    (ROOT/'reports/environment.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
