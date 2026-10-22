#!/bin/zsh
# Option A: wait out the YouTube bot block. Probe every 45 min with a single
# metadata-only request; resume extraction only once the probe succeeds. Never
# hammers YouTube while blocked (that is what deepens a block).
cd "/Users/saipe/claude code/youtube VLM" || exit 1
source .venv/bin/activate
LOG=data_main/extract_watcher.log
PROBE_ID=dQw4w9WgXcQ
for i in $(seq 1 96); do
  ts=$(date '+%F %T')
  out=$(yt-dlp --skip-download --print id \
        --extractor-args "youtube:player_client=android" \
        "https://www.youtube.com/watch?v=$PROBE_ID" 2>&1)
  if print -r -- "$out" | grep -qi "not a bot\|Sign in to confirm"; then
    echo "$ts BLOCKED (probe) — sleeping 45m" >> $LOG
    sleep 2700
    continue
  fi
  echo "$ts PROBE OK — resuming extraction" >> $LOG
  python -u scripts/03_extract.py --config config/config.main.yaml >> data_main/extract.log 2>&1
  rc=$?
  echo "$(date '+%F %T') extraction exited rc=$rc" >> $LOG
  if tail -40 data_main/extract.log | grep -qi "not a bot\|Sign in to confirm"; then
    echo "$(date '+%F %T') re-BLOCKED during extraction — backing off 90m" >> $LOG
    sleep 5400
  else
    remaining=$(python -c "
import sys,glob,pandas as pd;sys.path.insert(0,'src')
e=pd.read_parquet('data_main/02_eligible/eligible.parquet')
have={p.split('/')[-1] for p in glob.glob('data_main/03_frames/*')}
print(len(set(e['video_id'])-have))" 2>/dev/null)
    echo "$(date '+%F %T') remaining without frames: $remaining" >> $LOG
    [ "$remaining" = "0" ] && { echo "DONE" >> $LOG; break; }
    sleep 600
  fi
done
