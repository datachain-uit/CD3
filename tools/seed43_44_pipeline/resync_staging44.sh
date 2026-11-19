#!/bin/bash
RC="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn"
for T in CQ LO; do t=$(echo $T | tr A-Z a-z); for n in ${t}_f1_recurrent_v0_v16_full_facts_seed44_20261118 ${t}_patchtst_v0_v16_full_facts_seed44_20261119 ${t}_mantis_v2_v0_v16_full_facts_seed44_20261119; do
  $RC sync gdrive:$T/L2_facts/fact_exports/$n gdrive:$T/L2_facts/staging_incoming/$n --transfers 4 -q
  $RC check gdrive:$T/L2_facts/fact_exports/$n gdrive:$T/L2_facts/staging_incoming/$n >/dev/null 2>&1; echo "$n check rc $?"
done; done; echo RESYNC_DONE
