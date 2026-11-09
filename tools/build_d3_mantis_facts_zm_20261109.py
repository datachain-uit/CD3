"""D3 (request 2026-11-09): (1) Mantis CQ facts package r2: model_tier / variant_role / run_purpose on every checkpoint_selection row,
resource_null_reason for the rows without hours/energy; (2) Z_M with a MANTIS_V2 row (M-13b v2).
Sources: cq_mantis_v2_v0_v16_full_facts_20261109, m13b_z_m_delivery_20261108, standardized run manifests (energy_null_reason), CQ/W1/V0 cell record.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--std-roots', type=Path, nargs='+', required=True)
ap.add_argument('--cell-record', type=Path, required=True, help='f3_cell_record.json of CQ/W1/V0')
ap.add_argument('--probe-head', type=Path, required=True, help='probe_head.pt of CQ/W1/V0')
ap.add_argument('--lo-cell-record', type=Path, required=True, help='f3_cell_record.json of LO/W1/V0')
ap.add_argument('--layout', type=Path, required=True, help='feature_layout.json of CQ/W1/V0')
ap.add_argument('--layout-sha', required=True, help='feature_layout_sha256 of CQ/W1/V0 (from its run manifest)')
args = ap.parse_args()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_sums(d):
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    with open(d / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in files))


# ---- (1) facts package r2
SRC = Path('CQ/resuilt/cq_mantis_v2_v0_v16_full_facts_20261109')
OUT = Path('CQ/resuilt/cq_mantis_v2_v0_v16_full_facts_20261109_r2')
if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)
ck = pd.read_parquet(OUT / 'checkpoint_selection.parquet')
before = {c: int(ck[c].notna().sum()) for c in ('model_tier', 'variant_role', 'run_purpose')}
ck['model_tier'] = 'F3_TS_FOUNDATION'
ck['variant_role'] = 'EXPLORATORY'
ck['run_purpose'] = 'EXPLORATORY_CACHE_VALIDATION'
ck.to_parquet(OUT / 'checkpoint_selection.parquet', index=False)
ck.to_csv(OUT / 'checkpoint_selection.csv', index=False)
res = pd.read_parquet(OUT / 'resource_per_run.parquet')
reasons = {}
for root in args.std_roots:
    for mp in root.glob('CQ/W*/V*/MANTIS_V2/seed=42/run_manifest.json'):
        m = json.loads(mp.read_text(encoding='utf-8'))
        reasons[(m['pipeline_id'], m['window_id'])] = m.get('energy_null_reason')


def reason(row):
    if row.pipeline_id == 'V0':
        return ('NOT_RECORDED: the original V0 run kept no run manifest, wall-clock time or GPU energy; predictions and metrics were rebuilt from '
                'the stored probabilities (validation score equals the cell record); train_seconds is the sum of the recorded epoch durations')
    if str(row.energy_measurement_type) == 'UNAVAILABLE':
        return reasons.get((row.pipeline_id, row.window_id)) or 'NVML_POWER_SAMPLING_UNAVAILABLE_FOR_THIS_RUN'
    return None


res['resource_null_reason'] = res.apply(reason, axis=1)
res.to_parquet(OUT / 'resource_per_run.parquet', index=False)
res.to_csv(OUT / 'resource_per_run.csv', index=False)
summary = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
summary.update({'revision': 'r2', 'r2_changes': [
    f'checkpoint_selection: model_tier, variant_role, run_purpose set on all {len(ck)} rows (were set on {before})',
    f'resource_per_run: resource_null_reason added ({int(res.resource_null_reason.notna().sum())} rows with a reason)']})
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
readme = (OUT / 'README.md').read_text(encoding='utf-8')
(OUT / 'README.md').write_text(
    readme + '\n## Revision r2 (09/11/2026)\n\n`checkpoint_selection` now carries `model_tier = F3_TS_FOUNDATION`, `variant_role = EXPLORATORY` and '
    '`run_purpose = EXPLORATORY_CACHE_VALIDATION` on every row. `resource_per_run` has `resource_null_reason` for the rows without hours or energy '
    '(three V0 cells rebuilt from stored probabilities; runs whose NVML sampling was unavailable). Values of every other column are unchanged.\n', encoding='utf-8')
write_sums(OUT)
print('facts r2:', before, '->', {c: int(ck[c].notna().sum()) for c in before}, '| null reasons', int(res.resource_null_reason.notna().sum()))

# ---- (2) Z_M v2
ZS = Path('CQ/resuilt/m13b_z_m_delivery_20261108')
ZO = Path('CQ/resuilt/m13b_z_m_delivery_20261109_v2')
if ZO.exists():
    shutil.rmtree(ZO)
shutil.copytree(ZS, ZO)
z = pd.read_csv(ZO / 'z_m.csv')
rec = json.loads(args.cell_record.read_text(encoding='utf-8'))
lo = json.loads(args.lo_cell_record.read_text(encoding='utf-8'))
lay = json.loads(args.layout.read_text(encoding='utf-8'))
used, total_backbone, head = 2214144, 4188672, int(rec['param_count_trainable'])
assert int(rec['param_count_total']) == used + head, (rec['param_count_total'], used, head)
assert head == 12366, head          # the figure quoted by the writing side
total = used + head
static = len(lay['static_columns']) + len(lay['mask_static_columns'])
row = {'model_name': 'MANTIS_V2', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MANTIS', 'param_count_total': total, 'param_count_trainable': head,
       'log10_param_count': math.log10(total), 'uses_mask_channels': 1, 'uses_delta_t': 1, 'max_seq_len': np.nan, 'patch_len': np.nan, 'patch_stride': np.nan,
       'lr': 0.001, 'batch_size': 2048, 'max_epochs': 50, 'loss_name': 'cross_entropy', 'class_weighting': 'NONE',
       'reference_task': 'CQ', 'reference_window': 'W1', 'reference_pipeline': 'V0', 'reference_layout_sha256': args.layout_sha,
       'reference_checkpoint_sha256': sha(args.probe_head), 'reference_dynamic_channels': int(rec['adapter']['n_channels']),
       'reference_static_channels': int(static), 'model_revision': 'mantisv2_frozen_linear_probe_v1_pca8_interp512'}
extra = {'param_count_backbone_used': used, 'param_count_backbone_total': total_backbone, 'frozen_backbone': 1, 'return_transf_layer': 2,
         'output_token': 'combined', 'interp_len': 512, 'adapter_components': 8}
for c in extra:
    z[c] = None if c == 'output_token' else np.nan
row.update(extra)
z['frozen_backbone'] = z['frozen_backbone'].fillna(0).astype(int)
z = pd.concat([z, pd.DataFrame([row])], ignore_index=True)
z.to_csv(ZO / 'z_m.csv', index=False)
z.to_parquet(ZO / 'z_m.parquet', index=False)
bl = pd.read_csv(ZO / 'z_m_param_counts_by_layout.csv')
add = [{'model_name': 'MANTIS_V2', 'task_layout': 'CQ/W1/V0', 'param_count_total': total, 'param_count_trainable': head,
        'reference_static_channels': int(static), 'reference_dynamic_channels': int(rec['adapter']['n_channels'])},
       {'model_name': 'MANTIS_V2', 'task_layout': 'LO/W1/V0', 'param_count_total': int(lo['param_count_total']), 'param_count_trainable': int(lo['param_count_trainable']),
        'reference_static_channels': 25, 'reference_dynamic_channels': 148}]
pd.concat([bl, pd.DataFrame(add)], ignore_index=True).to_csv(ZO / 'z_m_param_counts_by_layout.csv', index=False)
zr = (ZO / 'README.md').read_text(encoding='utf-8')
note = (f'\n## v2 (09/11/2026): MANTIS_V2 row\n\n`param_count_total` = {total} = backbone parameters actually used ({used} of {total_backbone} in the checkpoint: '
        f'the encoder is truncated at `return_transf_layer` 2) + the linear probe ({head}, CQ/W1/V0; LO/W1/V0: {int(lo["param_count_trainable"])}). '
        '`param_count_trainable` is the probe only; the backbone is frozen (`frozen_backbone` = 1). `max_seq_len`, `patch_len`, `patch_stride` are NULL '
        '(PatchTST patching does not exist in Mantis). New columns: `param_count_backbone_used`, `param_count_backbone_total`, `frozen_backbone`, '
        '`return_transf_layer`, `output_token`, `interp_len`, `adapter_components` (NULL, or 0 for `frozen_backbone`, for the other models). Reference layout: CQ/W1/V0 '
        f'({int(rec["adapter"]["n_channels"])} dynamic channels, {int(static)} static channels); input encoding PCA8 per phase then linear resize to 512 points. '
        'Rows 1-5 are unchanged from v1.\n')
(ZO / 'README.md').write_text(zr.replace('# Z_M — model context (M-13b), five rows', '# Z_M — model context (M-13b), v2: six rows (MANTIS_V2 added)') + note, encoding='utf-8')
write_sums(ZO)
print('Z_M v2 rows:', len(z), '| MANTIS total/trainable', total, head, '| LO head', lo['param_count_trainable'], '| static', static)
