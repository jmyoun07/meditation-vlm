#!/usr/bin/env python3
"""Validate the human coding export and write it where Stage 5 expects it.

The human rows must line up with the model rows in both vocabulary and
dtype: Krippendorff alpha compares values, so a boolean coded as the string
"true" would read as disagreement with every True the models recorded.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from meditation_vlm import config as cfg_mod          # noqa: E402

BOOLS = ["visual_breathing_guide", "nature_imagery_present",
         "posture_or_mudra_shown"]
ENUMS = {
    "technique": ["focused_attention_breath", "body_scan", "loving_kindness",
                  "open_monitoring_mindfulness", "visualization_imagery",
                  "yoga_nidra_body_relaxation", "movement_walking", "other"],
    "visual_verbal_congruence": ["concordant", "discordant", "not_applicable"],
    "presenter_visibility": ["on_screen_presenter", "visuals_only_voiceover",
                             "mixed"],
    "setting_imagery": ["studio", "nature", "abstract_animated", "text_only",
                        "other"],
}
FIELDS = list(ENUMS) + BOOLS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.main.yaml")
    ap.add_argument("--input", default="human_coding/human_codes.json")
    ap.add_argument("--min-complete", type=int, default=50)
    args = ap.parse_args()
    import pandas as pd

    src = ROOT / args.input
    if not src.exists():
        print(f"no export at {src}\n"
              f"Open human_coding/rate.html, code the subsample, press "
              f"내보내기, and save the file to that path.")
        return 1
    payload = json.loads(src.read_text())
    rows = payload["rows"] if isinstance(payload, dict) else payload
    drawn = json.loads((ROOT / "human_coding/subsample.json").read_text())
    expected = {i["video_id"] for i in drawn["items"]}

    problems, clean = [], []
    for r in rows:
        vid = r.get("video_id")
        if vid not in expected:
            problems.append(f"{vid}: not in the drawn subsample")
            continue
        missing = [f for f in FIELDS if r.get(f) in (None, "")]
        if missing:
            continue                      # simply not coded yet
        out = {"video_id": vid}
        for f, allowed in ENUMS.items():
            if r[f] not in allowed:
                problems.append(f"{vid}.{f}: '{r[f]}' is not a codebook value")
            out[f] = r[f]
        for f in BOOLS:
            if str(r[f]).lower() not in ("true", "false"):
                problems.append(f"{vid}.{f}: '{r[f]}' is not true/false")
            out[f] = str(r[f]).lower() == "true"
        clean.append(out)

    if problems:
        print(f"{len(problems)} problem(s); nothing written:")
        for p in problems[:20]:
            print("  -", p)
        return 1
    if len(clean) < args.min_complete:
        print(f"only {len(clean)} of {len(expected)} videos are fully coded; "
              f"at least {args.min_complete} are needed for a usable alpha.\n"
              f"Keep going, or re-run with --min-complete to override.")
        return 1

    df = pd.DataFrame(clean)
    for f in BOOLS:
        df[f] = df[f].astype(bool)        # match the model rows exactly
    out = cfg_mod.data_path(cfg_mod.load_config(args.config), "06_human",
                            "human_codes.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"wrote {out}")
    print(f"  {len(df)} of {len(expected)} drawn videos fully coded")
    for f in FIELDS:
        vc = df[f].value_counts().to_dict()
        print(f"  {f:28s} {vc}")
    print("\nnext: python scripts/05_reliability.py --config "
          f"{args.config}, then rebuild the manuscript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
