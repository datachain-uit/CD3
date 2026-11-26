from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'tmp/mq08_targeted_diagnostics_20261124.py'
text=source.read_text(encoding='utf8')
text=text.replace("mq08_targeted_diagnostics_20261124'","mq08_targeted_dtype_preserved_20261124'")
needle="perm[cols]=first.loc[pd.Series(perm.rec_group_id).map(mapping).to_numpy()].to_numpy()"
assert text.count(needle)==1
text=text.replace(needle,"mapped=first.loc[pd.Series(perm.rec_group_id).map(mapping).to_numpy()];\n    for col in cols: perm[col]=pd.Series(mapped[col].array,index=perm.index).astype(train[col].dtype)\n    assert all(perm[col].dtype==train[col].dtype for col in cols)")
text=text.replace("fixed registered hyperparameters.","fixed registered hyperparameters; permuted state dtypes explicitly preserved.")
exec(compile(text,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
