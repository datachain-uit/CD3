"""Wait for short comparison and submit one-epoch diagnostic only if GPU check passes."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'CQ/resuilt/mantis_v2_microbatch_compare_20261107';OUT.mkdir(parents=True,exist_ok=True)
comparison=OUT/'comparison.json';state=OUT/'watcher_state.json'
def save(status,**kw):state.write_text(json.dumps({'status':status,'time_utc':datetime.now(timezone.utc).isoformat(),**kw},indent=2)+'\n',encoding='utf8')
def main():
 save('WAITING_FOR_COMPARISON')
 for _ in range(360):
  result=subprocess.run([sys.executable,'-X','utf8','-m','modal','volume','get','tempo-data-v1','/diagnostics/mantis_v2_microbatch_compare_20261107/comparison.json',str(comparison)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
  if result.returncode==0 and comparison.exists():break
  time.sleep(60)
 else:save('COMPARISON_TIMEOUT');return
 data=json.loads(comparison.read_text(encoding='utf8'));a=data['results']['2048'];b=data['results']['4096']
 if not a['finite'] or not b['finite'] or b['peak_reserved_bytes']>=21*1024**3:
  save('NOT_STARTED_PRECHECK_FAILED',comparison=data['comparison'],peak_reserved_bytes=b['peak_reserved_bytes']);return
 save('PRECHECK_PASSED_SUBMITTING',comparison=data['comparison'],peak_reserved_bytes=b['peak_reserved_bytes'])
 with (OUT/'pilot_submit.log').open('w',encoding='utf8') as log:
  proc=subprocess.Popen([sys.executable,'-X','utf8','-m','modal','run','--detach','modal_jobs/mantis_v2_cq_w1_v1_micro4096_one_epoch_20261107.py'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  save('PILOT_SUBMIT_PROCESS_STARTED',pid=proc.pid,comparison=data['comparison'],peak_reserved_bytes=b['peak_reserved_bytes'])
  rc=proc.wait();save('PILOT_SUBMIT_COMMAND_EXITED',exit_code=rc,comparison=data['comparison'],peak_reserved_bytes=b['peak_reserved_bytes'])
if __name__=='__main__':main()
