"""Configuration loading with environment-variable interpolation.

Reads config/config.yaml (falls back to config.example.yaml is NOT done — the
example is a template only). Any string value of the form ``${VAR}`` is replaced
by the environment variable ``VAR`` at load time, so secrets need never be
written to disk.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

# Repo root = two levels up from this file (src/meditation_vlm/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
CODEBOOK_DIR = REPO_ROOT / "codebook"


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ${VAR} with os.environ[VAR] (empty string if unset)."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(path: str | Path | None = None) -> dict:
    """Load the active config, interpolating env vars.

    Order of precedence for secrets: explicit value in config.yaml, then env var
    (via ${VAR}), then the ``secrets`` block, then os.environ by conventional name.
    """
    cfg_path = Path(path) if path else CONFIG_DIR / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"{cfg_path} not found. Copy config/config.example.yaml to "
            f"config/config.yaml and fill it in."
        )
    cfg = _interpolate_env(load_yaml(cfg_path))

    # Convenience: fall back to conventional env vars for keys.
    secrets = cfg.setdefault("secrets", {})
    secrets.setdefault("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
    secrets.setdefault("google_api_key", os.environ.get("GOOGLE_API_KEY", ""))
    secrets.setdefault("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

    retrieval = cfg.setdefault("retrieval", {})
    if not retrieval.get("youtube_api_key"):
        retrieval["youtube_api_key"] = os.environ.get("YOUTUBE_API_KEY", "")

    return cfg


def load_seed_queries() -> dict:
    return load_yaml(CONFIG_DIR / "seed_queries.yaml")


def load_eligibility() -> dict:
    return load_yaml(CONFIG_DIR / "eligibility.yaml")


def load_schema() -> dict:
    import json

    with open(CODEBOOK_DIR / "schema.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def data_path(cfg: dict, *parts: str) -> Path:
    """Resolve a path under the configured data directory, creating parents."""
    base = REPO_ROOT / cfg.get("run", {}).get("data_dir", "data")
    p = base.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
