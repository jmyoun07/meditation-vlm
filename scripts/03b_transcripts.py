#!/usr/bin/env python3
"""Stage 3b: backfill transcripts via faster-whisper ASR for any eligible video
that lacks platform captions (e.g. when caption fetch is IP-blocked)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from meditation_vlm import config as cfg_mod  # noqa: E402
from meditation_vlm import extraction  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--model", default="base", help="faster-whisper model size")
    args = ap.parse_args()
    extraction.backfill_transcripts(cfg_mod.load_config(args.config), args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
