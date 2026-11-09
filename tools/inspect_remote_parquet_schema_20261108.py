"""Read only a remote parquet footer for schema discovery, not data rows."""
import io
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import pyarrow.parquet as pq

remote = ('gdrive:Jobs/CQ/organized_moved_20261029/input_archives/source_inputs_20261029/'
          '_checked_feature_v2/phase_views_v2_2/phase_views_v2_2/'
          'part-00000-tid-8484414151895402239-401f2d3e-2459-419e-9948-08afba362ad1-1561-1.c000.snappy.parquet')
size = 643863865
length = 2 * 1024 * 1024
p = subprocess.run(['rclone', 'cat', remote, '--offset', str(size - length), '--count', str(length),
                    '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'],
                   check=True, capture_output=True, timeout=180)
tail = p.stdout
if len(tail) != length or tail[-4:] != b'PAR1':
    raise ValueError('Invalid remote parquet footer')
metadata_size = struct.unpack('<I', tail[-8:-4])[0]
if metadata_size + 8 > len(tail):
    raise ValueError('Footer exceeds fetched tail')
fake = io.BytesIO(b'PAR1' + tail[-metadata_size - 8:])
file = pq.ParquetFile(fake)
names = file.schema_arrow.names
matches = [name for name in names if any(word in name.lower() for word in
           ('coelo', 'afelo', 'acelo', 'triad', 'observed_length', 'chapter', 'event_count',
            'cutoff', 'offering', 'duration', 'start', 'finish', 'length', 'timestamp'))]
print('rows', file.metadata.num_rows, 'columns', len(names), 'matches', matches)
out = Path('CQ/resuilt/f0_partial_triad_source_audit_20261108')
out.mkdir(parents=True, exist_ok=True)
report = {'source': remote, 'source_size_bytes': size, 'num_rows': file.metadata.num_rows,
          'footer_tail_bytes': length, 'footer_tail_sha256': hashlib.sha256(tail).hexdigest(),
          'schema_columns': names, 'matched_columns': matches,
          'triad_component_columns': [name for name in names if any(term in name.lower() for term in ('coelo', 'afelo', 'acelo', 'triad'))],
          'scope': 'Parquet footer/schema only; no full-file checksum or row data read',
          'status': 'FINAL_COMPONENTS_ONLY_NO_PARTIAL_TRIAD_COLUMNS_IN_THIS_VIEW'}
(out / 'cq_train_validation_view_schema.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
