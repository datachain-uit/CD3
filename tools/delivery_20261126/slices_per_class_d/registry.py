import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
from pathlib import Path
R=Path(REPO); A=Path(AUDIT44); W=Path(f'{WORKD}/src')
CQR=R/'CQ/resuilt'; LOR=R/'LO/resuilt'
REC=['RNN','LSTM','GRU','BILSTM']
TABLES=['evaluation_slices','metrics_per_class','bootstrap_metrics_per_class','cohort_slice_status']
# unit -> dict(drive_pkg=..., dirs=[(dir, drivepkg_relative)], sanity_key)
def units():
    u={}
    s43c=W/'CQ/seed43'; s43l=W/'LO/seed43'
    for task,s43,fam44 in (('CQ',s43c,'CQ'),('LO',s43l,'LO')):
        t=task.lower()
        # seed 43
        for m in REC:
            d=s43/f'F1_recurrent/{t}_f1_recurrent_v0_v16_full_facts_seed43_20261116/{m}'
            u[(task,m,43)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=43/F1_recurrent/{t}_f1_recurrent_v0_v16_full_facts_seed43_20261116/{m}')],
              accepted_sanity=A/f'asm_inputs/seed43/{task}_f1_recurrent/{m}/sanity_components.csv', sanity_in=d/'sanity_components.csv')
        d=s43/f'F2_PatchTST/{t}_patchtst_v0_v16_full_facts_seed43_20261116'
        u[(task,'PATCHTST',43)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=43/F2_PatchTST/{d.name}')],accepted_sanity=A/f'asm_inputs/seed43/{task}_patchtst/sanity_components.csv',sanity_in=d/'sanity_components.csv')
        d=s43/f'F3_Mantis/{t}_mantis_v2_v0_v16_full_facts_seed43_20261116'
        u[(task,'MANTIS_V2',43)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=43/F3_Mantis/{d.name}')],accepted_sanity=A/f'asm_inputs/seed43/{task}_mantis_v2/sanity_components.csv',sanity_in=d/'sanity_components.csv')
        # seed 44
        for m in REC:
            d=A/f'facts44/{task}_f1_recurrent_v0_v16_seed44/{m}'
            u[(task,m,44)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=44/F1_recurrent/{t}_f1_recurrent_v0_v16_full_facts_seed44_20261118/{m}')],
              accepted_sanity=d/'sanity_components.csv',sanity_in=d/'sanity_components.csv')
        d=A/f'facts44/{task}_patchtst_v0_v16_seed44'
        u[(task,'PATCHTST',44)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=44/F2_PatchTST/{t}_patchtst_v0_v16_full_facts_seed44_20261119')],accepted_sanity=d/'sanity_components.csv',sanity_in=d/'sanity_components.csv')
        d=A/f'facts44/{task}_mantis_v2_v0_v16_seed44'
        u[(task,'MANTIS_V2',44)]=dict(dirs=[(d,f'{task}/L2_facts/model_facts/seed=44/F3_Mantis/{t}_mantis_v2_v0_v16_full_facts_seed44_20261119')],accepted_sanity=d/'sanity_components.csv',sanity_in=d/'sanity_components.csv')
    # seed 42 F2/F3
    def s42(task,m,dirs):
        u[(task,m,42)]=dict(dirs=dirs,accepted_sanity=None,sanity_in=None)
    s42('CQ','PATCHTST',[(CQR/'cq_patchtst_v0_v6_full_facts_20261103_r2','CQ/L2_facts/model_facts/seed=42/F2_PatchTST/cq_patchtst_v0_v6_full_facts_20261103_r2'),
                         (CQR/'cq_patchtst_v7_v16_full_facts_20261109_r2','CQ/L2_facts/model_facts/seed=42/F2_PatchTST/cq_patchtst_v7_v16_full_facts_20261109_r2')])
    s42('CQ','MANTIS_V2',[(CQR/'cq_mantis_v2_v0_v16_full_facts_20261109_r3','CQ/L2_facts/model_facts/seed=42/F3_Mantis/cq_mantis_v2_v0_v16_full_facts_20261109_r3')])
    s42('LO','PATCHTST',[(LOR/'lo_patchtst_v0_v16_full_facts_20261109_r2','LO/L2_facts/model_facts/seed=42/F2_PatchTST/lo_patchtst_v0_v16_full_facts_20261109_r2')])
    s42('LO','MANTIS_V2',[(LOR/'lo_mantis_v2_v0_v16_full_facts_20261110','LO/L2_facts/model_facts/seed=42/F3_Mantis/lo_mantis_v2_v0_v16_full_facts_20261110')])
    return u
