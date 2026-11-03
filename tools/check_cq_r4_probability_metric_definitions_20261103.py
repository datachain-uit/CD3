"""Check whether stored R4 model probability metrics reproduce from predictions."""
from pathlib import Path
import json,os,sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model.metrics import calibration_metrics, classification_metrics
ROOT=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029'
def main():
    r4=pd.read_parquet(ROOT/'L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023/cq_family_pipeline_window_phase_metrics.parquet')
    root=ROOT/'L1_runs/S3_model/preserved_packages'
    paths={'RNN':root/'cq_rnn_historical_layout_batch2048_seed42_20261020/CQ/W1/V0/seed=42/predictions/test_P1.parquet','LSTM':root/'cq_lstm_batch2048_full_20261018/lstm/CQ/W1/V0/seed=42/predictions/test_P1.parquet','GRU':root/'cq_recurrent_batch2048_seed42_20261019/gru/CQ/W1/V0/seed=42/predictions/test_P1.parquet','BILSTM':root/'cq_recurrent_batch2048_seed42_20261019/bilstm/CQ/W1/V0/seed=42/predictions/test_P1.parquet'}
    results=[]
    for family,f in paths.items():
        pred=pd.read_parquet(f); y=pred.y_true.str.removeprefix('c').astype(int).to_numpy(); yp=pred.y_pred.str.removeprefix('c').astype(int).to_numpy(); prob=pred[['prob_c0','prob_c1','prob_c2']].to_numpy();labels=np.arange(3)
        metric,_=classification_metrics(y,yp,prob,labels);metric.update(calibration_metrics(y,prob,labels))
        row=r4[(r4.model_name==family)&(r4.pipeline_id=='V0')&(r4.window_id=='W1')&(r4.phase_id=='P1')&(r4.eval_split=='TEST')]
        if len(row)!=1:raise ValueError('R4 key mismatch')
        row=row.iloc[0];cols=['multiclass_nll','multiclass_brier','top_label_ece_15','pr_auc_macro'];delta={k:float(abs(row[k]-metric[k])) for k in cols}
        results.append({'family':family,'rows':len(pred),'max_abs_differences':delta,'result':'PASS_1E-12' if max(delta.values())<=1e-12 else 'MISMATCH_1E-12'})
    result={'scope':'CQ W1 V0 TEST P1, four families','results':results}
    out=Path('CQ/resuilt/cq_r4_evaluation_slices_20261102');out.mkdir(parents=True,exist_ok=True);(out/'probability_metric_preflight.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
