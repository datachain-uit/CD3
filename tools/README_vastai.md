# Portable VastAI execution

This directory contains the reproducible, Modal-free execution path for a
locked CQ or LO release. It does not contain data, credentials, SSH endpoints,
or prediction salts.

## Workflow

1. Build and download the compact immutable input tree on the workstation.

   ```powershell
   .\tools\download_cq_vastai_inputs.ps1
   .\tools\download_lo_vastai_inputs.ps1
   ```

2. Upload a chosen tree and the runner to a rented L4 host. The endpoint is
   explicit rather than stored in source.

   ```powershell
   .\tools\upload_vastai_cq.ps1 -HostName <host> -Port <port>
   .\tools\upload_vastai_lo.ps1 -HostName <host> -Port <port>
   ```

3. On the host, set `TEMPO_PREDICTION_SALT` from a private file/environment,
   then invoke `vastai_train_shared.py` or `vastai_run_family.sh`. Recurrent
   families use batch 2,048. PatchTST uses optimisation batch 2,048 as four
   512-row micro-batches (`--accumulation-steps 4`).

4. After all 51 window × pipeline cells for one family and seed finish, run
   `vastai_audit_shared.py`. It produces canonical leakage, sanity,
   checkpoint-selection, per-class, bootstrap, and STRICT/OVERLAP facts without
   retraining.

5. Download those facts and ingest them into L2 before using them in a claim.

## Energy provenance

`vastai_train_shared.py` attempts one-second NVML power sampling when
`nvidia-ml-py` is installed. The result is explicitly labelled
`NVML_POWER_SAMPLING_ESTIMATE`; it is never interchangeable with a hardware
total-energy counter. If NVML is unavailable, the manifest records
`NOT_MEASURED`. No energy or CO2e is inferred from runtime, RAM, or VRAM.
