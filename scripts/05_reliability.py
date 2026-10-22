#!/usr/bin/env python3
"""Stage 5 runner: compute reliability (derived vars + agreement metrics)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from meditation_vlm import config as cfg_mod  # noqa: E402
from meditation_vlm import derived  # noqa: E402
from meditation_vlm import reliability  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    cfg = cfg_mod.load_config(args.config)
    derived.run(cfg)         # computed vars first (needed by analysis)
    reliability.run(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
