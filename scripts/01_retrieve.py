#!/usr/bin/env python3
"""Stage 1 runner: retrieve guided meditation videos via YouTube Data API v3.

Usage:
    python scripts/01_retrieve.py [--config config/config.yaml]

Writes data/01_raw/videos.parquet and data/01_raw/retrieval_manifest.json.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meditation_vlm import config as cfg_mod  # noqa: E402
from meditation_vlm import retrieval  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="Path to config.yaml")
    args = ap.parse_args()

    cfg = cfg_mod.load_config(args.config)
    retrieval.run(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
