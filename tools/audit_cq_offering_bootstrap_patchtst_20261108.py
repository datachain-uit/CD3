"""Compute flagged CQ PatchTST offering-cluster bootstrap from verified runs."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile

import pandas as pd
from audit_cq_offering_bootstrap_grid_20261108 import (
    ROOT, OUT, TMP, DATA, SALT, DRIVE, cohort, run_cell,
)

BASE = 'gdrive:Jobs/CQ/organized_moved_20261029/L1_runs/S3_model/run_bundles/cq_patchtst_v0_current_20261102/runs/CQ'
inventory = json.loads((ROOT / 'CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103/source_inventory.json').read_text(encoding='utf8'))
sources = {item['version']: item for item in inventory}
status_path = OUT / 'patchtst_status.json'

def status(value, **fields):
    status_path.write_text(json.dumps({'status': value, **fields}, indent=2) + '\n', encoding='utf8')

def sha(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def process(path, version, window, phase, datasets, source_ref, archive_sha=None):
    item = {'window_id': window, 'model_name': 'PATCHTST', 'pipeline_id': version, 'phase_id': phase}
    result = run_cell(item, datasets, local_prediction=path)
    output = OUT / 'cells' / 'PATCHTST' / window / version / f'TEST_{phase}.json'
    record = json.loads(output.read_text(encoding='utf8'))
    record.update(prediction_source=source_ref, source_archive_sha256=archive_sha)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(record) + '\n', encoding='utf8')
    temporary.replace(output)
    return result

def main():
    # PatchTST shell command substitution removed LF only; preserve a CR
    # byte when it is part of the original prediction salt (RNN differs).
    salt = SALT.read_bytes().rstrip(b'\n').decode('utf8')
    if not salt:
        raise ValueError('empty salt')
    datasets = {window: cohort(window, salt) for window in ('W1', 'W3')}
    done, errors = 0, []
    status('RUNNING', cells_total=56, cells_done=0, errors=errors)
    for version in ('V0', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
        if version == 'V0':
            for window in ('W1', 'W3'):
                for phase in ('P1', 'P2', 'P3', 'P4'):
                    remote = f'{BASE}/{window}/V0/PATCHTST/seed=42/predictions/test_{phase}.parquet'
                    temp = TMP / f'PATCHTST_{window}_V0_{phase}.parquet'
                    try:
                        subprocess.run(['rclone', 'copyto', remote, str(temp), '--drive-root-folder-id', DRIVE,
                                        '--retries', '3'], check=True, timeout=600, capture_output=True)
                        outcome = process(temp, version, window, phase, datasets, remote)
                        done += 1
                        print(version, window, phase, outcome, done, flush=True)
                    except Exception as exc:
                        errors.append({'version': version, 'window': window, 'phase': phase, 'error': str(exc)})
                    finally:
                        temp.unlink(missing_ok=True)
                    status('RUNNING', cells_total=56, cells_done=done, errors=errors)
            continue
        source = sources[version]
        archive = Path(source['archive'])
        if not archive.is_file() or sha(archive) != source['sha256']:
            errors.append({'version': version, 'error': 'source archive missing or checksum mismatch'})
            status('RUNNING', cells_total=56, cells_done=done, errors=errors)
            continue
        wanted = {(w, p): f'/CQ/{w}/{version}/PATCHTST/seed=42/predictions/test_{p}.parquet'
                  for w in ('W1', 'W3') for p in ('P1', 'P2', 'P3', 'P4')}
        found = set()
        with tarfile.open(archive, mode='r|gz') as tar:
            for member in tar:
                match = next((key for key, suffix in wanted.items() if member.name.endswith(suffix)), None)
                if match is None or not member.isfile():
                    continue
                window, phase = match
                temp = TMP / f'PATCHTST_{window}_{version}_{phase}.parquet'
                try:
                    with tar.extractfile(member) as source_file, temp.open('wb') as output:
                        while chunk := source_file.read(1024 * 1024):
                            output.write(chunk)
                    outcome = process(temp, version, window, phase, datasets, f'{archive.name}:{member.name}', source['sha256'])
                    found.add(match); done += 1
                    print(version, window, phase, outcome, done, flush=True)
                except Exception as exc:
                    errors.append({'version': version, 'window': window, 'phase': phase, 'error': str(exc)})
                finally:
                    temp.unlink(missing_ok=True)
                status('RUNNING', cells_total=56, cells_done=done, errors=errors)
                if len(found) == 8:
                    break
        missing = set(wanted).difference(found)
        if missing:
            errors.append({'version': version, 'missing': sorted(missing)})
    status('COMPLETE' if done == 56 and not errors else 'PARTIAL_ERRORS', cells_total=56, cells_done=done, errors=errors)

if __name__ == '__main__':
    main()
