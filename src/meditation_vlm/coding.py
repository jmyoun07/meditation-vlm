"""Stage 4 — VLM coding (protocol: Data extraction and VLM coding).

Every eligible video with extracted frames+transcript is coded independently by
each configured model (>=2 for inter-model agreement). Additionally:
- a prompt-sensitivity pass re-codes with alternative prompt phrasings (RQ4),
- a test-retest subsample is re-coded by the same model under identical settings.

Each (model, prompt_variant, replicate) combination writes its own parquet so the
reliability stage can compute agreement without ambiguity. Output rows hold the
flattened schema fields plus provenance columns.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd

from . import config as cfg_mod
from . import vlm as vlm_mod

# How many transcript characters to include in the prompt.
_TRANSCRIPT_CHARS = 6000


def _load_transcript_text(path: str | None) -> str:
    if not path or not Path(path).exists():
        return "[no transcript available]"
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segs = data.get("segments", [])
    lines = [f"[{s['start']:.0f}s] {s['text'].strip()}" for s in segs]
    text = "\n".join(lines)
    return text[:_TRANSCRIPT_CHARS]


def _frame_paths(frames_dir: str | None) -> list[str]:
    if not frames_dir or not Path(frames_dir).exists():
        return []
    return [str(p) for p in sorted(Path(frames_dir).glob("frame_*.jpg"))]


def select_frames(frames_dir: str | None, max_n: int = 12) -> list[str]:
    """Opening-weighted subsample of frames, capped at max_n, so both VLMs see an
    identical, bounded set (keeps token cost + rate-limit pressure manageable)."""
    paths = _frame_paths(frames_dir)
    if len(paths) <= max_n:
        return paths
    head_n = max(1, max_n // 2)          # keep the dense opening frames
    head = paths[:head_n]
    tail = paths[head_n:]
    need = max_n - len(head)
    step = max(1, len(tail) // need)
    return head + tail[::step][:need]


def _build_user_text(video_id: str, transcript_text: str) -> str:
    return (f"video_id: {video_id}\n\n"
            f"TRANSCRIPT (timestamped excerpt):\n{transcript_text}\n\n"
            f"Frames follow in temporal order. Return the JSON object now.")


def _flatten(obj: dict, provenance: dict) -> dict:
    row = dict(provenance)
    for k, v in obj.items():
        if k == "confidence" and isinstance(v, dict):
            for ck, cv in v.items():
                row[f"conf_{ck}"] = cv
        else:
            row[k] = v
    # Join integrity: provenance keys (esp. video_id) are authoritative — models
    # sometimes mangle the echoed id (observed: Gemini drops characters).
    row.update(provenance)
    return row


def code_video(client, prompt, schema, video_id, frames, transcript_text) -> dict:
    user_text = _build_user_text(video_id, transcript_text)
    return client.complete_json(prompt, frames, user_text, schema)


def load_all_codes(cfg: dict) -> pd.DataFrame:
    """All coding rows: automated providers (codes_long) + in-session Claude
    (codes_session). The two files have separate writers to avoid races."""
    frames = []
    for name in ("codes_long.parquet", "codes_session.parquet"):
        p = cfg_mod.data_path(cfg, "04_coded", name)
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        raise FileNotFoundError("no coding output found under 04_coded/")
    return pd.concat(frames, ignore_index=True)


def coding_ready(cfg: dict) -> pd.DataFrame:
    """Manifest rows ready to code: frames extracted AND a transcript file on
    disk. Transcript paths are recomputed from video_id because the manifest
    checkpoint can be stale while the ASR backfill is running."""
    manifest = pd.read_parquet(cfg_mod.data_path(cfg, "03_extraction_manifest.parquet"))
    manifest = manifest[manifest["n_frames"] > 0].copy()
    tdir = cfg_mod.data_path(cfg, "03_transcripts", "_probe.json").parent
    manifest["transcript_path"] = manifest["video_id"].map(
        lambda v: str(tdir / f"{v}.json"))
    ready = manifest[manifest["transcript_path"].map(lambda p: Path(p).exists())]
    return ready


def run(cfg: dict) -> pd.DataFrame:
    schema = cfg_mod.load_schema()
    manifest = coding_ready(cfg)
    print(f"[code] coding-ready videos (frames + transcript): {len(manifest)}")

    ccfg = cfg["coding"]
    secrets = cfg["secrets"]
    primary_prompt = (cfg_mod.REPO_ROOT / ccfg["prompt_file"]).read_text(encoding="utf-8")

    # Only API models run in this automated stage. In-session providers (Claude
    # via Claude Code) are coded separately by session_coding.py and merged.
    api_models = [m for m in ccfg["models"]
                  if not vlm_mod.is_session_provider(m["provider"])]
    session_models = [m for m in ccfg["models"]
                      if vlm_mod.is_session_provider(m["provider"])]
    if session_models:
        print(f"[code] NOTE: {len(session_models)} in-session model(s) "
              f"({[m['model'] for m in session_models]}) are coded via Claude Code, "
              f"not here. Run session_coding after this stage.")
    if not api_models:
        print("[code] No API models configured; nothing to run in the automated stage.")
        return pd.DataFrame()

    # Build (model, prompt_variant) plan for API models.
    plan = []
    for m in api_models:
        plan.append({"provider": m["provider"], "model": m["model"],
                     "temperature": m.get("temperature", 0),
                     "prompt_path": ccfg["prompt_file"], "prompt": primary_prompt,
                     "variant": "v1"})
    # Prompt sensitivity: re-run the FIRST API model with each variant prompt.
    for i, vp in enumerate(ccfg.get("prompt_variants_for_sensitivity", []) or []):
        m = api_models[0]
        plan.append({"provider": m["provider"], "model": m["model"],
                     "temperature": m.get("temperature", 0),
                     "prompt_path": vp,
                     "prompt": (cfg_mod.REPO_ROOT / vp).read_text(encoding="utf-8"),
                     "variant": f"sens{i+1}"})

    # Test-retest subsample (replicate=2) for the first model, primary prompt.
    rng = random.Random(cfg.get("run", {}).get("random_seed", 0))
    ids = manifest["video_id"].tolist()
    frac = ccfg.get("test_retest_fraction", 0.0)
    retest_ids = set(rng.sample(ids, max(1, int(len(ids) * frac)))) if frac and ids else set()

    # Prompt-sensitivity subsample: the protocol re-extracts key variables under
    # alternative phrasings — a random subsample suffices (sens_fraction < 1
    # keeps quota-limited providers viable on the full run).
    sens_frac = float(ccfg.get("sens_fraction", 1.0))
    sens_ids = (set(rng.sample(ids, max(1, int(len(ids) * sens_frac))))
                if 0 < sens_frac < 1 and ids else set(ids))

    max_frames = int(ccfg.get("max_frames_per_call", 12))
    out = cfg_mod.data_path(cfg, "04_coded", "codes_long.parquet")

    # Resume: keep prior SUCCESSFUL rows; failed rows are retried this run.
    # A row's identity is (video_id, provider, model, prompt_variant, replicate).
    all_rows: list[dict] = []
    done: set[tuple] = set()
    if out.exists():
        prev = pd.read_parquet(out)
        ok = prev[prev["error"].isna()] if "error" in prev else prev
        all_rows = ok.to_dict("records")
        done = {(r["video_id"], r["provider"], r["model"],
                 r["prompt_variant"], r["replicate"]) for r in all_rows}
        if done:
            print(f"[code] resuming: {len(done)} rows already coded")

    checkpoint_every = int(ccfg.get("checkpoint_every", 10))
    quota_streak_abort = int(ccfg.get("quota_streak_abort", 5))
    new_since_ckpt = 0
    quota_streak = 0

    for spec in plan:
        client = vlm_mod.make_client(spec["provider"], spec["model"],
                                     spec["temperature"], secrets)
        replicates = [1]
        for _, mrow in manifest.iterrows():
            if quota_streak >= quota_streak_abort:
                break
            vid = mrow["video_id"]
            if spec["variant"].startswith("sens") and vid not in sens_ids:
                continue
            reps = [1, 2] if (vid in retest_ids and spec["variant"] == "v1"
                              and spec is plan[0]) else replicates
            todo_reps = [r for r in reps if (vid, spec["provider"], spec["model"],
                                             spec["variant"], r) not in done]
            if not todo_reps:
                continue
            frames = select_frames(mrow["frames_dir"], max_frames)
            transcript_text = _load_transcript_text(mrow["transcript_path"])
            for rep in todo_reps:
                prov = {"video_id": vid, "provider": spec["provider"],
                        "model": spec["model"], "prompt_variant": spec["variant"],
                        "replicate": rep}
                try:
                    obj = code_video(client, spec["prompt"], schema, vid,
                                     frames, transcript_text)
                    all_rows.append(_flatten(obj, prov))
                    quota_streak = 0
                except Exception as e:
                    all_rows.append({**prov, "error": str(e)})
                    if vlm_mod.is_quota_error(str(e)):
                        quota_streak += 1
                        print(f"[code] {client.name} {vid}: QUOTA/RATE ({quota_streak}/{quota_streak_abort})")
                    else:
                        print(f"[code] {client.name} {vid} rep{rep}: ERROR {e}")
                new_since_ckpt += 1
            if new_since_ckpt >= checkpoint_every:
                pd.DataFrame(all_rows).to_parquet(out, index=False)
                new_since_ckpt = 0
            print(f"[code] {client.name} {spec['variant']} {vid}: done")
        if quota_streak >= quota_streak_abort:
            print(f"[code] aborting: {quota_streak} consecutive quota errors — "
                  f"re-run after the usage window renews (progress saved).")
            break

    coded = pd.DataFrame(all_rows)
    coded.to_parquet(out, index=False)
    n_ok = int(coded["error"].isna().sum()) if "error" in coded else len(coded)
    print(f"[code] {len(coded)} rows ({n_ok} ok) -> {out}")
    return coded
