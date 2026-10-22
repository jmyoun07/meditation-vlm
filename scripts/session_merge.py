"""Validate a JSON array of in-session Claude codes and merge into the parquet."""
import json, sys
sys.path.insert(0, "src")
from meditation_vlm import config as cfg_mod, session_coding
cfg = cfg_mod.load_config("config/config.main.yaml")
objs = json.load(open(sys.argv[1]))
merged = session_coding.append_codes(cfg, objs)
pend = session_coding.pending(cfg)
print(f"[merge] +{len(objs)} total={len(merged)} pending={len(pend)}")
print("NEXT " + " ".join(t["video_id"] for t in pend[:12]))
