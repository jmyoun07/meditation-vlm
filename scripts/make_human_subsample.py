#!/usr/bin/env python3
"""Draw the human-verification subsample registered in section 5.4.

The subsample is drawn with a fixed seed from the analytic corpus and is
given exactly the inputs the two models received: the same 12
opening-weighted frames, selected by the pipeline's own function, and the
same transcript text. Anything else would make the comparison a test of
different inputs rather than of different raters.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from meditation_vlm import config as cfg_mod          # noqa: E402
from meditation_vlm import analysis, coding           # noqa: E402

SEED = 20261018          # the date the subsample was drawn
OUT_DIR = ROOT / "human_coding"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.main.yaml")
    ap.add_argument("--n", type=int, default=100)
    args = ap.parse_args()

    cfg = cfg_mod.load_config(args.config)
    df = analysis.build_frame(cfg)
    manifest = cfg_mod.data_path(cfg, "", "03_extraction_manifest.parquet")
    import pandas as pd
    man = pd.read_parquet(manifest).set_index("video_id")

    pool = [v for v in df.video_id if v in man.index]
    sample = (pd.Series(sorted(pool))
              .sample(n=min(args.n, len(pool)), random_state=SEED)
              .tolist())

    items = []
    for vid in sample:
        row = man.loc[vid]
        frames = coding.select_frames(row["frames_dir"], 12)
        text = coding._load_transcript_text(row["transcript_path"])
        items.append({
            "video_id": vid,
            "frames": [str(pathlib.Path(f).relative_to(ROOT)) for f in frames],
            "transcript": text,
        })

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "subsample.json"
    out.write_text(json.dumps(
        {"seed": SEED, "n": len(items), "drawn_from": int(len(pool)),
         "items": items}, ensure_ascii=False, indent=1))
    nf = sorted({len(i["frames"]) for i in items})
    print(f"wrote {out}")
    print(f"  {len(items)} videos drawn from {len(pool)}, seed {SEED}")
    print(f"  frames per video: {nf}")
    print(f"  transcript chars: min {min(len(i['transcript']) for i in items)}, "
          f"max {max(len(i['transcript']) for i in items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
