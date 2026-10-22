"""Stage 5 — Reliability & validity (protocol: Reliability and validity).

Replaces clinician scoring with reproducibility evidence:
- Inter-model agreement: >=2 models, Krippendorff's alpha (categorical/nominal,
  ordinal) or ICC (continuous), per variable.
- Test-retest: same model, replicate 1 vs 2.
- Prompt sensitivity: primary prompt (v1) vs reworded variants.
- Human verification: VLM consensus vs trained-rater codes (if provided).

Variables below the configured threshold are flagged low-reliability and excluded
from confirmatory models downstream.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as cfg_mod

# Variable -> measurement level for choosing the metric.
NOMINAL = ["technique", "visual_verbal_congruence", "presenter_visibility",
           "setting_imagery", "background_sound_type"]
BINARY = ["visual_breathing_guide", "nature_imagery_present",
          "posture_or_mudra_shown", "onscreen_text_overlay"]
CONTINUOUS = ["breathing_cadence_bpm"]


def _krippendorff_alpha(matrix: list[list], level: str) -> float | None:
    """matrix: list of unit-vectors (one per rater) with possible None values."""
    try:
        import krippendorff
    except Exception:
        return None
    # krippendorff expects reliability_data as raters x units, np.nan for missing.
    arr = np.array(matrix, dtype=object)
    # Encode categoricals to integers.
    if level in ("nominal", "ordinal"):
        cats = sorted({v for row in matrix for v in row if v is not None and not _isnan(v)})
        code = {c: i for i, c in enumerate(cats)}
        data = [[code.get(v, np.nan) if (v is not None and not _isnan(v)) else np.nan
                 for v in row] for row in matrix]
    else:
        data = [[float(v) if (v is not None and not _isnan(v)) else np.nan
                 for v in row] for row in matrix]
    try:
        return float(krippendorff.alpha(reliability_data=data,
                                        level_of_measurement=level))
    except Exception:
        return None


def _isnan(v) -> bool:
    try:
        return bool(np.isnan(v))
    except (TypeError, ValueError):
        return False


def _icc(long_df: pd.DataFrame, target: str, rater: str, value: str) -> float | None:
    try:
        import pingouin as pg
    except Exception:
        return None
    sub = long_df[[target, rater, value]].dropna()
    if sub[rater].nunique() < 2 or sub[target].nunique() < 2:
        return None
    try:
        res = pg.intraclass_corr(data=sub, targets=target, raters=rater,
                                 ratings=value)
        # ICC2 = two-way random, absolute agreement.
        row = res[res["Type"] == "ICC2"]
        return float(row["ICC"].iloc[0]) if len(row) else None
    except Exception:
        return None


def _agreement_for_subset(df: pd.DataFrame, rater_col: str) -> dict:
    """Compute per-variable agreement across the levels of rater_col."""
    out = {}
    raters = sorted(df[rater_col].unique())
    pivoted = {}
    for var in NOMINAL + BINARY + CONTINUOUS:
        if var not in df.columns:
            continue
        # Build units x raters table aligned on video_id.
        wide = df.pivot_table(index="video_id", columns=rater_col, values=var,
                              aggfunc="first")
        matrix = [wide[r].tolist() for r in raters if r in wide.columns]
        if len(matrix) < 2:
            out[var] = None
            continue
        if var in CONTINUOUS:
            long = wide.reset_index().melt(id_vars="video_id",
                                           var_name="rater", value_name="val")
            out[var] = _icc(long, "video_id", "rater", "val")
        else:
            level = "nominal"
            out[var] = _krippendorff_alpha(matrix, level)
    return out


def run(cfg: dict) -> dict:
    from .coding import load_all_codes
    coded = load_all_codes(cfg)
    coded = coded[coded.get("error").isna()] if "error" in coded else coded

    report = {}

    # 1. Inter-model agreement: replicate==1, prompt v1, across providers/models.
    inter = coded[(coded["replicate"] == 1) & (coded["prompt_variant"] == "v1")].copy()
    inter["rater"] = inter["provider"] + ":" + inter["model"]
    report["inter_model"] = _agreement_for_subset(inter, "rater")

    # 2. Test-retest: first model, v1, replicate 1 vs 2.
    if (coded["replicate"] == 2).any():
        first = coded.sort_values("replicate")
        m0 = coded.iloc[0]["model"]
        rt = coded[(coded["model"] == m0) & (coded["prompt_variant"] == "v1")].copy()
        rt["rater"] = "rep" + rt["replicate"].astype(str)
        report["test_retest"] = _agreement_for_subset(rt, "rater")
    else:
        report["test_retest"] = {}

    # 3. Prompt sensitivity: first model, v1 vs sens* variants.
    sens = coded[coded["prompt_variant"].str.startswith(("v1", "sens"))].copy()
    if sens["prompt_variant"].nunique() > 1:
        m0 = coded.iloc[0]["model"]
        sens = sens[sens["model"] == m0]
        sens["rater"] = sens["prompt_variant"]
        report["prompt_sensitivity"] = _agreement_for_subset(sens, "rater")
    else:
        report["prompt_sensitivity"] = {}

    # 4. Human verification (optional): data/06_human/human_codes.parquet
    human_path = cfg_mod.data_path(cfg, "06_human", "human_codes.parquet")
    if human_path.exists():
        human = pd.read_parquet(human_path)
        # consensus VLM (mode across models) vs human, treated as two raters.
        consensus = (inter.groupby("video_id")[NOMINAL + BINARY]
                     .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
                     .reset_index())
        consensus["rater"] = "vlm_consensus"
        human["rater"] = "human"
        merged = pd.concat([consensus, human], ignore_index=True)
        report["human_agreement"] = _agreement_for_subset(merged, "rater")
    else:
        report["human_agreement"] = {"note": "no human_codes.parquet provided"}

    # Flag variables from inter-model agreement. Per the preregistration (§5.4)
    # we distinguish three states:
    #   reliable        — agreement computed and >= threshold
    #   low_reliability — agreement computed and < threshold (excluded from
    #                     confirmatory models)
    #   not_assessable  — agreement undefined because the variable had (near-)no
    #                     variance in this sample; reported as underpowered, NOT
    #                     as unreliable. (The analysis stage's zero-variance
    #                     guard drops these from models mechanically.)
    a_thr = cfg["reliability"]["agreement_threshold_alpha"]
    i_thr = cfg["reliability"]["agreement_threshold_icc"]
    flags = {}
    for var, val in report["inter_model"].items():
        thr = i_thr if var in CONTINUOUS else a_thr
        if var in inter.columns:
            n_levels = inter[var].dropna().nunique()
        else:
            n_levels = 0
        n_obs = int(inter[var].notna().sum()) if var in inter.columns else 0
        if val is None:
            # Agreement is UNDEFINED, not low. Two distinct causes, both of
            # which mean "underpowered", never "the models disagreed":
            #   no_variance          — every unit got the same value
            #   insufficient_overlap — too few units where both raters answered
            #                          (e.g. breathing_cadence_bpm is null
            #                          whenever no on-screen pacer exists)
            status = "not_assessable"
            reason = "no_variance" if n_levels < 2 else "insufficient_overlap"
        elif val >= thr:
            status, reason = "reliable", None
        else:
            status, reason = "low_reliability", None
        flags[var] = {"value": val, "status": status, "reason": reason,
                      "n_levels_observed": int(n_levels),
                      "n_observations": n_obs,
                      "reliable": status == "reliable"}
    report["low_reliability_excluded"] = [v for v, f in flags.items()
                                          if f["status"] == "low_reliability"]
    report["not_assessable"] = [v for v, f in flags.items()
                                if f["status"] == "not_assessable"]
    # Back-compat key; kept narrow to its literal meaning.
    report["not_assessable_no_variance"] = [
        v for v, f in flags.items() if f.get("reason") == "no_variance"]
    report["variable_flags"] = flags

    out = cfg_mod.data_path(cfg, "05_reliability", "reliability_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"[reliability] report -> {out}")
    print(f"[reliability] low-reliability (excluded): {report['low_reliability_excluded']}")
    print(f"[reliability] not assessable: "
          f"{[(v, flags[v]['reason']) for v in report['not_assessable']]}")
    return report
