"""Build one coder prompt file per video for the in-session Claude rater.

Lives in scripts/ rather than a tmp scratchpad: the scratchpad is cleaned
periodically and this has already been lost mid-run twice.
"""
import sys, re, pathlib
sys.path.insert(0, "src")
from meditation_vlm import config as cfg_mod, session_coding
import pandas as pd

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
cfg = cfg_mod.load_config("config/config.main.yaml")
base = pathlib.Path("codebook/prompts/coding_v1.md").read_text()
EXTRA = """
ADDITIONAL RULES (study amendments)
- Frames are sampled every 5 s for the first 2 min, then every 30 s. Cadences
  faster than 6 bpm (first 2 min) or 1 bpm (after) are NOT resolvable from the
  frames. If the pacer's cadence is visibly faster than the frame sampling can
  resolve, set breathing_cadence_bpm to null and add the token
  "cadence_out_of_range" to the START of your evidence string.
- Only use that flag when a pacer actually exists; a countdown / session /
  hold / progress timer is NOT a pacer.
"""
meta = pd.read_parquet("data_main/02_eligible/eligible.parquet")
WORDLIKE = re.compile(r"[^\W_]", re.UNICODE)
tasks = {t["video_id"]: t for t in session_coding.pending(cfg)}

for vid in sys.argv[2:]:
    t = tasks[vid]
    tx = t["transcript_text"] or ""
    words = sum(1 for w in re.sub(r"\[\d+s\]", " ", tx).split() if WORDLIKE.search(w))
    warn = []
    if words < 10:
        warn.append("WARNING: this video's ASR transcript carries no real words "
                    "(punctuation/music markers only). Treat it as having no usable "
                    "speech; do not infer speech content from it.")
    row = meta[meta["video_id"] == vid]
    lang = row.iloc[0]["default_audio_language"] if len(row) else None
    if isinstance(lang, str) and lang and not lang.lower().startswith("en"):
        warn.append(f"WARNING: this video declares audio language '{lang}'. The "
                    "transcript may be a machine translation; rely on the frames for "
                    "visual codes and lower confidence on transcript-derived codes.")
    txt = tx if len(tx) <= 12000 else tx[:12000] + "\n[...transcript truncated...]"
    body = f"""{base}
{EXTRA}
{chr(10).join(warn)}

VIDEO_ID: {vid}

Read these frames IN ORDER with the Read tool (one pass, do not re-read):
{chr(10).join('- ' + f for f in t['frames'])}

TRANSCRIPT (timestamps in seconds):
{txt}

Work efficiently: read the frames once, then decide. Your FINAL message must be
ONE flat JSON object only (no prose, no code fence) with the keys from the
codebook plus "confidence" (an object of per-field 0-1 values) and "evidence"
(<=600 chars). Echo video_id exactly as "{vid}".
"""
    (OUT / f"{vid}.txt").write_text(body)
    print(vid, "words=", words, "warns=", len(warn), "frames=", len(t["frames"]))
