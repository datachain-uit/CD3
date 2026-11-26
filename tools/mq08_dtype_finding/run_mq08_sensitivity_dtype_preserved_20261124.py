from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'tmp/mq08_sensitivity_20261124.py';text=source.read_text(encoding='utf8')
text=text.replace("mq08_sensitivity_main_20261124'","mq08_sensitivity_dtype_preserved_20261124'")
needle="perm[ state ] =" # intentionally match only the exact original expression below
needle="perm[state]=first.loc[pd.Series(groups).map(mapping).to_numpy()].to_numpy()"
assert text.count(needle)==1
text=text.replace(needle,"mapped=first.loc[pd.Series(groups).map(mapping).to_numpy()]\n   for col in state: perm[col]=pd.Series(mapped[col].array,index=perm.index).astype(tr[col].dtype)\n   assert all(perm[col].dtype==tr[col].dtype for col in state)")
text=text.replace('Five group permutations (seeds 0–4), five model seeds','Five group permutations (seeds 0–4), explicitly dtype-preserved state columns, five model seeds')
exec(compile(text,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
