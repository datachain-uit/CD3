"""Create a transparent inventory for the CQ current-layout V0 evidence."""
from pathlib import Path
import hashlib,json
ROOT=Path('CQ/resuilt')
OUT=ROOT/'cq_patchtst_v0_current_drive_20261102'
SOURCES={'runs':ROOT/'cq_patchtst_v0_current_seed42_r21',
         'audit':ROOT/'cq_patchtst_v0_current_seed42_r21_audit',
         'report_facts':ROOT/'cq_patchtst_v0_current_seed42_r21_report'}
DOC=Path('CQ/docs/REPORT_CQ_PATCHTST_V0_CURRENT_2026-10-31_STATIC_PROVENANCE.docx')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifests=list(SOURCES['runs'].rglob('run_manifest.json'))
    if len(manifests)!=3:raise ValueError('expected 3 manifests')
    records=[json.loads(p.read_text(encoding='utf8')) for p in manifests]
    if {m['window_id'] for m in records}!={'W1','W2','W3'}:raise ValueError('wrong windows')
    for m in records:
        if (m['pipeline_id'],m['model_name'],m['seed'],m['batch_size'],m['micro_batch_size'],m['accumulation_steps'])!=('V0','PATCHTST',42,2048,512,4):raise ValueError('wrong run contract')
    lines=[]
    for label,source in SOURCES.items():
        for p in sorted(source.rglob('*')):
            if p.is_file():lines.append(f'{sha(p)}  {label}/{p.relative_to(source).as_posix()}\n')
    lines.append(f'{sha(DOC)}  report/{DOC.name}\n')
    (OUT/'sha256sums.txt').write_text(''.join(lines),encoding='utf8')
    (OUT/'README.md').write_text('''# CQ PatchTST V0 current layout, seed 42

Three W1–W3 runs, audit, original download verification and first-epoch replay receipt. The three immutable manifests record runner 29da3b252dde9ed96f42f7bda7f886b11ae1efa1, layout sha256 367bf42bb9fcc68a91f5c8c9a2419cca28df7f8decfc8ceaa639b5ef6667b904, LR 0.001, no warm-up/clip and effective batch 2048 = 4 × 512. The historical manifest field reference_layout_sha256 is null; it is not modified or represented as a separately verified reference. The actual layout hash and replay evidence are retained. Audit includes sanity, evaluation slices, per-class, B=2000 bootstrap and checkpoint selection. This is a V0 bundle, not completion of the F2 grid.

sha256sums.txt records all source files in runs/, audit/, report_facts/ and report/. The first-epoch replay evidence is in report_facts/current_epoch1_replay_receipt.json. The run outputs and accompanying report may contain historical path references; those are provenance, not new Drive paths.
''',encoding='utf8')
    print(f'inventoried {len(lines)} files; layout reference null preserved')
if __name__=='__main__':main()
