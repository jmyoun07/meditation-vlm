#!/usr/bin/env python3
"""Network-free smoke test for the pure-logic stages (derived, reliability,
analysis). Generates synthetic inputs that mimic the artifacts produced by
stages 1-4, then runs stages 5-6 and asserts outputs exist and are sane.

Run:  python tests/smoke_test.py
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from meditation_vlm import analysis, derived, reliability  # noqa: E402

TECHNIQUES = ["focused_attention_breath", "body_scan", "loving_kindness",
              "open_monitoring_mindfulness", "visualization_imagery",
              "yoga_nidra_body_relaxation", "movement_walking"]
SETTINGS = ["studio", "nature", "abstract_animated", "text_only"]
SOUNDS = ["none", "ambient_nature", "singing_bowls", "binaural_isochronic_tones", "music"]


def make_config(data_dir: Path) -> dict:
    return {
        "run": {"label": "smoke", "random_seed": 7, "extraction_date": "2026-01-15",
                "data_dir": str(data_dir)},
        "retrieval": {"target_eligible_n": 60},
        "reliability": {"agreement_threshold_alpha": 0.60,
                        "agreement_threshold_icc": 0.60},
        "analysis": {
            "primary_outcomes": ["like_rate", "comment_rate"],
            "secondary_outcomes": ["video_power_index"],
            "covariates": ["session_length_min", "subscriber_count",
                           "channel_type", "recency_days"],
            "random_effect": "channel_id",
            "fdr_method": "benjamini-hochberg",
            "vpi_formula": "views_weight*log1p(view_count) + likes_weight*log1p(like_count)",
            "vpi_weights": {"views_weight": 1.0, "likes_weight": 1.0},
        },
    }


def synth(cfg: dict, n: int = 60):
    rng = np.random.default_rng(7)
    dd = Path(cfg["run"]["data_dir"])
    (dd / "01_raw").mkdir(parents=True, exist_ok=True)

    elig_rows, coded_rows = [], []
    for i in range(n):
        vid = f"vid{i:03d}"
        # Independent random feature draws to avoid collinearity/separation.
        tech = TECHNIQUES[int(rng.integers(0, len(TECHNIQUES)))]
        has_breath = bool(rng.random() < 0.5)
        setting = SETTINGS[int(rng.integers(0, len(SETTINGS)))]
        sound = SOUNDS[int(rng.integers(0, len(SOUNDS)))]
        nature = bool(rng.random() < 0.5)
        posture = bool(rng.random() < 0.4)
        overlay = bool(rng.random() < 0.3)
        presenter = ["on_screen_presenter", "visuals_only_voiceover", "mixed"][
            int(rng.integers(0, 3))]
        congruence = ["concordant", "discordant", "not_applicable"][
            int(rng.integers(0, 3))]
        view_count = int(rng.integers(1000, 500000))
        # Engagement increases with breathing guide (H1-like signal) + noise.
        base = 0.02 + 0.01 * has_breath + 0.004 * nature + rng.normal(0, 0.004)
        like_rate = float(min(max(base, 0.001), 0.2))
        comment_rate = float(min(max(base / 4 + rng.normal(0, 0.001), 0.0005), 0.05))
        dur_min = float(rng.integers(3, 40))
        channel = f"ch{int(rng.integers(0, 40)):02d}"

        elig_rows.append({
            "video_id": vid, "channel_id": channel,
            "channel_type": "individual" if i % 3 else "organization",
            "session_length_min": dur_min,
            "subscriber_count": int(rng.integers(500, 2_000_000)),
            "published_at": f"2025-{int(rng.integers(1,13)):02d}-"
                            f"{int(rng.integers(1,28)):02d}T00:00:00Z",
            "view_count": view_count,
            "like_count": int(like_rate * view_count),
            "comment_count": int(comment_rate * view_count),
            "like_rate": like_rate, "comment_rate": comment_rate,
        })

        # Build a synthetic transcript (speech covering ~60-90% of duration).
        dur_s = dur_min * 60.0
        speech_frac = float(rng.uniform(0.55, 0.9))
        seg = {"start": 0.0, "end": dur_s * speech_frac,
               "text": "breathe in and out slowly relax " * 20}
        tpath = dd / "03_transcripts" / f"{vid}.json"
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text(json.dumps({"video_id": vid, "timing_source": "asr",
                                     "segments": [seg]}))

        # Two models that mostly agree (high reliability) on most fields.
        for model, jitter in [("claude-opus-4-8", 0.05), ("gpt-4o", 0.10)]:
            flip = rng.random() < jitter
            coded_rows.append({
                "video_id": vid, "provider": "anthropic" if "claude" in model else "openai",
                "model": model, "prompt_variant": "v1", "replicate": 1,
                "technique": tech,
                "visual_breathing_guide": has_breath if not flip else (not has_breath),
                "breathing_cadence_bpm": (float(rng.uniform(5, 7)) if has_breath else None),
                "visual_verbal_congruence": congruence,
                "presenter_visibility": presenter,
                "setting_imagery": setting,
                "nature_imagery_present": nature,
                "posture_or_mudra_shown": posture,
                "background_sound_type": sound,
                "onscreen_text_overlay": overlay,
                "error": None,
            })
        # Test-retest replicate + sensitivity variant for the first model.
        coded_rows.append({**coded_rows[-2], "replicate": 2})
        coded_rows.append({**coded_rows[-3], "prompt_variant": "sens1"})

    (dd / "02_eligible").mkdir(parents=True, exist_ok=True)
    (dd / "04_coded").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(elig_rows).to_parquet(dd / "02_eligible" / "eligible.parquet", index=False)
    pd.DataFrame(coded_rows).to_parquet(dd / "04_coded" / "codes_long.parquet", index=False)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        cfg = make_config(Path(td))
        synth(cfg, n=120)

        d = derived.run(cfg)
        assert {"silence_to_voice_ratio", "voice_pacing_wpm", "video_power_index"} <= set(d.columns)
        assert d["silence_to_voice_ratio"].between(0, 1).all()
        print(f"  derived: {len(d)} rows, silence ratio mean={d['silence_to_voice_ratio'].mean():.3f}")

        rep = reliability.run(cfg)
        assert "inter_model" in rep and "variable_flags" in rep
        im = rep["inter_model"]
        print(f"  reliability inter-model alpha (technique)={im.get('technique')}, "
              f"breathing_guide={im.get('visual_breathing_guide')}")

        res = analysis.run(cfg)
        assert res["n"] > 0
        assert res["rq2_n_terms"] > 0, "RQ2 produced no model terms"
        print(f"  analysis: N={res['n']}, RQ2 terms={res['rq2_n_terms']}, RQ3 terms={res['rq3_n_terms']}")

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
