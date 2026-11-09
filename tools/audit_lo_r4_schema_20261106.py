"""Compare LO facts with CQ R4 while retaining source/version caveats."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import pandas as pd

CQ=Path('CQ/resuilt/input/results/GD1_CQ_V2_2_clean_r1/cq_family_pipeline_window_phase_metrics.parquet')
LO=Path('LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_family_pipeline_window_phase_metrics.parquet')
OUT=Path('LO/resuilt/lo_r4_schema_audit_20261106')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=pd.read_parquet(CQ); b=pd.read_parquet(LO); shared=sorted(set(a.columns)&set(b.columns)); only_cq=sorted(set(a.columns)-set(b.columns))
 key=['task','model_name','window_id','pipeline_id','seed','eval_split','phase_id']
 out=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),cq_rows=len(a),lo_rows=len(b),cq_only_columns=only_cq,lo_only_columns=sorted(set(b.columns)-set(a.columns)),type_differences={c:[str(a[c].dtype),str(b[c].dtype)] for c in shared if str(a[c].dtype)!=str(b[c].dtype)},cq_duplicate_keys=int(a.duplicated(key).sum()),lo_duplicate_keys=int(b.duplicated(key).sum()),cq_sha256=digest(CQ),lo_sha256=digest(LO),scope='Schema names/types and key uniqueness only; no source provenance, value semantics or downstream compatibility proof.')
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'schema_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
