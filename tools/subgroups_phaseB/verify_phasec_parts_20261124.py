import hashlib,json,os
from pathlib import Path
root=Path(os.environ.get('TEMPO_PHASEC_OUTPUT', 'CQ/resuilt/mm_runs_phaseC_r2_20261123'))
rows=json.loads((root/'large_file_parts/parts_manifest.json').read_text())
for row in rows:
 h=hashlib.sha256()
 for part in row['parts']:
  data=(root/part['path']).read_bytes()
  assert len(data)==part['bytes'] and hashlib.sha256(data).hexdigest()==part['sha256']
  h.update(data)
 assert h.hexdigest()==row['sha256'],row['original']
print('files reconstructed and hashes matched:',len(rows))
