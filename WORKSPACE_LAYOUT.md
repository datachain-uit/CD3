# Canonical workspace layout

Only these trees are active inputs to the current CQ/LO protocol:

```text
CQ/
  Feature_extraction/              # CQ feature, label and split builders
  resuilt/CQ/hybrid/               # current v1 views, audits, manifests, test prefixes
  imputation/                      # CQ-facing contracts/docs
  model/                           # CQ model-stage entrypoint notes
LO/
  Feature_extraction_LO/           # LO feature, label and split builders
  resuilt/LO/hybrid/               # current v1 views, audits, manifests, test prefixes
  imputation/
  model/

imputation_core/                   # shared imputation implementation
augmentation_core/                 # shared CDSMOTE/SASMOTE/RadiusSMOTE implementation
model/                             # shared RNN/LSTM/GRU/BiLSTM implementation
modal_jobs/                        # Modal job entrypoints
downloads/imputation/              # small locally downloaded manifests/facts only
tools/report_maintenance/          # one-off report refresh scripts
TEMPO-DQ-Framework/                # read-only algorithm reference
```

`resuilt/` at the workspace root was a legacy duplicate and is intentionally
not an active data root. Modal receives only the canonical `CQ/resuilt/...`
and `LO/resuilt/...` views. The raw `course*.csv/json` files remain at the
workspace root because legacy feature-extraction scripts may refer to them.
