#!/bin/zsh
# The Codex (gpt-5.6-sol) coder runs on a ChatGPT Plus quota window, so stage 4
# aborts every time the window is exhausted. Restarting it by hand loses hours;
# this supervisor re-runs the stage on a backoff and stops on its own once every
# coding-ready video has a Codex row. Progress is checkpointed in the parquet,
# so each re-run resumes rather than recodes.
cd "/Users/saipe/claude code/youtube VLM" || exit 1
source .venv/bin/activate
LOG=data_main/codex_watcher.log

ok_rows() {
  python -c "
import pandas as pd, pathlib
p = pathlib.Path('data_main/04_coded/codes_long.parquet')
print(int(pd.read_parquet(p)['error'].isna().sum()) if p.exists() else 0)" 2>/dev/null
}

# The provider states a reset time in the error text it stores in the parquet.
# Honour it instead of guessing; cap at 36h so a bad parse cannot park forever.
retry_wait_seconds() {
  python - <<'PY' 2>/dev/null
import re, datetime as dt, pathlib
import pandas as pd
p = pathlib.Path('data_main/04_coded/codes_long.parquet')
if not p.exists():
    raise SystemExit
d = pd.read_parquet(p)
errs = d.loc[d['error'].notna(), 'error'].astype(str).tolist()
best = None
pat = re.compile(r'try again at ([A-Z][a-z]{2}) (\d{1,2})(?:st|nd|rd|th)?, (\d{4}) (\d{1,2}):(\d{2})\s*([AP]M)')
for e in errs:
    m = pat.search(e)
    if not m:
        continue
    mon, day, year, hh, mm, ap = m.groups()
    hh = int(hh) % 12 + (12 if ap == 'PM' else 0)
    try:
        t = dt.datetime.strptime(f'{mon} {day} {year} {hh}:{mm}', '%b %d %Y %H:%M')
    except ValueError:
        continue
    best = t if best is None else max(best, t)
if best is None:
    raise SystemExit
wait = int((best - dt.datetime.now()).total_seconds()) + 120
print(max(0, min(wait, 36 * 3600)))
PY
}

remaining() {
  python -c "
import sys; sys.path.insert(0, 'src')
import pandas as pd, pathlib
from meditation_vlm import config as cfg_mod, coding
cfg = cfg_mod.load_config('config/config.main.yaml')
ready = set(coding.coding_ready(cfg)['video_id'])
p = pathlib.Path('data_main/04_coded/codes_long.parquet')
done = set()
if p.exists():
    d = pd.read_parquet(p)
    done = set(d[d['error'].isna()]['video_id'])
print(len(ready - done))" 2>/dev/null
}

for i in $(seq 1 96); do
  before=$(ok_rows)
  echo "$(date '+%F %T') pass $i starting (ok rows=$before, remaining=$(remaining))" >> $LOG
  python -u scripts/04_code.py --config config/config.main.yaml >> data_main/codex_coding.log 2>&1
  after=$(ok_rows)
  left=$(remaining)
  echo "$(date '+%F %T') pass $i done: +$((after - before)) rows, remaining=$left" >> $LOG
  [ "$left" = "0" ] && { echo "$(date '+%F %T') DONE" >> $LOG; break; }
  if [ "$after" -le "$before" ]; then
    # No forward progress. The provider usually says exactly when the window
    # reopens ("try again at Sep 19th, 2026 6:32 PM") and that can be more than
    # a day out — a fixed 60-minute retry then burns ~30 pointless passes. Sleep
    # until the stated time when we can parse one; fall back to 60 minutes.
    wait_s=$(retry_wait_seconds)
    if [ -n "$wait_s" ] && [ "$wait_s" -gt 0 ]; then
      echo "$(date '+%F %T') blocked until provider reset; sleeping ${wait_s}s" >> $LOG
      sleep "$wait_s"
    else
      echo "$(date '+%F %T') no progress — no reset time given, sleeping 60m" >> $LOG
      sleep 3600
    fi
  else
    sleep 300
  fi
done
