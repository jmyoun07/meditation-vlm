"""Stage 6 — Statistical analysis (protocol: Statistical analysis).

Builds the analytic frame (VLM consensus codes + computed vars + metadata), then:
- RQ1: descriptive distributions of techniques and features.
- RQ2: associations between meditation-specific features and engagement, adjusting
  for session length, channel size, channel type, recency; channel clustering via
  cluster-robust standard errors. Rates modeled with fractional logit
  (GLM Binomial, logit link).
- RQ3: technique x feature interactions (stratified moderation).
- FDR control (Benjamini-Hochberg) across the feature set; standardized effect
  sizes with CIs are reported rather than thresholds.

Low-reliability variables (from Stage 5) are excluded from confirmatory models.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as cfg_mod

CATEGORICAL = ["technique", "visual_verbal_congruence", "presenter_visibility",
               "setting_imagery", "background_sound_type"]
BINARY = ["visual_breathing_guide", "nature_imagery_present",
          "posture_or_mudra_shown", "onscreen_text_overlay"]
CONTINUOUS_VLM = ["breathing_cadence_bpm"]
CONTINUOUS_DERIVED = ["silence_to_voice_ratio", "voice_pacing_wpm"]


def _consensus(coded: pd.DataFrame) -> pd.DataFrame:
    """Majority vote (categorical/binary) and mean (continuous) across models."""
    base = coded[(coded["replicate"] == 1) & (coded["prompt_variant"] == "v1")].copy()
    if "error" in base:
        base = base[base["error"].isna()]
    agg = {}
    for c in CATEGORICAL + BINARY:
        if c in base:
            agg[c] = (c, lambda s: s.mode().iloc[0] if len(s.mode()) else None)
    for c in CONTINUOUS_VLM:
        if c in base:
            agg[c] = (c, "mean")
    out = base.groupby("video_id").agg(**agg).reset_index()
    return out


def load_all_codes_for_diagnostics(cfg: dict) -> pd.DataFrame:
    from .coding import load_all_codes
    return load_all_codes(cfg)


def build_frame(cfg: dict) -> pd.DataFrame:
    from .coding import load_all_codes
    coded = load_all_codes(cfg)
    derived = pd.read_parquet(cfg_mod.data_path(cfg, "05_derived", "derived.parquet"))
    consensus = _consensus(coded)
    df = consensus.merge(derived, on="video_id", how="inner")
    # Channel type may live in eligible metadata.
    elig = pd.read_parquet(cfg_mod.data_path(cfg, "02_eligible", "eligible.parquet"))
    cols = [c for c in ["video_id", "channel_type"] if c in elig.columns]
    if "channel_type" in elig.columns:
        df = df.merge(elig[cols], on="video_id", how="left")
    df["log_subscribers"] = np.log1p(df["subscriber_count"].fillna(0))
    return df


def _excluded_vars(cfg: dict) -> list[str]:
    path = cfg_mod.data_path(cfg, "05_reliability", "reliability_report.json")
    if not path.exists():
        return []
    rep = json.loads(path.read_text(encoding="utf-8"))
    # Both states keep a variable out of confirmatory models, for different
    # reasons: low_reliability = the models disagreed; not_assessable = the
    # agreement statistic is undefined (no variance, or too little rater
    # overlap). Reporting differs (§5.4) but neither is modellable.
    return (rep.get("low_reliability_excluded", [])
            + rep.get("not_assessable", []))


def rq1_descriptives(df: pd.DataFrame) -> dict:
    desc = {}
    for c in CATEGORICAL + BINARY:
        if c in df:
            desc[c] = df[c].value_counts(dropna=False).to_dict()
    for c in CONTINUOUS_VLM + CONTINUOUS_DERIVED:
        if c in df:
            desc[c] = {"mean": float(df[c].mean()), "sd": float(df[c].std()),
                       "n": int(df[c].notna().sum())}
    # Cadence is defined only where a pacer exists, but the consensus rule
    # resolves the pacer flag by mode and the cadence by mean, so a video can
    # carry a cadence while the consensus codes no pacer. Report the statistic
    # on the videos the consensus calls pacers, and report the median: the
    # distribution is strongly right-skewed, so the mean overstates the centre.
    if "breathing_cadence_bpm" in df and "visual_breathing_guide" in df:
        c, g = df["breathing_cadence_bpm"], df["visual_breathing_guide"]
        s_pacer = c[c.notna() & (g == True)]  # noqa: E712 - NA-safe
        desc["breathing_cadence_bpm"] = {
            "n_with_cadence": int(c.notna().sum()),
            "n_pacer_consensus": int(s_pacer.notna().sum()),
            "n_cadence_without_consensus_pacer": int((c.notna() & (g != True)).sum()),
            "median": float(s_pacer.median()), "q1": float(s_pacer.quantile(.25)),
            "q3": float(s_pacer.quantile(.75)), "mean": float(s_pacer.mean()),
            "sd": float(s_pacer.std()), "min": float(s_pacer.min()),
            "max": float(s_pacer.max()),
            "n_in_resonance_band_4_5_to_6_5": int(s_pacer.between(4.5, 6.5).sum()),
            "n_below_4_5": int((s_pacer < 4.5).sum()),
            "n_above_6_5": int((s_pacer > 6.5).sum()),
        }
    # Counts of each presentation feature within each technique. Written here
    # so the technique-by-feature figure can be rebuilt from the published
    # results alone: the analytic frame needs the run configuration, which
    # carries credentials and is not distributable.
    if "technique" in df:
        xt = {}
        for t, sub in df.groupby("technique"):
            cell = {"n": int(len(sub))}
            for c in BINARY:
                if c in sub:
                    cell[c] = int((sub[c] == True).sum())      # noqa: E712
            for c in CATEGORICAL:
                if c in sub and c != "technique":
                    cell[c] = {str(k): int(v) for k, v
                               in sub[c].value_counts().items()}
            xt[str(t)] = cell
        desc["technique_by_feature"] = xt
    return desc


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0.0


def _has_variance(s: pd.Series) -> bool:
    return s.notna().sum() >= 2 and float(s.std(skipna=True) or 0) > 0


def _cat_usable(s: pd.Series) -> bool:
    return s.dropna().nunique() >= 2


def _is_proportion(s: pd.Series) -> bool:
    """True when the outcome is a rate in [0, 1] and so belongs on the binomial
    (fractional-logit) family. `video_power_index` is a composite of logged
    counts on a 0-32 scale: filtering it to [0, 1] left 3 of 1,201 rows, which
    is a silent near-total sample loss, so it is fitted as a linear model
    instead."""
    v = pd.to_numeric(s, errors="coerce").dropna()
    return bool(len(v)) and float(v.min()) >= 0.0 and float(v.max()) <= 1.0


# Minimum support for a `technique x feature` interaction column to be
# estimable. Without it the interaction set produces quasi-separation
# artefacts: `setting_imagery[text_only] x technique[movement_walking]` holds a
# single video whose comment_rate is 0, which yielded beta = -14.66 with the
# smallest p value in the whole interaction table. Columns below the threshold
# are dropped and those videos contribute to the main effect instead.
MIN_INTERACTION_CELL = 10


def _prune_design(X: pd.DataFrame,
                  min_interaction_cell: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Drop constant and linearly dependent columns from a design matrix.

    `technique x feature` interactions generate a column for every cell, but
    several cells are structurally empty: `visual_breathing_guide` is True in
    only 2 of the 8 technique levels, so 6 of its interaction columns are all
    zero and others are exact aliases of a main effect. Statsmodels does not
    drop these, so the cluster covariance is singular and the whole model
    fails (observed: like_rate) or returns aliased coefficients that look
    estimated but are not (observed: comment_rate). Columns are tested in
    formula order so the intercept and main effects are kept and the
    unidentified interaction cells are the ones dropped.
    """
    keep: list[str] = []
    dropped: list[str] = []
    acc = np.empty((len(X), 0), dtype=float)
    rank = 0
    for col in X.columns:
        v = X[col].to_numpy(float)
        if col != "Intercept" and np.ptp(v) == 0.0:
            dropped.append(col)
            continue
        # Interaction columns are nonzero exactly on the cell they represent,
        # so the nonzero count is that cell's sample size.
        if (min_interaction_cell and ":" in col
                and int(np.count_nonzero(v)) < min_interaction_cell):
            dropped.append(col)
            continue
        trial = np.column_stack([acc, v])
        new_rank = int(np.linalg.matrix_rank(trial))
        if new_rank <= rank:
            dropped.append(col)
            continue
        acc, rank = trial, new_rank
        keep.append(col)
    return X[keep], dropped


def _fit_fractional_logit(df: pd.DataFrame, outcome: str, terms: list[str],
                          group: str, min_interaction_cell: int = 0):
    import patsy
    import statsmodels.api as sm

    work = df.copy()
    proportion = _is_proportion(work[outcome])
    if proportion:
        work = work[work[outcome].between(0, 1, inclusive="both")]
    work = work.dropna(subset=[outcome] + [t for t in terms if t in work])
    if len(work) < max(10, len(terms) + 3):
        return None, work
    formula = f"{outcome} ~ " + " + ".join(terms)
    try:
        family = (sm.families.Binomial() if proportion
                  else sm.families.Gaussian())
        if not proportion:
            print(f"[analysis] {outcome}: not a proportion "
                  f"(range {work[outcome].min():.2f}-{work[outcome].max():.2f}); "
                  f"fitted as a linear model, not fractional logit")
        y, X = patsy.dmatrices(formula, data=work, return_type="dataframe")
        # patsy drops its own NA rows; keep `work` aligned so the cluster
        # groups and the reported n refer to the rows actually modelled.
        work = work.loc[X.index]
        X, dropped = _prune_design(X, min_interaction_cell)
        if dropped:
            print(f"[analysis] {outcome}: dropped {len(dropped)} unidentified "
                  f"design column(s) (empty or aliased cells): "
                  f"{', '.join(dropped[:4])}"
                  f"{' ...' if len(dropped) > 4 else ''}")
        model = sm.GLM(y, X, family=family)
        n_params = model.exog.shape[1]
        n_clusters = work[group].nunique() if group in work else 0
        # Cluster-robust SEs need more clusters than parameters; otherwise the
        # cluster covariance is singular. This is expected on a small pilot, so
        # fall back to heteroskedasticity-robust (HC1) SEs and flag it.
        if n_clusters > n_params + 1:
            res = model.fit(cov_type="cluster", cov_kwds={"groups": work[group]})
            res._se_type = f"cluster({n_clusters})"
        else:
            res = model.fit(cov_type="HC1")
            res._se_type = "HC1_robust"
            print(f"[analysis] {outcome}: {n_clusters} clusters <= {n_params} params; "
                  f"using HC1 robust SEs (channel random effect needs the full sample).")
        # Set on both branches: a linear-model outcome reported as
        # `binomial_logit` would misstate the model in the results table.
        res._family = "binomial_logit" if proportion else "gaussian_identity"
        return res, work
    except Exception as e:
        print(f"[analysis] model failed for {outcome}: {e}")
        return None, work


# Minimum non-null share for a variable to enter the main model. The model
# drops rows listwise, so a structurally-missing variable silently destroys the
# sample: `breathing_cadence_bpm` is null wherever no on-screen pacer exists
# (2.8% coverage) and once cut the analytic frame from N=1,201 to N=34.
MIN_COVERAGE = 0.50

# `visual_verbal_congruence` is defined only when a visual breathing guide is
# present, so it is near-deterministically nested in the H1 feature (observed:
# 1,163 of 1,169 non-guide videos are "not_applicable"). Entering both in one
# model is a specification error; congruence is analysed inside the
# guide-present subsample instead (Amendment 3).
NESTED_IN_H1 = ["visual_verbal_congruence"]


def _feature_terms(df: pd.DataFrame, excluded: list[str]) -> list[str]:
    """Build model terms, skipping excluded, zero-variance, structurally-nested
    and sparsely-observed columns."""
    terms = []
    for c in BINARY + CATEGORICAL:
        if c == "technique" or c in excluded or c not in df:
            continue
        if c in NESTED_IN_H1:
            print(f"[analysis] {c}: nested in the H1 feature; excluded from "
                  f"the main model. The guide-present subsample model is not "
                  f"fitted: too few guide-present videos to carry it.")
            continue
        if _coverage_ok(df, c) and _cat_usable(df[c]):
            terms.append(f"C({c})")
    for c in CONTINUOUS_VLM + CONTINUOUS_DERIVED:
        if c in excluded or c not in df:
            continue
        if _coverage_ok(df, c) and _has_variance(df[c]):
            df[c + "_z"] = _zscore(df[c])
            terms.append(c + "_z")
    return terms


def _coverage_ok(df: pd.DataFrame, col: str) -> bool:
    cov = float(df[col].notna().mean())
    if cov < MIN_COVERAGE:
        print(f"[analysis] {col}: only {cov:.1%} observed (< {MIN_COVERAGE:.0%}); "
              f"excluded so listwise deletion cannot collapse the sample")
        return False
    return True


def _covariate_terms(df: pd.DataFrame) -> list[str]:
    terms = []
    for raw, z in [("session_length_min", "session_length_min_z"),
                   ("log_subscribers", "log_subscribers_z"),
                   ("recency_days", "recency_days_z")]:
        if raw in df and _has_variance(df[raw].astype(float)):
            df[z] = _zscore(df[raw].astype(float))
            terms.append(z)
    if "channel_type" in df and _cat_usable(df["channel_type"]):
        terms.append("C(channel_type)")
    return terms


def _in_fdr_family(term: str, cov_terms: list[str]) -> bool:
    """Is this term part of the preregistered multiplicity family?

    Section 5.3 controls the false discovery rate "across the feature set".
    Covariates and the technique main effects are nuisance parameters, not
    tested quantities, and correcting over them as well makes the family
    larger while adding p values smaller than the features' own, which pulls
    the features' q values down. The first implementation corrected over
    every term in the model and was anti-conservative for exactly that
    reason; see the correction dated 2026-10-18 in the registration record.
    """
    base = term.split(":")[0]
    for cov in cov_terms:
        if base == cov or term == cov:
            return False
        if cov.startswith("C(") and term.startswith(cov):
            return False
    if term.startswith("C(technique)") and ":" not in term:
        return False
    return True


def _tidy(res, outcome: str, fdr_method: str,
          cov_terms: list[str] | None = None) -> pd.DataFrame:
    import statsmodels.stats.multitest as mt
    params = res.params
    conf = res.conf_int()
    pvals = res.pvalues
    se_type = getattr(res, "_se_type", "model")
    cov_terms = cov_terms or []
    rows = []
    for name in params.index:
        if name == "Intercept":
            continue
        rows.append({"outcome": outcome, "term": name,
                     "family": getattr(res, "_family", "binomial_logit"),
                     "beta": float(params[name]),
                     "ci_low": float(conf.loc[name, 0]),
                     "ci_high": float(conf.loc[name, 1]),
                     "p": float(pvals[name]),
                     "se_type": se_type})
    tidy = pd.DataFrame(rows)
    if len(tidy):
        method = "fdr_bh" if "benjamini" in fdr_method.lower() else "bonferroni"
        tidy["in_fdr_family"] = tidy["term"].map(
            lambda t: _in_fdr_family(t, cov_terms))
        tidy["p_fdr"] = pd.NA
        fam = tidy["in_fdr_family"]
        if fam.any():
            tidy.loc[fam, "p_fdr"] = mt.multipletests(
                tidy.loc[fam, "p"], method=method)[1]
        tidy["p_fdr"] = pd.to_numeric(tidy["p_fdr"])
    return tidy


# --- H1: rare-event estimation (Preregistration Amendment 1, 2026-09-14) -----
# `visual_breathing_guide` is present in ~2.7% of the corpus. Ordinary ML at
# that prevalence is biased away from the null with unstable Wald SEs, so H1 is
# estimated with Firth penalized likelihood and profile-likelihood CIs. The
# unpenalized estimate is still reported, as the amendment commits to.
H1_FEATURE = "visual_breathing_guide"


def _h1_design(df: pd.DataFrame, outcome: str, cov_terms: list[str]):
    """Return (X, y, names, work) for the H1 model, or None if not estimable."""
    import patsy

    if H1_FEATURE not in df:
        return None
    terms = [f"C({H1_FEATURE})"] + cov_terms
    formula = f"{outcome} ~ " + " + ".join(terms)
    work = df[df[outcome].between(0, 1, inclusive="both")].copy()
    try:
        y, X = patsy.dmatrices(formula, work, return_type="dataframe")
    except Exception as e:
        print(f"[analysis] H1 design failed for {outcome}: {e}")
        return None
    if X.shape[0] < 20:
        return None
    return X.to_numpy(float), y.to_numpy(float).ravel(), list(X.columns), work


def rq_h1_firth(df: pd.DataFrame, outcomes: list[str],
                cov_terms: list[str]) -> pd.DataFrame:
    from . import firth as firth_mod

    rows = []
    for outcome in outcomes:
        if outcome not in df:
            continue
        built = _h1_design(df, outcome, cov_terms)
        if built is None:
            continue
        X, y, names, work = built
        idxs = [i for i, n in enumerate(names) if H1_FEATURE in n]
        if not idxs:
            continue
        beta, cov, converged = firth_mod.fit(X, y)
        for i in idxs:
            lo, hi = firth_mod.profile_ci(X, y, beta, cov, i)
            rows.append({
                "outcome": outcome, "term": names[i], "estimator": "firth",
                "beta": float(beta[i]), "ci_low": float(lo), "ci_high": float(hi),
                "ci_type": "profile_likelihood", "converged": bool(converged),
                "n": int(X.shape[0]),
                "n_feature_positive": int(work[H1_FEATURE].fillna(False).astype(bool).sum()),
                "prevalence": float(work[H1_FEATURE].fillna(False).astype(bool).mean()),
            })
    return pd.DataFrame(rows)


# --- Consensus-rule diagnostics (reviewer-prompted, 2026-10-20) --------------
# Two models give two codes per video. `_consensus` takes the mode for
# categorical/binary variables; with exactly two raters a disagreement has no
# majority, and pandas returns the sort-first value, so boolean ties always
# resolve to False. Prevalence is therefore a lower bound, and the rule must be
# shown not to drive the findings. This writes, per variable, how often the
# tie-break fired, and refits each FDR-surviving binary feature on the videos
# where the two models agreed outright.
# --- Average marginal effects (reviewer-prompted, 2026-10-20) ---------------
# A logit coefficient is not a quantity a reader can act on, and the relative
# changes quoted in the text were previously written by hand rather than
# computed. This derives them from the fitted model so the manuscript audit can
# check them: for each binary feature, the mean predicted outcome with the
# feature set off and on across the whole modelled frame, their difference in
# percentage points, and the relative change.
def marginal_effects(df: pd.DataFrame, outcome: str, feat_terms: list[str],
                     cov_terms: list[str], group: str) -> pd.DataFrame:
    import numpy as np
    import patsy

    res, work = _fit_fractional_logit(df, outcome, feat_terms + cov_terms,
                                      group)
    if res is None:
        return pd.DataFrame()
    formula = f"{outcome} ~ " + " + ".join(feat_terms + cov_terms)
    _y, X = patsy.dmatrices(formula, work, return_type="dataframe")
    beta = res.params.reindex(X.columns).to_numpy(float)
    rows = []
    for col in X.columns:
        binary = "[T.True]" in col
        # Standardized covariates are read per 1 SD; everything else is a
        # level contrast this summary does not try to reduce to one number.
        continuous = col.endswith("_z")
        if not (binary or continuous):
            continue
        x0, x1 = X.copy(), X.copy()
        if binary:
            x0[col], x1[col] = 0.0, 1.0
        else:
            x1[col] = x1[col] + 1.0
        p0 = float((1 / (1 + np.exp(-(x0.to_numpy(float) @ beta)))).mean())
        p1 = float((1 / (1 + np.exp(-(x1.to_numpy(float) @ beta)))).mean())
        rows.append({
            "outcome": outcome, "term": col, "n": int(res.nobs),
            "contrast": "present vs absent" if binary else "per +1 SD",
            "beta": round(float(res.params[col]), 6),
            "pred_off": round(p0, 6), "pred_on": round(p1, 6),
            "abs_change_pp": round(100 * (p1 - p0), 3),
            "rel_change_pct": round(100 * (p1 / p0 - 1), 1),
        })
    return pd.DataFrame(rows)


def consensus_sensitivity(cfg: dict, df: pd.DataFrame, coded: pd.DataFrame,
                          feat_terms: list[str], cov_terms: list[str],
                          outcomes: list[str], group: str) -> pd.DataFrame:
    base = coded[(coded["replicate"] == 1) & (coded["prompt_variant"] == "v1")]
    rows = []
    for v in CATEGORICAL + BINARY:
        if v not in base or v not in df:
            continue
        per = base[base[v].notna()].groupby("video_id")[v].nunique()
        n_dis = int((per > 1).sum())
        rec = {"variable": v, "n_videos": int(len(per)), "n_disagreed": n_dis,
               "pct_disagreed": round(100 * n_dis / max(1, len(per)), 2)}
        if v in BINARY:
            either = base.groupby("video_id")[v].apply(lambda s: (s == True).any())  # noqa: E712
            rec["n_positive_consensus"] = int((df[v] == True).sum())  # noqa: E712
            rec["n_positive_either_model"] = int(either.sum())
        rows.append(rec)
    # The sensitivity refit restricts to videos where the two models agreed on
    # EVERY feature entering the model, not merely on the feature being read
    # off. A per-feature restriction would leave the other regressors carrying
    # tie-broken values, which is the thing being tested.
    entering = [v for v in CATEGORICAL + BINARY
                if any(v in t for t in feat_terms)]
    complete = None
    for v in entering:
        ok = set(base[base[v].notna()].groupby("video_id")[v]
                 .nunique().pipe(lambda s: s[s == 1].index))
        complete = ok if complete is None else (complete & ok)
    complete = complete or set()
    sub = df[df["video_id"].isin(complete)]
    for rec in rows:
        rec["entered_model"] = rec["variable"] in entering
        rec["n_videos_complete_agreement"] = len(complete)
    for outcome in outcomes:
        if outcome not in df or not len(sub):
            continue
        res, _w = _fit_fractional_logit(sub, outcome, feat_terms + cov_terms,
                                        group)
        if res is None:
            continue
        for rec in rows:
            name = next((n for n in res.params.index
                         if rec["variable"] in n), None)
            if name is None:
                continue
            ci = res.conf_int().loc[name]
            rec[f"{outcome}_agree_only_n"] = int(res.nobs)
            rec[f"{outcome}_agree_only_beta"] = round(float(res.params[name]), 4)
            rec[f"{outcome}_agree_only_ci_low"] = round(float(ci[0]), 4)
            rec[f"{outcome}_agree_only_ci_high"] = round(float(ci[1]), 4)
            rec[f"{outcome}_agree_only_p"] = float(res.pvalues[name])
    return pd.DataFrame(rows)


def run(cfg: dict) -> dict:
    acfg = cfg["analysis"]
    df = build_frame(cfg)
    excluded = _excluded_vars(cfg)
    print(f"[analysis] N={len(df)}; excluded low-reliability vars: {excluded}")

    results = {"n": int(len(df)), "excluded_low_reliability": excluded}

    # RQ1
    rq1 = rq1_descriptives(df)
    with open(cfg_mod.data_path(cfg, "06_results", "rq1_descriptives.json"),
              "w", encoding="utf-8") as fh:
        json.dump(rq1, fh, indent=2, default=str)
    results["rq1"] = rq1

    feat_terms = _feature_terms(df, excluded)
    cov_terms = _covariate_terms(df)
    group = acfg.get("random_effect", "channel_id")
    fdr = acfg.get("fdr_method", "benjamini-hochberg")

    # RQ2 — main associations per outcome.
    rq2_all = []
    for outcome in acfg.get("primary_outcomes", []) + acfg.get("secondary_outcomes", []):
        if outcome not in df:
            continue
        terms = feat_terms + cov_terms
        res, work = _fit_fractional_logit(df, outcome, terms, group)
        n_used = len(work)
        if n_used < 0.5 * len(df):
            print(f"[analysis] WARNING {outcome}: modelled on {n_used}/{len(df)} "
                  f"rows — listwise deletion is dropping half the sample")
        if res is not None:
            tidy = _tidy(res, outcome, fdr, cov_terms)
            tidy["model"] = "rq2_main"
            tidy["n_modelled"] = n_used
            rq2_all.append(tidy)
    rq2_df = pd.concat(rq2_all, ignore_index=True) if rq2_all else pd.DataFrame()
    if len(rq2_df):
        rq2_df.to_csv(cfg_mod.data_path(cfg, "06_results", "rq2_associations.csv"),
                      index=False)
    results["rq2_n_terms"] = int(len(rq2_df))

    # RQ3 — technique x feature interactions (primary outcomes only).
    rq3_all = []
    if "technique" in df and "technique" not in excluded and df["technique"].nunique() > 1:
        for outcome in acfg.get("primary_outcomes", []):
            if outcome not in df:
                continue
            # Interact the headline feature (H1) with technique, plus main effects.
            inter_feats = [t for t in feat_terms]
            inter_terms = []
            for f in inter_feats:
                inter_terms.append(f"{f}:C(technique)")
            terms = ["C(technique)"] + feat_terms + cov_terms + inter_terms
            res, _ = _fit_fractional_logit(
                df, outcome, terms, group,
                min_interaction_cell=MIN_INTERACTION_CELL)
            if res is not None:
                tidy = _tidy(res, outcome, fdr, cov_terms)
                tidy["model"] = "rq3_interaction"
                rq3_all.append(tidy)
    # H1 — Firth penalized estimate (Amendment 1). Reported alongside the
    # unpenalized RQ2 term for the same feature, which stays in rq2_df.
    h1_df = pd.DataFrame()
    if H1_FEATURE not in excluded:
        outcomes = acfg.get("primary_outcomes", []) + acfg.get("secondary_outcomes", [])
        h1_df = rq_h1_firth(df, outcomes, cov_terms)
        if len(h1_df):
            h1_df.to_csv(cfg_mod.data_path(cfg, "06_results", "h1_firth.csv"),
                         index=False)
            prev = float(h1_df["prevalence"].iloc[0])
            npos = int(h1_df["n_feature_positive"].iloc[0])
            print(f"[analysis] H1 Firth: {len(h1_df)} terms; "
                  f"{H1_FEATURE} positive in {npos} videos ({prev:.1%})")
    results["h1_n_terms"] = int(len(h1_df))
    results["h1_prevalence"] = (float(h1_df["prevalence"].iloc[0])
                                if len(h1_df) else None)

    rq3_df = pd.concat(rq3_all, ignore_index=True) if rq3_all else pd.DataFrame()
    if len(rq3_df):
        rq3_df.to_csv(cfg_mod.data_path(cfg, "06_results", "rq3_interactions.csv"),
                      index=False)
    results["rq3_n_terms"] = int(len(rq3_df))

    # Average marginal effects for the binary features, per primary outcome.
    me = pd.concat([marginal_effects(df, o, feat_terms, cov_terms, group)
                    for o in acfg.get("primary_outcomes", []) if o in df],
                   ignore_index=True)
    if len(me):
        me.to_csv(cfg_mod.data_path(cfg, "06_results",
                                    "marginal_effects.csv"), index=False)

    # Consensus-rule diagnostics + agreement-only sensitivity.
    cs = consensus_sensitivity(
        cfg, df, load_all_codes_for_diagnostics(cfg), feat_terms, cov_terms,
        acfg.get("primary_outcomes", []), group)
    if len(cs):
        cs.to_csv(cfg_mod.data_path(cfg, "06_results",
                                    "consensus_sensitivity.csv"), index=False)
        results["consensus_max_pct_disagreed"] = float(cs["pct_disagreed"].max())

    with open(cfg_mod.data_path(cfg, "06_results", "analysis_summary.json"),
              "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"[analysis] RQ2 terms={results['rq2_n_terms']}, RQ3 terms={results['rq3_n_terms']}")
    print(f"[analysis] results -> {cfg_mod.data_path(cfg, '06_results')}")
    return results
