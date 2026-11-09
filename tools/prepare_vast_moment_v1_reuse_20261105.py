"""Use verified V1/W1 donor shards and create V1/W2-W3 fresh caches."""
from pathlib import Path
root=Path('upload_staging/vast_moment_v1_20261105');root.mkdir(parents=True,exist_ok=True)
donor='/workspace/CD3/moment_v1_20261105/donor_w1/8c66c22f24cb4e59892267057966163517c0ff6d1d245dcb6b7b34f7237124d1'
for window in ('w1','w2','w3'):
    source=Path(f'upload_staging/vast_moment_v5_20261105/run_{window}.py').read_text(encoding='utf8')
    source=source.replace('moment_v5_20261105','moment_v1_20261105')
    source=source.replace("'purpose':'SHARDED_CACHE_MULTI_EPOCH_DIAGNOSTIC_NOT_PRIMARY'", "'purpose':'V1_SHARDED_CACHE_CROSS_ENV_DIAGNOSTIC_NOT_PRIMARY'")
    source=source.replace("'timings':timings,'cache_direct_max_abs_logit_diff':maxdiff,", "'timings':timings,'cache_created_torch':identity.get('torch_version'),'runtime_torch':torch.__version__,'cache_direct_max_abs_logit_diff':maxdiff,")
    if window=='w1':
        start=source.index('    identity_hash=hashlib.sha256(')
        end=source.index('    cache.mkdir(parents=True,exist_ok=True)',start)
        source=source[:start]+f'''    # W1 donor was computed under Modal PyTorch 2.15. Match every source,
    # feature and backbone field; cross-runtime numerical check follows.
    donor=Path('{donor}')
    donor_identity=json.loads((donor/'identity.json').read_text())
    normalised=json.loads(json.dumps(identity,default=str))
    for key in normalised:
        if key!='torch_version' and normalised[key]!=donor_identity.get(key):
            raise ValueError(f'Donor identity mismatch: {{key}}')
    identity=donor_identity
    identity_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
    if identity_hash!=donor.name:raise ValueError('Donor identity hash mismatch')
    cache=donor
'''+source[end:]
    (root/f'run_{window}.py').write_text(source,encoding='utf8',newline='\n')
