"""Stage 2 — Screening / eligibility (protocol: Eligibility criteria).

Two layers:
1. Deterministic metadata gates (duration window, public, not age-restricted,
   not live, audio-or-captions available). Cheap, exact, applied first.
2. VLM eligibility classifier on survivors, using only the thumbnail image plus
   title/description (no video download). Distinguishes a guided session from
   music-only or a lecture. Uses the first configured model.

A random subsample is flagged for human verification; the rule is meant to be
refined before the full run.
"""

from __future__ import annotations

import json
import random

import pandas as pd

from . import config as cfg_mod
from . import vlm as vlm_mod


def _deterministic_mask(df: pd.DataFrame, elig: dict) -> pd.Series:
    dmin = elig["duration_min_minutes"]
    dmax = elig["duration_max_minutes"]
    ok = df["session_length_min"].between(dmin, dmax, inclusive="both")
    if elig.get("require_public", True):
        ok &= df["privacy_status"].fillna("public").eq("public")
    if elig.get("exclude_age_restricted", True) and "made_for_kids" in df:
        ok &= ~df["made_for_kids"].fillna(False)
    if elig.get("exclude_live", True):
        ok &= df["live_broadcast"].fillna("none").eq("none")
    if elig.get("require_audio_or_captions", True):
        # All real videos have audio; captions optional. Keep as caption flag OR True.
        ok &= (df["closed_captions_available"].fillna(False) | True)
    return ok


def _eligibility_record(client, prompt, schema, row) -> dict:
    text = (f"video_id: {row['video_id']}\n"
            f"title: {row.get('title')}\n"
            f"channel: {row.get('channel_title')}\n"
            f"description: {row.get('description')}")
    images = [row["thumbnail_url"]] if row.get("thumbnail_url") else []
    return client.complete_json(prompt, images, text, schema)


# Lightweight schema for the eligibility classifier output.
_ELIG_SCHEMA = {
    "type": "object",
    "required": ["video_id", "include", "reason", "confidence"],
    "properties": {
        "video_id": {"type": "string"},
        "include": {"type": "boolean"},
        "reason": {"type": "string"},
        "likely_technique": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def run(cfg: dict) -> pd.DataFrame:
    elig = cfg_mod.load_eligibility()
    raw = pd.read_parquet(cfg_mod.data_path(cfg, "01_raw", "videos.parquet"))

    det = _deterministic_mask(raw, elig)
    survivors = raw[det].copy()
    survivors["passed_metadata_gate"] = True
    print(f"[screen] metadata gate: {det.sum()}/{len(raw)} survive")

    # VLM eligibility classifier model: an explicit `coding.screening_model`
    # override wins (e.g. keep free-tier Gemini for screening while coding uses
    # a quota-limited provider); otherwise the first non-session coding model.
    mcfg = cfg["coding"].get("screening_model")
    if not mcfg:
        api_models = [m for m in cfg["coding"]["models"]
                      if not vlm_mod.is_session_provider(m["provider"])]
        if not api_models:
            raise RuntimeError("Screening needs at least one API model (e.g. Gemini).")
        mcfg = api_models[0]
    client = vlm_mod.make_client(mcfg["provider"], mcfg["model"],
                                 mcfg.get("temperature", 0), cfg["secrets"])
    prompt = (cfg_mod.REPO_ROOT /
              cfg["coding"]["eligibility_prompt_file"]).read_text(encoding="utf-8")

    # Resume: previously judged rows (no classifier_error) are kept; errored or
    # unjudged rows are (re)tried. A streak of quota errors aborts the run so a
    # daily/free-tier quota isn't burned on doomed retries — re-run to continue.
    partial_path = cfg_mod.data_path(cfg, "02_eligible", "screening_partial.parquet")
    records: list[dict] = []
    done_ids: set[str] = set()
    if partial_path.exists():
        prev = pd.read_parquet(partial_path)
        ok_prev = prev[~prev["reason"].astype(str).str.startswith("classifier_error")]
        records = ok_prev.to_dict("records")
        done_ids = set(ok_prev["video_id"])
        if done_ids:
            print(f"[screen] resuming: {len(done_ids)} already judged")

    quota_streak = 0
    quota_streak_abort = 5
    new_since_ckpt = 0
    aborted = False
    for _, row in survivors.iterrows():
        if row["video_id"] in done_ids:
            continue
        if quota_streak >= quota_streak_abort:
            aborted = True
            break
        try:
            rec = _eligibility_record(client, prompt, _ELIG_SCHEMA, row)
            # Join integrity: NEVER trust the model-echoed id (Gemini drops
            # characters in ~5% of echoes) — the source row is authoritative.
            rec["video_id"] = row["video_id"]
            quota_streak = 0
        except Exception as e:  # keep the run resilient; mark for human review
            rec = {"video_id": row["video_id"], "include": True,
                   "reason": f"classifier_error: {e}", "confidence": 0.0,
                   "likely_technique": "unknown"}
            if vlm_mod.is_quota_error(str(e)):
                quota_streak += 1
        records.append(rec)
        new_since_ckpt += 1
        if new_since_ckpt >= 25:
            pd.DataFrame(records).to_parquet(partial_path, index=False)
            new_since_ckpt = 0
            print(f"[screen] progress: {len(records)}/{len(survivors)}")
    pd.DataFrame(records).to_parquet(partial_path, index=False)
    if aborted:
        print(f"[screen] aborting after {quota_streak} consecutive quota errors — "
              f"{len(records)} judged so far; re-run after the quota renews.")
    elig_df = pd.DataFrame(records)

    out = survivors.merge(elig_df, on="video_id", how="left", suffixes=("", "_vlm"))
    eligible = out[out["include"].fillna(False)].copy()

    # Incomplete screening (quota abort / partial coverage): don't emit a partial
    # eligible list that downstream stages could silently run on.
    n_judged = int((~out["reason"].astype(str).str.startswith("classifier_error")
                    & out["include"].notna()).sum())
    if aborted or n_judged < len(survivors):
        out.to_parquet(cfg_mod.data_path(cfg, "02_eligible", "screening_full.parquet"),
                       index=False)
        print(f"[screen] INCOMPLETE ({n_judged}/{len(survivors)} judged) — "
              f"eligible.parquet NOT written; re-run to continue.")
        return eligible

    # Random human-verification subsample.
    rng = random.Random(cfg.get("run", {}).get("random_seed", 0))
    frac = elig.get("human_subsample_fraction", 0.1)
    ids = out["video_id"].tolist()
    k = max(1, int(round(len(ids) * frac))) if ids else 0
    out["human_verify_subsample"] = out["video_id"].isin(rng.sample(ids, k)) if k else False

    # Optionally trim to target n (keep highest-confidence, then most-surfaced).
    target = cfg["retrieval"].get("target_eligible_n")
    if target and len(eligible) > target:
        eligible = (eligible
                    .sort_values(["confidence", "n_queries_surfaced"],
                                 ascending=[False, False])
                    .head(target))

    full_path = cfg_mod.data_path(cfg, "02_eligible", "screening_full.parquet")
    out.to_parquet(full_path, index=False)
    elig_path = cfg_mod.data_path(cfg, "02_eligible", "eligible.parquet")
    eligible.to_parquet(elig_path, index=False)

    summary = {
        "n_raw": int(len(raw)),
        "n_metadata_pass": int(det.sum()),
        "n_vlm_eligible": int(out["include"].fillna(False).sum()),
        "n_final_eligible": int(len(eligible)),
        "human_verify_n": int(out["human_verify_subsample"].sum()),
    }
    with open(cfg_mod.data_path(cfg, "02_eligible", "screening_summary.json"),
              "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[screen] eligible: {len(eligible)} -> {elig_path}")
    return eligible
