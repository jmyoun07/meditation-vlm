#!/usr/bin/env python3
"""Write the analytic dataset the Data Availability statement promises.

Video identifiers, the codes, and the derived measures the reported models
use. No title, description, transcript, thumbnail, or frame is included, so
nothing of the original video or audio is redistributed.
"""
from __future__ import annotations
import argparse, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from meditation_vlm import config as cfg_mod, analysis   # noqa: E402

# Everything the reported models read, and nothing that carries content.
COLUMNS = [
    "video_id", "channel_id",
    "technique", "visual_breathing_guide", "breathing_cadence_bpm",
    "visual_verbal_congruence", "presenter_visibility", "setting_imagery",
    "nature_imagery_present", "posture_or_mudra_shown",
    "background_sound_type", "onscreen_text_overlay",
    "silence_to_voice_ratio", "voice_pacing_wpm", "timing_source",
    "session_length_min", "subscriber_count", "recency_days",
    "like_rate", "comment_rate", "video_power_index",
]
WITHHELD = ("title", "description", "transcript", "thumbnail_url",
            "frames_dir", "transcript_path", "channel_title")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.main.yaml")
    args = ap.parse_args()
    df = analysis.build_frame(cfg_mod.load_config(args.config))

    leaked = [c for c in df.columns if c in WITHHELD]
    if leaked:
        print(f"refusing to write: content columns present {leaked}")
        return 1
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        print(f"refusing to write: expected columns absent {missing}")
        return 1

    out = ROOT / "data_main/07_share/analytic_dataset.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df[COLUMNS].to_csv(out, index=False)
    print(f"wrote {out}")
    print(f"  {len(df):,} videos x {len(COLUMNS)} columns, "
          f"{out.stat().st_size/1024:.0f} KB")
    print(f"  withheld: {', '.join(WITHHELD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
