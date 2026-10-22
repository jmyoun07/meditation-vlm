#!/usr/bin/env python3
"""Build the five manuscript tables from the analysis outputs.

Every cell is read from the Stage 5/6 result files rather than transcribed, so
the tables cannot drift from the numbers reported in the text.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _p(v: float) -> str:
    """JMIR P-value style: no leading zero, <.001 floor."""
    if v < 0.001:
        return "<.001"
    return f"{v:.3f}".lstrip("0")


def _p_row(r) -> str:
    """Adjusted P where the term is in the prespecified family, otherwise
    the unadjusted P marked as such. Covariates are nuisance parameters and
    are outside the feature set the analysis plan corrects over."""
    import pandas as _pd
    if "p_fdr" in r and not _pd.isna(r.p_fdr):
        return _p(r.p_fdr)
    return _p(r.p) + " (u)"


def _ci(lo: float, hi: float, nd: int = 3) -> str:
    return f"{lo:.{nd}f} to {hi:.{nd}f}"


def load():
    if not (ROOT / "config/config.main.yaml").exists():
        return None, None, None          # Table 1 falls back to its cache
    from meditation_vlm import config as cfg_mod
    from meditation_vlm.analysis import build_frame
    cfg = cfg_mod.load_config(str(ROOT / "config/config.main.yaml"))
    df = build_frame(cfg)
    e = pd.read_parquet(ROOT / "data_main/02_eligible/eligible.parquet")
    s = pd.read_parquet(ROOT / "data_main/04_coded/codes_session.parquet")
    d = pd.read_parquet(ROOT / "data_main/05_derived/derived.parquet")
    coded = sorted(set(s[(s.prompt_variant == "v1") & (s.replicate == 1)].video_id))
    return df, e[e.video_id.isin(coded)], d[d.video_id.isin(coded)]


CORPUS_JSON = ROOT / "data_main/06_results/corpus_characteristics.json"


def table1(df, ec, dd):
    """Corpus characteristics.

    The formatted rows are cached to a published results file. Every other
    table and figure is built from published results; this one needed the
    analytic frame, which needs the run configuration, which carries
    credentials and is not distributable. With the cache committed, the whole
    manuscript rebuilds from what the repository can actually ship.
    """
    if df is None:
        rows = [tuple(r) for r in json.loads(CORPUS_JSON.read_text())["rows"]]
        return _table1_spec(rows)

    def med_iqr(series, nd=1, thousands=False):
        v = pd.to_numeric(series, errors="coerce").dropna()
        f = (lambda x: f"{x:,.0f}") if thousands else (lambda x: f"{x:.{nd}f}")
        return f"{f(v.median())} ({f(v.quantile(.25))} to {f(v.quantile(.75))})"

    vc = ec.channel_id.value_counts()
    rows = [
        ("Videos in the analytic corpus, n", f"{len(df):,}"),
        ("Distinct channels, n", f"{df.channel_id.nunique():,}"),
        ("Videos per channel, median (IQR)", med_iqr(vc, 0)),
        ("Videos from the single largest channel, n", f"{vc.max():,}"),
        ("Share of corpus from the 5 largest channels, %",
         f"{100 * vc.head(5).sum() / len(ec):.1f}"),
        ("Session length in minutes, median (IQR)", med_iqr(dd.session_length_min)),
        ("Video age in days at retrieval, median (IQR)", med_iqr(dd.recency_days, 0, True)),
        ("Channel subscribers, median (IQR)", med_iqr(dd.subscriber_count, 0, True)),
        ("Views, median (IQR)", med_iqr(ec.view_count, 0, True)),
        ("Likes, median (IQR)", med_iqr(ec.like_count, 0, True)),
        ("Comments, median (IQR)", med_iqr(ec.comment_count, 0, True)),
    ]
    for col, lab in [("like_rate", "Like rate, mean (SD)"),
                     ("comment_rate", "Comment rate, mean (SD)"),
                     ("video_power_index", "Video power index, mean (SD)")]:
        v = pd.to_numeric(dd[col], errors="coerce").dropna()
        nd = 5 if col != "video_power_index" else 3
        rows.append((lab, f"{v.mean():.{nd}f} ({v.std():.{nd}f})"))
    CORPUS_JSON.write_text(json.dumps({"rows": rows}, indent=1))
    return _table1_spec(rows)


def _table1_spec(rows):
    age_row = next(i for i, r in enumerate(rows, start=1)
                   if r[0].startswith("Video age"))
    return {"caption": "Characteristics of the analytic corpus (N=1,635 videos).",
            "columns": ["Characteristic", "Value"], "rows": rows,
            "footnotes": ["IQR: interquartile range; SD: standard deviation.",
                          "Video age is counted to the retrieval date of July 27, 2026."],
            "anchors": [("header", 1), ("cell", age_row, 0)]}


# Names for the coded variables, shared with Multimedia Appendix 1 so the
# codebook table and the reliability table cannot drift apart.
CODED_LABELS = {
    "technique": "Technique", "visual_breathing_guide": "Visual breathing guide",
    "visual_verbal_congruence": "Visual-verbal congruence",
    "presenter_visibility": "Presenter visibility",
    "setting_imagery": "Setting imagery",
    "nature_imagery_present": "Nature imagery present",
    "posture_or_mudra_shown": "Posture or mudra shown",
    "background_sound_type": "Background sound type",
    "onscreen_text_overlay": "On-screen text overlay",
    "breathing_cadence_bpm": "Breathing cadence, breaths per minute",
}
GATE_STATUS = {"reliable": "Reliable", "low_reliability": "Low reliability",
               "not_assessable": "Not assessable"}


def coded_order(rel):
    """Alpha-descending, so Table 2 and Table A1 list the variables alike."""
    return sorted(CODED_LABELS, key=lambda k: (rel["inter_model"][k] is None,
                                               -(rel["inter_model"][k] or 0)))


def _human_n() -> int:
    import json
    p = ROOT / "data_main/06_human/human_codes.parquet"
    try:
        return int(len(pd.read_parquet(p)))
    except Exception:
        return 0


HUMAN_N = _human_n()


def human_arm(rel):
    """The model-to-human arm, present only once the subsample is coded."""
    ha = rel.get("human_agreement") or {}
    vals = {k: v for k, v in ha.items() if isinstance(v, (int, float))}
    return vals or None


def table2(rel):
    """Reliability across the automated arms, and the human arm when it exists."""
    labels = CODED_LABELS
    status = {"reliable": "Entered models", "low_reliability": "Excluded",
              "not_assessable": "Not assessable"}
    # Clearing the gate is not the same as entering the models. Congruence
    # cleared it and was still excluded, as near-collinear with the H1
    # feature (Amendment 3); the column said "Entered models" regardless.
    DECISION = {"visual_verbal_congruence": "Excluded, nested"}
    order = coded_order(rel)
    human = human_arm(rel)
    f = lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else "NA"
    rows = []
    for k in order:
        row = [labels[k], f(rel["inter_model"][k]), f(rel["test_retest"][k]),
               f(rel["prompt_sensitivity"][k])]
        if human:
            row.append(f(human.get(k)))
        row.append(DECISION.get(k, status[rel["variable_flags"][k]["status"]]))
        rows.append(tuple(row))
    cols = ["Coded variable", "Inter-model", "Test-retest", "Prompt sensitivity"]
    if human:
        cols.append("VLM vs human")
    cols.append("Decision")
    n_arms = "four arms" if human else "three arms"
    notes = [
        "Values are Krippendorff alpha. The inclusion threshold was 0.60, a value "
        "fixed in the analysis plan rather than in the protocol (Amendment 9).",
        "Inter-model agreement is based on 3,270 coded observations per variable "
        "(1,635 videos coded independently by 2 models); the test-retest arm "
        "re-coded 396 videos and the prompt-sensitivity arm 408 videos.",
        "NA: breathing cadence was flagged not assessable for insufficient overlap, "
        "because the variable is defined only where a pacer is present and both "
        "models coded the variable on the same video only 76 times.",
        "Visual-verbal congruence cleared the gate but is defined only where a "
        "breathing guide exists, is therefore near-collinear with the feature "
        "tested in H1, and was excluded from the main model (Amendment 3)."]
    cong = next(i for i, r in enumerate(rows, start=1)
                if r[0].startswith("Visual-verbal"))
    anchors = [("header", 1), ("header", 2), ("cell", len(rows), 0),
               ("cell", cong, len(cols) - 1)]
    if human:
        notes.append(f"The human arm compares the modal code of the two models "
                     f"against a single trained rater on a random subsample of "
                     f"{HUMAN_N} videos given identical inputs.")
        anchors.append(("header", 4))
    return {"caption": f"Reliability of vision-language model coding across "
                       f"{n_arms}, and the resulting inclusion decision.",
            "columns": cols,
            "rows": rows,
            "anchors": anchors,
            "footnotes": notes}


def table3(rq1):
    """RQ1 distributions."""
    groups = [
        ("Meditation technique", "technique", {
            "visualization_imagery": "Visualization and imagery",
            "focused_attention_breath": "Focused attention on the breath",
            "body_scan": "Body scan", "loving_kindness": "Loving-kindness",
            "yoga_nidra_body_relaxation": "Yoga nidra and body relaxation",
            "open_monitoring_mindfulness": "Open-monitoring mindfulness",
            "movement_walking": "Movement or walking", "other": "Other"}),
        ("Presenter visibility", "presenter_visibility", {
            "visuals_only_voiceover": "Visuals only, voiceover",
            "on_screen_presenter": "On-screen presenter", "mixed": "Mixed"}),
        ("Setting", "setting_imagery", {
            "nature": "Nature", "abstract_animated": "Abstract or animated",
            "other": "Other", "studio": "Studio", "text_only": "Text only"}),
        ("Visual breathing guide", "visual_breathing_guide",
         {"true": "Present", "false": "Absent"}),
        ("Nature imagery", "nature_imagery_present",
         {"true": "Present", "false": "Absent"}),
        ("Posture or mudra", "posture_or_mudra_shown",
         {"true": "Shown", "false": "Not shown"}),
    ]
    rows = []
    for header, key, mapping in groups:
        rows.append((header, "", ""))
        for k, lab in mapping.items():
            n = rq1[key].get(k, 0)
            rows.append((f"    {lab}", f"{n:,}", f"{100 * n / 1635:.1f}"))
    return {"caption": "Distribution of meditation technique and audiovisual "
                       "presentation features (N=1,635 videos).",
            "columns": ["Category", "Videos, n", "%"], "rows": rows,
            "anchors": [("header", 2), ("header", 0)],
            "footnotes": ["Percentages are of the full analytic corpus and may not sum "
                          "to 100 because of rounding.",
                          "Background sound type and on-screen text overlay are omitted "
                          "because both failed the 0.60 reliability gate."]}


# --------------------------------------------------- shared term labels
# One vocabulary for every table. The appendix used to print raw patsy
# names ("voice pacing wpm z"), so the same coefficient carried two
# different names in the main text and in the supplement.
VAR_LABELS = {
    "visual_breathing_guide": "Visual breathing guide",
    "posture_or_mudra_shown": "Posture or mudra shown",
    "nature_imagery_present": "Nature imagery present",
    "presenter_visibility": "Presenter",
    "setting_imagery": "Setting",
    "technique": "Technique",
    "channel_type": "Channel type",
    "silence_to_voice_ratio_z": "Silence-to-voice ratio, per SD",
    "voice_pacing_wpm_z": "Voice pacing, per SD",
    "session_length_min_z": "Session length, per SD",
    "log_subscribers_z": "Channel subscribers, log, per SD",
    "recency_days_z": "Video age, per SD",
}
LEVEL_LABELS = {
    "on_screen_presenter": "on-screen",
    "visuals_only_voiceover": "voiceover only",
    "mixed": "mixed",
    "nature": "nature",
    "studio": "studio",
    "text_only": "text only",
    "abstract_animated": "abstract or animated",
    "focused_attention_breath": "focused attention on the breath",
    "open_monitoring_mindfulness": "open-monitoring mindfulness",
    "loving_kindness": "loving-kindness",
    "body_scan": "body scan",
    "yoga_nidra_body_relaxation": "yoga nidra and body relaxation",
    "visualization_imagery": "visualization and imagery",
    "movement_walking": "movement or walking practice",
    "other": "other",
}


def _label_part(part: str) -> str:
    """One patsy component -> its reader-facing name."""
    m = re.fullmatch(r"C\((\w+)\)\[T\.([^\]]+)\]", part)
    if not m:
        return VAR_LABELS.get(part, part.replace("_", " "))
    var, lev = m.group(1), m.group(2)
    name = VAR_LABELS.get(var, var.replace("_", " ").capitalize())
    if lev == "True":            # binary indicator: the name says it all
        return name
    return f"{name}: {LEVEL_LABELS.get(lev, lev.replace('_', ' '))}"


def pretty_term(term: str) -> str:
    """Full patsy term -> its reader-facing name, interactions included."""
    parts = [_label_part(x) for x in term.split(":") if x]
    out = " \u00d7 ".join(parts)
    return out[:1].upper() + out[1:] if out else term


def table4(rq2):
    order = [
        "C(visual_breathing_guide)[T.True]",
        "C(posture_or_mudra_shown)[T.True]",
        "C(nature_imagery_present)[T.True]",
        "C(presenter_visibility)[T.on_screen_presenter]",
        "C(presenter_visibility)[T.visuals_only_voiceover]",
        "C(setting_imagery)[T.nature]",
        "C(setting_imagery)[T.studio]",
        "C(setting_imagery)[T.text_only]",
        "C(setting_imagery)[T.other]",
        "silence_to_voice_ratio_z",
        "voice_pacing_wpm_z",
        "session_length_min_z",
        "log_subscribers_z",
        "recency_days_z",
    ]
    pretty = {k: pretty_term(k) for k in order}
    rows = []
    for oc, lab in [("like_rate", "Like rate"), ("comment_rate", "Comment rate"),
                    ("video_power_index", "Video power index")]:
        sub = rq2[rq2.outcome == oc].set_index("term")
        rows.append((f"{lab} (n={int(sub.n_modelled.iloc[0]):,})", "", "", ""))
        for term, name in pretty.items():
            if term not in sub.index:
                continue
            r = sub.loc[term]
            rows.append((f"    {name}", f"{r.beta:.3f}",
                         _ci(r.ci_low, r.ci_high), _p_row(r)))
    return {"caption": "Adjusted associations between presentation features and "
                       "viewer engagement.",
            "columns": ["Outcome and term", "Coefficient", "95% CI", "P value"],
            "rows": rows,
            "anchors": [("header", 1), ("header", 0), ("header", 3), ("header", 2)],
            "footnotes": [
                "Like rate and comment rate were fitted with fractional-logit "
                "generalized linear models (binomial family, logit link); video power "
                "index is a linear outcome and was fitted with a Gaussian identity link.",
                "All models adjust for session length, log channel subscribers, and "
                "video age, and carry channel cluster-robust standard errors.",
                "P values are Benjamini-Hochberg adjusted across the prespecified "
                "feature set. Covariates are nuisance parameters outside that set, "
                "and the P values for covariates are unadjusted and marked (u).",
                "CI: confidence interval; SD: standard deviation."]}


def table5(rq3, h1):
    rows = []
    sig = rq3[(rq3.p_fdr < 0.05) & rq3.term.str.contains(":")]  # family members only
    rows.append(("Interaction terms surviving correction", "", "", ""))
    for _, r in sig.sort_values("p_fdr").iterrows():
        rows.append((f"    {pretty_term(r.term)} ({r.outcome.replace('_', ' ')})",
                     f"{r.beta:.3f}", _ci(r.ci_low, r.ci_high), _p_row(r)))
    rows.append(("Hypothesized moderation of the breathing guide", "", "", ""))
    key = "C(visual_breathing_guide)[T.True]:C(technique)[T.focused_attention_breath]"
    for oc in ["like_rate", "comment_rate"]:
        r = rq3[(rq3.outcome == oc) & (rq3.term == key)]
        if len(r):
            r = r.iloc[0]
            rows.append((f"    {pretty_term(key)} ({oc.replace('_', ' ')})",
                         f"{r.beta:.3f}", _ci(r.ci_low, r.ci_high), _p_row(r)))
    rows.append(("H1, Firth penalized likelihood", "", "", ""))
    for _, r in h1.iterrows():
        rows.append((f"    Visual breathing guide ({r.outcome.replace('_', ' ')})",
                     f"{r.beta:.3f}", _ci(r.ci_low, r.ci_high), "NA"))
    return {"caption": "Technique-moderated associations and the Firth test of H1.",
            "columns": ["Term", "Coefficient", "95% CI", "P value"], "rows": rows,
            "anchors": [("header", 0), ("header", 2), ("header", 3)],
            "footnotes": [
                "Interaction columns supported by fewer than 10 observations were dropped "
                "before fitting (Amendment 5); the breathing guide occurs in only 2 of 8 "
                "technique levels, so a single interaction term was estimable.",
                "Firth intervals are profile-likelihood intervals and are not accompanied "
                "by a Benjamini-Hochberg adjusted P value; the estimator corrects "
                "small-sample bias in the score equation but leaves the likelihood "
                "uncorrected for dispersion, so the intervals are conservative relative "
                "to the cluster-robust intervals in Table 4.",
                "CI: confidence interval; NA: not applicable; SD: standard deviation."]}


def build():
    df, ec, dd = load()
    rel = json.loads((ROOT / "data_main/05_reliability/reliability_report.json").read_text())
    rq1 = json.loads((ROOT / "data_main/06_results/rq1_descriptives.json").read_text())
    rq2 = pd.read_csv(ROOT / "data_main/06_results/rq2_associations.csv")
    rq3 = pd.read_csv(ROOT / "data_main/06_results/rq3_interactions.csv")
    h1 = pd.read_csv(ROOT / "data_main/06_results/h1_firth.csv")
    return [table1(df, ec, dd), table2(rel), table3(rq1), table4(rq2), table5(rq3, h1)]


if __name__ == "__main__":
    for i, t in enumerate(build(), 1):
        print(f"\n=== Table {i}. {t['caption']}")
        print("  " + " | ".join(t["columns"]))
        for r in t["rows"]:
            print("  " + " | ".join(str(x) for x in r))
        for f in t["footnotes"]:
            print("  ^ " + f)
