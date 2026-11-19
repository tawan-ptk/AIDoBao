"""Run the installed CLI and capture actual resource telemetry and logs."""
import argparse, datetime, json, pathlib, subprocess, sys, time
import psutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='models/pilot.yaml');ap.add_argument('--label',default='pilot');ap.add_argument('--resume');a=ap.parse_args()
    audit=json.loads((ROOT/'reports/training-data-audit.json').read_text())
    if not audit['counts']['train']:raise SystemExit('No eligible training data')
    # This entry point never downloads datasets or consumes local user records.
    command=[sys.executable,str(ROOT/'scripts/mlx_entry.py'),'--config',a.config]
    if a.resume:command+=['--resume-adapter-file',a.resume]
    start=time.monotonic();samples=[]
    with (ROOT/'logs'/f'{a.label}.log').open('w') as log:
        proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        process=psutil.Process(proc.pid)
        baseline=psutil.swap_memory().used
        while proc.poll() is None:
            try:
                sample={'seconds':time.monotonic()-start,'rss_bytes':process.memory_info().rss,'available_bytes':psutil.virtual_memory().available,'swap_used_bytes':psutil.swap_memory().used,'memory_pressure':subprocess.run(['memory_pressure','-Q'],capture_output=True,text=True).stdout.strip()}
                samples.append(sample)
                # Stop on sustained large additional swap pressure rather than forcing the machine.
                if len(samples)>=3 and all(x['swap_used_bytes']-baseline>2_000_000_000 and x['available_bytes']<800_000_000 for x in samples[-3:]):
                    proc.terminate();log.write('\nStopped: sustained memory pressure threshold.\n');proc.wait();break
            except psutil.NoSuchProcess:break
            time.sleep(2)
    result={'command':command,'exit_code':proc.wait(),'elapsed_seconds':time.monotonic()-start,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'samples':samples,'resume_semantics':'adapter weights only; optimizer/RNG not restored' if a.resume else None}
    (ROOT/'reports'/f'{a.label}-resources.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='samples'},indent=2));sys.exit(result['exit_code'])
if __name__=='__main__':main()
