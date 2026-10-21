"""Join W1 ablation predictions by their own salt; report seen-course x strict slices."""
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, recall_score

base = Path('LO/resuilt/lo_static_ablation_20261019')
data = Path('downloads/vastai/LO_V3_1_clean_grain_seed42')
salt = (base / '.ablation_prediction_salt').read_text(encoding='utf-8').strip()
if not salt:
    raise ValueError('Missing ablation prediction salt')
classes = {'I/D': 'c0', 'G': 'c1', 'E': 'c2'}
rows = []
for pipeline, parent in [('V0', 'V0'), ('V8', 'V5')]:
    train = pd.read_parquet(data / 'train/W1' / parent / 'train.parquet', columns=['context__course_id'])
    if train['context__course_id'].isna().any():
        raise ValueError(f'Null training course IDs: {parent}')
    courses = set(train['context__course_id'].astype(str))
    del train
    for split in ('validation', 'test'):
        for phase in ('P1', 'P2', 'P3', 'P4'):
            name = 'validation.parquet' if split == 'validation' else f'test_{phase}.parquet'
            strict = f'context__temporal_strict_{phase}'
            frame = pd.read_parquet(data / 'evaluation/W1' / parent / name,
                                    columns=['enrollment_id', 'context__course_id', 'LO_performance_label_3', strict])
            if frame[['enrollment_id', 'context__course_id', strict]].isna().any().any():
                raise ValueError(f'Null cohort key: {pipeline}/{split}/{phase}')
            frame['enrollment_id_hash'] = frame.enrollment_id.astype(str).map(lambda x: sha256(f'{salt}|{x}'.encode()).hexdigest())
            if frame.enrollment_id_hash.duplicated().any():
                raise ValueError('Duplicate cohort hash')
            frame['course_cohort'] = np.where(frame['context__course_id'].astype(str).isin(courses), 'SEEN_COURSE', 'UNSEEN_COURSE')
            frame['temporal_slice'] = np.where(frame[strict] == 1, 'STRICT', 'OVERLAP')
            if not frame[strict].isin([0, 1]).all():
                raise ValueError('Invalid strict flag')
            for variant in ('no_static', 'gender_duration'):
                path = base / variant / 'LO/W1' / pipeline / 'LSTM/seed=42/predictions' / f'{split}_{phase}.parquet'
                pred = pd.read_parquet(path, columns=['enrollment_id_hash', 'y_true', 'y_pred'])
                joined = frame.merge(pred, on='enrollment_id_hash', validate='one_to_one', how='outer', indicator=True)
                if not joined['_merge'].eq('both').all() or not joined['LO_performance_label_3'].map(classes).eq(joined.y_true).all():
                    raise ValueError(f'Hash or label mismatch: {path}')
                for (course, temporal), part in joined.groupby(['course_cohort', 'temporal_slice']):
                    true, predicted = part.y_true, part.y_pred
                    support = true.value_counts()
                    recall = recall_score(true, predicted, labels=['c0', 'c1', 'c2'], average=None, zero_division=0)
                    rows.append({'pipeline': pipeline, 'variant': variant, 'split': split.upper(), 'phase': phase,
                                 'course_cohort': course, 'temporal_slice': temporal, 'n': len(part),
                                 'support_c0': int(support.get('c0', 0)), 'support_c1': int(support.get('c1', 0)),
                                 'support_c2': int(support.get('c2', 0)), 'recall_c0': recall[0], 'recall_c1': recall[1],
                                 'recall_c2': recall[2], 'macro_f1_fixed3': f1_score(true, predicted, labels=['c0', 'c1', 'c2'], average='macro', zero_division=0),
                                 'small_support_flag': bool(int(support.min()) < 400 if len(support) == 3 else True)})
            print(pipeline, split, phase, flush=True)
result = pd.DataFrame(rows)
result.to_csv(base / 'ablation_seen_course_x_strict.csv', index=False)
print('cohort_slices', len(result))
