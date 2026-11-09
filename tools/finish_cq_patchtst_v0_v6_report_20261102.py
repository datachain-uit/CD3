"""Wait for verified V2/V4 downloads, then rebuild the full V0–V6 report."""
from pathlib import Path
import subprocess,sys,time

root=Path(__file__).resolve().parents[1]
receipts=[root/'CQ/resuilt'/f'cq_patchtst_{v}_seed42_20261101'/'download_receipt.json' for v in ('v2','v4')]
for _ in range(2880):
    if all(p.is_file() for p in receipts):
        print('Both verified download receipts present; rebuilding report',flush=True)
        subprocess.run([sys.executable,'-u','-X','utf8',str(root/'tools/report_cq_patchtst_v0_v6_20261102.py')],cwd=root,check=True)
        break
    time.sleep(30)
else:
    raise TimeoutError('V2/V4 verified receipts not both present after 24h; report retained as partial')
