"""In-session Claude coding bridge.

The chosen setup uses Claude Opus 4.8 as one of the two required VLM coders, run
*inside the Claude Code session* (on the user's Claude Max subscription) rather
than via the billed Anthropic API. Claude Code reads each video's sampled frames
and transcript and produces the same structured JSON as the API path; this module
validates those objects and merges them into codes_long.parquet as a distinct
rater (provider="anthropic", model="claude-opus-4-8", source="session").

Workflow:
    tasks = session_coding.pending(cfg)     # what to code (frames + transcript)
    # -> Claude Code inspects frames per task and builds a list of coded dicts
    session_coding.append_codes(cfg, coded) # validate + merge into the parquet
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config as cfg_mod
from . import vlm as vlm_mod
from .coding import _flatten, _load_transcript_text, coding_ready, select_frames

SESSION_PROVIDER = "anthropic"
SESSION_MODEL = "claude-opus-4-8"


def pending(cfg: dict) -> list[dict]:
    """Return coding tasks for the in-session Claude pass (frames + transcript
    both present), excluding videos already session-coded."""
    manifest = coding_ready(cfg)
    done: set[str] = set()
    sess = cfg_mod.data_path(cfg, "04_coded", "codes_session.parquet")
    if sess.exists():
        prev = pd.read_parquet(sess)
        done = set(prev[prev["prompt_variant"] == "v1"]["video_id"])
    max_frames = int(cfg.get("coding", {}).get("max_frames_per_call", 12))
    tasks = []
    for _, r in manifest.iterrows():
        if r["video_id"] in done:
            continue
        tasks.append({
            "video_id": r["video_id"],
            "frames": select_frames(r["frames_dir"], max_frames),
            "transcript_text": _load_transcript_text(r["transcript_path"]),
        })
    return tasks


def append_codes(cfg: dict, coded_objs: list[dict],
                 prompt_variant: str = "v1", replicate: int = 1) -> pd.DataFrame:
    """Validate coded dicts against the schema and merge into codes_long.parquet."""
    schema = cfg_mod.load_schema()
    rows = []
    for obj in coded_objs:
        errs = vlm_mod.validate(obj, schema)
        if errs:
            raise ValueError(f"{obj.get('video_id')}: schema errors: {errs[:3]}")
        prov = {"video_id": obj["video_id"], "provider": SESSION_PROVIDER,
                "model": SESSION_MODEL, "prompt_variant": prompt_variant,
                "replicate": replicate, "source": "session", "error": None}
        rows.append(_flatten(obj, prov))
    new = pd.DataFrame(rows)

    # Session codes live in their OWN parquet: the automated coding loop
    # checkpoints codes_long.parquet concurrently, and two writers on one file
    # would silently drop rows. Reliability/analysis concatenate both files.
    out = cfg_mod.data_path(cfg, "04_coded", "codes_session.parquet")
    if out.exists():
        existing = pd.read_parquet(out)
        # Drop any prior session rows for these videos to keep re-runs idempotent.
        mask = ~((existing["video_id"].isin(new["video_id"]))
                 & (existing["prompt_variant"] == prompt_variant)
                 & (existing["replicate"] == replicate))
        merged = pd.concat([existing[mask], new], ignore_index=True)
    else:
        merged = new
    merged.to_parquet(out, index=False)
    print(f"[session-coding] merged {len(new)} Claude rows -> {out} "
          f"(total {len(merged)} rows)")
    return merged


def write_tasks_json(cfg: dict) -> Path:
    """Dump pending tasks to JSON for reference/auditing."""
    tasks = pending(cfg)
    slim = [{"video_id": t["video_id"], "n_frames": len(t["frames"]),
             "frames": t["frames"]} for t in tasks]
    p = cfg_mod.data_path(cfg, "04_coded", "session_tasks.json")
    p.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    return p
