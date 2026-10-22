"""Computed (non-VLM) variables (codebook groups B, C, D).

Deterministic from transcript timestamps + metadata. Produced separately from VLM
codes and merged before analysis.
"""

from __future__ import annotations

import json
import re
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg_mod


_WORDLIKE = re.compile(r"[^\W_]", re.UNICODE)


def _real_words(segments: list[dict]) -> int:
    """Tokens carrying at least one letter or digit.

    ASR on a wordless video does not return nothing — it returns timed segments
    whose text is a bare "." Counting those as words makes a silent video look
    like a talkative one, so only word-like tokens count.
    """
    return sum(1 for s in segments
               for w in str(s.get("text", "")).split() if _WORDLIKE.search(w))


def silence_to_voice_ratio(segments: list[dict], duration_s: float) -> float | None:
    if not duration_s or duration_s <= 0:
        return None
    # No segments means no transcript, NOT a silent video. Returning 0 speech
    # here would score a third of the corpus as 100% silence and corrupt H2;
    # the value is missing, so say so.
    if not segments:
        return None
    # A transcript can exist and still carry no speech: on music-only or
    # wordless videos the ASR emits timed segments containing only punctuation.
    # Their timestamps would score the video as almost entirely *voiced* —
    # the opposite of the truth, and precisely in the high-silence tail H2 is
    # about. We cannot tell an ASR failure from a genuinely wordless video from
    # the transcript alone, and neither is measurable, so both are missing.
    if _real_words(segments) == 0:
        return None
    speech = sum(max(0.0, s["end"] - s["start"]) for s in segments)
    speech = min(speech, duration_s)
    return float(max(0.0, 1.0 - speech / duration_s))


def voice_pacing_wpm(segments: list[dict]) -> float | None:
    speech_min = sum(max(0.0, s["end"] - s["start"]) for s in segments) / 60.0
    if speech_min <= 0:
        return None
    words = _real_words(segments)
    if words == 0:
        return None
    return float(words / speech_min)


def _recency_days(published_at: str | None, extraction_date: str | None) -> int | None:
    if not published_at or not extraction_date:
        return None
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00")).date()
        ref = datetime.fromisoformat(extraction_date).date()
        return (ref - pub).days
    except Exception:
        return None


def _vpi(view_count, like_count, formula: str, weights: dict) -> float | None:
    if view_count is None:
        return None
    try:
        return eval(formula, {"__builtins__": {}}, {  # noqa: S307 - fixed config formula
            "log1p": math.log1p,
            "view_count": float(view_count or 0),
            "like_count": float(like_count or 0),
            "views_weight": float(weights.get("views_weight", 1.0)),
            "likes_weight": float(weights.get("likes_weight", 1.0)),
        })
    except Exception:
        return None


def run(cfg: dict) -> pd.DataFrame:
    eligible = pd.read_parquet(cfg_mod.data_path(cfg, "02_eligible", "eligible.parquet"))
    acfg = cfg["analysis"]
    ext_date = cfg.get("run", {}).get("extraction_date")

    rows = []
    for _, r in eligible.iterrows():
        vid = r["video_id"]
        tpath = cfg_mod.data_path(cfg, "03_transcripts", f"{vid}.json")
        segs, timing = [], None
        if Path(tpath).exists():
            data = json.loads(Path(tpath).read_text(encoding="utf-8"))
            segs = data.get("segments", [])
            timing = data.get("timing_source")
        dur_s = float(r["session_length_min"]) * 60.0 if pd.notna(r["session_length_min"]) else 0.0
        rows.append({
            "video_id": vid,
            "silence_to_voice_ratio": silence_to_voice_ratio(segs, dur_s),
            "voice_pacing_wpm": voice_pacing_wpm(segs),
            "timing_source": timing,
            "recency_days": _recency_days(r.get("published_at"), ext_date),
            "video_power_index": _vpi(r.get("view_count"), r.get("like_count"),
                                      acfg.get("vpi_formula", ""),
                                      acfg.get("vpi_weights", {})),
            "like_rate": r.get("like_rate"),
            "comment_rate": r.get("comment_rate"),
            "session_length_min": r.get("session_length_min"),
            "subscriber_count": r.get("subscriber_count"),
            "recency_published_at": r.get("published_at"),
            "channel_id": r.get("channel_id"),
        })
    df = pd.DataFrame(rows)
    out = cfg_mod.data_path(cfg, "05_derived", "derived.parquet")
    df.to_parquet(out, index=False)
    print(f"[derived] {len(df)} rows -> {out}")
    return df
