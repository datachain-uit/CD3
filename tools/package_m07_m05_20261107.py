"""Prepare M-07 split evidence and validate M-05 LO offering facts locally."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "LO/resuilt/m07_m05_delivery_20261107"
if DEST.exists():
    raise FileExistsError(f"Choose a new output; this already exists: {DEST}")

support_path = ROOT / "LO/resuilt/lo_offering_bootstrap_delivery_20261107"
metrics_path = ROOT / "LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_family_pipeline_window_phase_metrics.parquet"
support = pd.read_csv(support_path / "class_offering_support.csv")
flags = pd.read_csv(support_path / "cell_flags.csv")
boot = pd.read_csv(support_path / "offering_cluster_bootstrap_per_class.csv")
facts = pd.read_parquet(metrics_path)
keys = ["task", "window_id", "pipeline_id", "model_name", "seed", "eval_split", "phase_id"]
assert len(facts) == 1632 and not facts.duplicated(keys).any()
assert len(flags) == 1632 and not flags.duplicated(keys).any()
assert len(boot) == 4896 and not boot.duplicated(keys + ["class_code"]).any()
assert boot["bootstrap_replicates"].eq(2000).all()
assert boot["prediction_join"].eq("ONE_TO_ONE_LABELS_MATCH").all()
wide = facts[keys + ["c0_support", "c1_support", "c2_support"]].melt(
    id_vars=keys, var_name="class_code", value_name="facts_support")
wide["class_code"] = wide["class_code"].str.replace("_support", "", regex=False)
match = boot.merge(wide, on=keys + ["class_code"], how="outer", validate="one_to_one", indicator=True)
assert match["_merge"].eq("both").all()
assert match["support"].eq(match["facts_support"]).all(), "Bootstrap support differs from static-v2 facts"
support_keys = ["task", "window_id", "eval_split", "class_code"]
mapping = {"I/D": "c0", "G": "c1", "E": "c2"}
support["class_code"] = support["class_code"].replace(mapping)
joined = boot.merge(support, on=support_keys, how="left", validate="many_to_one", indicator=True)
assert joined["_merge"].eq("both").all() and joined["support"].eq(joined["n_support"]).all()
assert flags.merge(facts[keys], on=keys, how="outer", validate="one_to_one", indicator=True)["_merge"].eq("both").all()
assert support["single_offering_flag"].eq(support["n_offerings_with_class"].le(1)).all()
results = {"facts_cells": len(facts), "flag_cells": len(flags), "bootstrap_class_rows": len(boot),
           "support_rows": len(support), "bootstrap_support_equals_facts": True,
           "bootstrap_support_equals_offering_table": True, "flag_keys_equal_facts": True,
           "bootstrap_repetitions": 2000, "bootstrap_prediction_join": "ONE_TO_ONE_LABELS_MATCH",
           "ci_status_counts": boot["ci_status"].value_counts(dropna=False).to_dict(),
           "limitations": ["Existing post-hoc bootstrap, not an independent rerun.",
                           "Join status is verified as recorded in source facts, not rerun from predictions.",
                           "Single-offering confidence intervals are not estimable.",
                           "This package is not an official L2 ingest receipt."]}
DEST.mkdir(parents=True)
for task, source in [("CQ", "CQ/resuilt/m07_split_evidence_received_20261107"),
                     ("LO", "LO/resuilt/m07_split_evidence_received_20261107_r2")]:
    target = DEST / task / "L0_registry" / "M07_split_evidence"
    shutil.copytree(ROOT / source, target)
    with zipfile.ZipFile(ROOT / "LO/resuilt/m07_population_provenance_20261107T152138Z.zip") as archive:
        assert archive.testzip() is None
        for item in archive.infolist():
            name = Path(item.filename).name
            if name in {"summary.json", "processed_enrollments_files.json", f"{task}_labels_files.json", f"{task}_manifest_files.json"}:
                (target / f"population_{name}").write_bytes(archive.read(item))
    if task == "CQ":
        with zipfile.ZipFile(ROOT / "CQ/resuilt/m07_missing_label_population_20261107T153555Z.zip") as archive:
            assert archive.testzip() is None
            item = next(i for i in archive.infolist() if i.filename.endswith("summary.json"))
            (target / "cq_missing_label_population_summary.json").write_bytes(archive.read(item))
    (target / "README_delivery.md").write_text(
        f"# M-07 {task} — evidence delivery 2026-11-07\n\n"
        "Original split tables and original package checksums are retained. population_summary.json is from "
        "the completed CQ/LO enrollment-label audit; population_*_files.json inventories current sources. "
        "Manifest parquet files have SHA-256 in their inventories. The new SHA256_DELIVERY.txt covers every "
        "delivered file except itself.\n\n"
        + ("CQ missing-label reconstruction: all 8,614,884 IDs are proxy enrollments without an in-window "
           "video/problem/comment event, using currently available inputs including comment_v2. " if task == "CQ" else
           "LO split coverage includes A/T1/T2/T3 and a separate UNASSIGNED category. ")
        + "Results describe the selected cohort. Processed enrollment is not an independent raw source. "
        "Present-day hashes do not prove historical manifest identity without a prior reference. "
        "Source reconstruction does not prove historical inputs were identical.\n", encoding="utf-8")

target = DEST / "LO/L2_facts/M05_offering_support_bootstrap"
shutil.copytree(support_path, target)
(target / "reconciliation.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
(target / "README_delivery.md").write_text(
    "# M-05 LO — seed 42 reconciliation\n\n"
    "Static-v2 metrics: 1,632 unique cells. Bootstrap: 4,896 unique cell/class rows; all support counts "
    "match both the static-v2 fact export and the offering support table. All 1,632 flag keys match facts. "
    "The source records B=2,000 and ONE_TO_ONE_LABELS_MATCH. Reconciliation checks existing facts; it "
    "does not rerun the prediction join or bootstrap. Of 4,896 class rows, 544 are NOT_ESTIMABLE_SINGLE_OFFERING; "
    "4,352 use intervals conditional on class presence. Energy and official L2 ingest are outside this package.\n",
    encoding="utf-8")

for package in [DEST / "CQ/L0_registry/M07_split_evidence", DEST / "LO/L0_registry/M07_split_evidence", target]:
    lines = []
    for f in sorted(p for p in package.rglob("*") if p.is_file() and p.name != "SHA256_DELIVERY.txt"):
        h = hashlib.sha256()
        with f.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {f.relative_to(package).as_posix()}")
    (package / "SHA256_DELIVERY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"output": str(DEST), "M05_reconciliation": results}, ensure_ascii=False, indent=2))
