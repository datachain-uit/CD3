from hashlib import sha256
from pathlib import Path
import pandas as pd

salt = Path('downloads/private/cq_patchtst_prediction_salt').read_text(encoding='utf8').strip()
raw = pd.read_parquet('downloads/vastai/CQ_V2_2_clean_grain_seed42/evaluation/W1/V0/test_P1.parquet',
                      columns=['enrollment_id', 'CQ_label_final'])
raw['enrollment_id_hash'] = raw.enrollment_id.astype(str).map(lambda x: sha256(f'{salt}|{x}'.encode()).hexdigest())
raw['expected'] = raw.CQ_label_final.map({'warning': 'c0', 'average': 'c1', 'good': 'c2'})
for model in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    name = f'{model.lower()}_w1_v0_test_p1_probe.parquet' if model == 'GRU' else f'{model}_w1_v0_test_p1_probe.parquet'
    pred = pd.read_parquet(Path('CQ/resuilt/cq_offering_dominance_20261108') / name,
                           columns=['enrollment_id_hash', 'y_true'])
    match = raw[['enrollment_id_hash', 'expected']].merge(pred, on='enrollment_id_hash', how='outer',
                                                          validate='one_to_one', indicator=True)
    print(model, 'rows', len(match), 'matches', int(match._merge.eq('both').sum()),
          'labels_match', bool(match.expected.eq(match.y_true).all()))
