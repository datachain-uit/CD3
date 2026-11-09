"""Package only explicitly partial phase-1 findings; never label as release."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

out = Path('CQ/resuilt/meta_phase1_work_in_progress_20261108')
out.mkdir(parents=True, exist_ok=True)
folders = {'s0_profile_partial': Path('CQ/resuilt/m13a_s0_profile_20261108'),
           'model_context_partial': Path('CQ/resuilt/m13b_model_context_20261108'),
           'offering_cq': Path('CQ/resuilt/cq_offering_dominance_20261108'),
           'fact_preflight': Path('CQ/resuilt/meta_phase1_preflight_20261108')}
for label, source in folders.items():
    target = out / label
    target.mkdir(exist_ok=True)
    for file in source.iterdir():
        if file.is_file() and not file.name.endswith('_probe.parquet'):
            shutil.copy2(file, target / file.name)
shutil.copy2('docs/05112026/FACTS_OF_RECORD_PHASE1_20261108.md', out / 'FACTS_OF_RECORD_DRAFT.md')
shutil.copy2('CQ/resuilt/s0_current_cq_20261108.zip', out / 's0_cq_raw_facts_current.zip')
lo_source = Path('LO/resuilt/s0_current_lo_modal_20261108')
inventory = json.loads((lo_source / 'inventory.json').read_text(encoding='utf8'))
if inventory['missing'] != 0 or len(inventory['files']) != 63:
    raise ValueError('LO S0 download is incomplete')
with zipfile.ZipFile(out / 's0_lo_raw_facts_current.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(lo_source.rglob('*')):
        if file.is_file() and not file.name.endswith('.partial'):
            archive.write(file, file.relative_to(lo_source).as_posix())
(out / 'README.md').write_text('# Phase-1 meta work in progress — NOT an official release\n\nContains current-release S0 fact downloads, a 48-row partial S0 profile, representative model contexts, CQ offering flags, a fact coverage preflight and a draft facts-of-record note. Missing mandatory profile columns remain NULL; F0 CQ, official assembler/QA and meta-model outputs are not included. Do not use as M-14 release. S0 LO was read from Volume without running a container.\n', encoding='utf8')
with (out / 'sha256sums.txt').open('w', encoding='utf8') as stream:
    for file in sorted(out.rglob('*')):
        if file.is_file() and file.name != 'sha256sums.txt':
            stream.write(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.relative_to(out).as_posix()}\n')
print('packaged', out)
