cd /workspace/CD3
echo "gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader|head -1) free=$(df -h /workspace|tail -1|awk '{print $4}')"
ps -eo etime,args | grep -E "[r]un_mantis_cq_grid|[v]astai_train_shared|[c]hain_after_lo|[c]hain2|[c]hain44016|[c]hain37939|[q]_v5family|[m]antis_single_nogate|[r]un_mantis_v2" | sed -E "s/--(data-root|work-root|output-root|static-layout-policy|run-purpose|workers|accumulation-steps|augmentation-seed-policy|energy-[a-z-]+|batch-size|max-epochs|patience|seed|model-name|task|micro-batch-size) [^ ]+//g" | cut -c1-110 | sort -u | head -5
for f in $(ls -t *.log 2>/dev/null | grep -v "err.log\|disk\|refit" | head -3); do
  age=$(( ( $(date +%s) - $(stat -c %Y $f) ) / 60 ))
  [ $age -gt 180 ] && continue
  echo " LOG $f age=${age}m: $(grep -aE '^(TRAIN_STARTED|TRAIN_COMPLETE|CACHE_VERIFIED|RESULTS_READY|BUNDLE_READY|INSUFFICIENT|CHAIN|LO_|MANTIS|QUEUE|V9|V14|REFIT|ADAPTER|SYNTH|DATA_TIMEOUT)' $f | tail -1 | cut -c1-100)"
  grep -a '"event": "epoch_complete"' $f | tail -1 | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l);print('   epoch',d.get('window'),d.get('pipeline'),d.get('epoch'),'f1',round(d.get('validation_macro_f1_mean_p1_p4',0),3))" 2>/dev/null
  grep -aE "epoch [0-9]+ best" $f | tail -1 | cut -c1-80
done
ls mantis_cq_V*_20261108/state/FAILED runs/*/FAILED 2>/dev/null | head -3
