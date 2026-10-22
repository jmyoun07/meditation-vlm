#!/usr/bin/env python3
"""Build Multimedia Appendix 1 and Multimedia Appendix 2."""
from __future__ import annotations
import json, pathlib, sys
import pandas as pd
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_docx import (ROOT as R2, base_doc, heading, _para, _runs, add_table,
                       _set_font, BODY_PT, SMALL_PT)
from make_tables import pretty_term, CODED_LABELS, GATE_STATUS, coded_order


def _p(v):
    return "<.001" if v < 0.001 else f"{v:.3f}".lstrip("0")


# Full text of the protocol amendments. The Methods carry a one- or
# two-sentence summary of each; the complete record lives here and in the Open
# Science Framework entry, so the Methods can read as methods.
AMENDMENTS = [
 ("Amendment 1 (2026-09-14): Firth penalized likelihood for H1.",
  "The visual breathing guide proved far rarer than anticipated, so "
  "maximum-likelihood estimates for the feature are biased away from the null "
  "with unstable standard errors. H1 is estimated by Firth penalized likelihood, "
  "a Jeffreys-prior penalty on the binomial-logit score, with "
  "profile-likelihood confidence intervals, on the feature and the covariates "
  "rather than on the full feature set carried by the main models (see "
  "Amendment 10). The unpenalized estimate is reported alongside the penalized "
  "one as a sensitivity analysis, and the observed prevalence is reported "
  "regardless of the test outcome."),
 ("Amendment 2 (2026-09-14): not_assessable split into no_variance and "
  "insufficient_overlap.",
  "A variable whose agreement statistic is undefined is reported in one of two "
  "distinct states, never as unreliable: no_variance, where the feature is "
  "near-absent so agreement is not estimable, and insufficient_overlap, where "
  "the variable is structurally conditional so the two raters rarely code the "
  "variable on the same video. Variables in either state are reported as underpowered. No "
  "variable's inclusion changed."),
 ("Amendment 3 (2026-09-14): three specification corrections.",
  "A coverage guard excludes predictors observed on under half the corpus from "
  "the main model and analyses such predictors in the subsample of definition; the nested "
  "congruence variable, defined only where a breathing guide exists and "
  "therefore near-collinear with the H1 feature, is analysed conditionally; and "
  "the non-proportion outcome takes a Gaussian family with an identity link "
  "rather than the fractional-logit family specified for the rates."),
 ("Amendment 4 (2026-09-17): the measurement instrument as actually run.",
  "The analysis plan named the second coder inconsistently, as Gemini 2.5 Flash "
  "in the prose and GPT-4o in the configuration file beside the plan, and "
  "neither "
  "matched the run. Under a hard zero-marginal-cost constraint, corpus-scale "
  "coding does not fit any free application programming interface tier, so both "
  "raters ran on existing subscriptions: rater 1 is claude-opus-4-8 in an "
  "interactive session, rater 2 is gpt-5.6-sol through the Codex command-line "
  "interface, and Gemini 2.5 Flash was retained only for eligibility screening. "
  "Three consequences are reported here rather than buried. Inter-model "
  "agreement is between Claude and Codex and is not comparable to the pilot's "
  "Claude-to-Gemini values. A temperature of 0 holds for rater 2 and the "
  "screening classifier but is not settable for rater 1, so the 10% test-retest "
  "arm carries the burden of demonstrating that rater's stability. And rater "
  "1's blinding to outcomes is a procedural guarantee, since the coding prompt "
  "carries only frames and transcript, rather than an architectural one."),
 ("Amendment 5 (2026-10-04): minimum support for interaction cells.",
  "The analysis plan added technique-by-feature interaction terms without "
  "specifying a minimum cell size. Executed as written, the specification was "
  "not estimable: six of the eight breathing-guide interaction columns were "
  "identically zero, the like-rate model failed with a singular cluster "
  "covariance, and the comment-rate model returned aliased coefficients "
  "indistinguishable in the output from estimated ones. Cells holding a single "
  "video produced quasi-separation artefacts, the most extreme resting on one "
  "video and returning a coefficient of -14.66 with the smallest P value in the "
  "interaction table. Design columns that are constant or exactly aliased are "
  "now dropped, as are interaction columns supported by fewer than 10 "
  "observations. Interaction terms surviving correction fall from 12 to 1 and "
  "the largest surviving coefficient from 14.66 to 4.69; both counts are "
  "recomputed under the corrected multiplicity family below, and the amendment "
  "was filed when the guarded count stood at 3. The threshold was chosen after "
  "the unguarded table had been seen, and is reported as a documented "
  "deviation."),
 ("Amendment 6 (2026-10-04): two corrections of record.",
  "The analysis plan stated that a formal power calculation was recorded in a "
  "named file. No such calculation was performed and no such file existed; the "
  "originating protocol chose the target sample pragmatically and deferred the "
  "calculation to the analysis plan, where the calculation was never completed. A post-hoc "
  "precision analysis of the realized design now stands in place of the "
  "promised calculation and is labelled post-hoc. The analysis plan also "
  "promised a commit hash recorded when the plan was written. The project was "
  "not under version control at that point, so no such hash exists; version control was "
  "initialized after coding and analysis were complete, and the resulting "
  "snapshot and checksum manifest are reproducibility records that do not "
  "evidence pre-lock freezing."),
 ("Correction (2026-10-18): the false discovery rate family was too broad.",
  "Section 5.3 of the analysis plan controls the false discovery rate across the "
  "feature set. The first implementation corrected across every estimated term "
  "in each model, covariates and technique main effects included. The widening "
  "was not neutral: a term's adjusted value is the unadjusted P value times "
  "the family size over the term's rank, and the covariates carry some of the "
  "smallest P values in these models, so including the covariates raised the "
  "family size by a few while raising every feature's rank by as much, pulling "
  "the ratio toward the unadjusted value. The too-large family therefore made the features look more "
  "significant, not less. The family is now the prespecified feature set, with "
  "covariate P values reported unadjusted and marked. No coefficient, standard "
  "error, or confidence interval changes. The three like-rate associations and "
  "the composite-index association of the breathing guide are unaffected, but "
  "interaction terms surviving correction fall from 3 to 1: posture or mudra "
  "within loving-kindness practice on comment rate and voice pacing within the "
  "residual technique category on like rate no longer survive. Both readings of "
  "the feature set for the interaction model, interactions alone or feature "
  "main effects together with interactions, give the same surviving set. The "
  "change restores the planned specification rather than amending the "
  "specification."),
 ("Amendment 7 (2026-10-18): the human-verified subsample was not coded.",
  "The analysis plan specified a human-verified subsample of about 150 videos, "
  "coded by two trained non-expert raters, to establish agreement between the "
  "vision-language models and human coders. A 10% subsample was drawn and set "
  "aside as planned, but no human coding was performed, so the planned "
  "model-to-human comparison is absent. Reliability evidence therefore rests "
  "entirely on the three automated arms, which establish that the two models "
  "agree with each other and with themselves, not that either agrees with a "
  "human expert. A bias shared by both models would raise inter-model agreement "
  "rather than lower that agreement, and would be invisible in all three arms, so the "
  "manuscript's claims are phrased as claims about reproducible coding rather "
  "than about validated coding."),
 ("Amendment 8 (2026-10-20): two planned covariates are not in the models.",
  "Section 5.1 of the analysis plan lists channel type among the covariates. "
  "The retrieval never collected the variable: channel type is absent from "
  "the raw metadata and from every downstream frame, so no model adjusted "
  "for channel type and none could have. Closed captions available was collected but likewise "
  "never carried into the analytic frame. The covariates actually fitted in "
  "every reported model are session length, log channel subscribers and video "
  "age, each standardized, with channel cluster-robust standard errors. Three "
  "places in the manuscript asserted adjustment for channel type and are "
  "corrected. The variable cannot be recovered without a fresh retrieval, "
  "which would return current metadata for a corpus retrieved on 2026-07-27, "
  "so channel type is recorded as missing rather than added. Channel type would have "
  "absorbed between-channel composition that the remaining covariates do not; "
  "cluster-robust standard errors account for dependence within a channel but "
  "do not adjust the point estimates for composition."),
 ("Amendment 9 (2026-10-20): what was fixed when, and three protocol items "
  "not delivered.",
  "The protocol was prepared on 2026-06-14, before the first retrieval on "
  "2026-07-27, and fixed the four research questions, the three directional "
  "hypotheses, the eligibility rules in the form reported here, the coding "
  "design of opening-weighted frames with a transcript against a fixed schema "
  "coded by at least two models, the three reliability arms, the rule that a "
  "variable failing an agreement threshold is reported as low-reliability and "
  "excluded from the confirmatory models, fractional-logit models for the "
  "rates with channel-level clustering, false discovery rate control across "
  "the feature set, and reporting under the Strengthening the Reporting of "
  "Observational Studies in Epidemiology (STROBE) statement. Neither the protocol nor the "
  "analysis plan drawn from the protocol was deposited in a study registry. "
  "Both are openly available at https://github.com/jmyoun07/meditation-vlm, but that repository was published "
  "after the analysis was complete and so fixes no date, and "
  "neither date can be verified independently of the files themselves. The "
  "study is reported as protocol-driven and is not described as preregistered. Four things in this report do not come from the protocol. "
  "The agreement threshold of 0.60 is a value the protocol deferred to the "
  "analysis plan, and that plan postdates the data. The composite video power index is "
  "not in the protocol. The negative-binomial robustness check on counts with "
  "a views offset is not reported. The parallel Korean-language retrieval for "
  "cross-language comparison was never carried out. And the screening "
  "classifier was to be verified on a random subsample by trained raters with "
  "a third adjudicating: the subsample was drawn (n=189) and never coded, a "
  "separate omission from the human coding subsample of Amendment 7."),

 ("Amendment 10 (2026-10-20): the consensus rule is stated, and four reported "
  "quantities are corrected.",
  "A pre-submission audit against the analysis code and the coded data "
  "corrected five statements and added one analysis. First, the rule reducing "
  "two models' codes to one value per video was never stated. The rule takes "
  "the mode "
  "for categorical and binary variables and the mean for continuous ones, and "
  "with two raters a tie resolves to the sort-first value, which for a binary "
  "variable is the negative one. Binary prevalences are therefore lower "
  "bounds, and every confirmatory model is now also refit on the 1,146 videos "
  "(70.1%) where the two models agreed on every feature the model carries; both "
  "surviving effects are unchanged (posture or mudra 0.197 to 0.200, breathing "
  "guide -0.302 to -0.314). "
  "Second, the frame schedule was misdescribed. The 24-frame cap binds for "
  "every video over 2 minutes and discards half of the 2-minute opening "
  "window, so the retained opening frames span 0 to 55 seconds and the "
  "remaining extracted frames are a median of 60 seconds apart; of the 12 "
  "frames a model receives, 6 fall in the first 25 seconds, the later ones "
  "are a median of 180 seconds apart, and the last sits at a median 68% of "
  "session length. Third, the reported breathing cadence of 6.136 breaths per "
  "minute reported a mean for a right-skewed distribution and averaged 47 "
  "videos, 11 of which the consensus coded as having no pacer. The mean was "
  "the substantive error: the median is 3.81 over the 36 consensus pacers and "
  "3.88 over all 47, so the denominator barely shifts the centre. The statistic is now "
  "the median of the 36 consensus-identified pacers, 3.81 "
  "(interquartile range 3.15-5.81). Fourth, the test-retest arm was "
  "described as 10% of the "
  "corpus and is 396 videos (24.2%). Fifth, breathing cadence was said to "
  "have been coded by both models on the same video 76 times; 76 is the "
  "total number of cadence codes and the two-model overlap is 29 videos, on "
  "which agreement was high (intraclass correlation coefficient 0.948). "
  "The Firth model for H1 is also no "
  "longer described as sharing the main models' specification: that model "
  "carries the "
  "breathing guide and the covariates, where the main models carry every "
  "presentation feature jointly, which is why the two differ in sign."),

 ("Amendment 11 (2026-10-20): the effect sizes quoted in prose are now "
  "computed rather than asserted.",
  "The relative and percentage-point effects in the Abstract, Results and "
  "Discussion did not follow from the fitted coefficients by any standard "
  "transformation and could not be reproduced. The coefficients themselves "
  "never changed, so the quoted effects appear to have been written by hand "
  "when the Results were first drafted and never checked. Each quoted effect "
  "is now derived from the fitted model as an average marginal effect, the mean "
  "predicted outcome with a feature off and on across the whole modelled "
  "frame, and written to marginal_effects.csv, which the manuscript audit "
  "checks every quoted figure against. Three quantities change. Showing a posture or mudra moves the "
  "predicted like rate by 0.365 percentage points, a relative increase of "
  "21.3%, not 0.355 points and 19.3%. A visual breathing guide moves the same "
  "rate by "
  "-0.477 points, a relative reduction of 25.7%, not -0.545 points and "
  "29.7%. A one-SD increase in video age gives a 32.3% relative reduction, "
  "not 39.0%. No coefficient, confidence interval or P value changes, and no "
  "conclusion turns on the revision."),
]


def appendix():
    doc = base_doc()
    p = _para(doc, spacing=2.0, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(p.add_run("Multimedia Appendix 1. Supplementary methods and results"),
              13, bold=True)

    heading(doc, "A. Coded variables and the prespecified reliability gate", 1)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "Each video was coded independently by two vision-language models given "
             "identical inputs: 12 opening-weighted frames and the transcript. The "
             "codebook, the output schema, and the coding prompts were frozen before "
             "coding and are reproduced in the project repository. A variable entered "
             "the confirmatory models only on reaching a Krippendorff alpha of 0.60 "
             "or above in the inter-model arm.")
    rel = json.loads((ROOT / "data_main/05_reliability/reliability_report.json").read_text())
    spec = {"caption": "Coded variables, measurement level, and inclusion status.",
            "columns": ["Variable", "Level", "Inter-model alpha", "Status"],
            "rows": [], "anchors": [("header", 2), ("header", 1)], "footnotes": [
                "Alpha values are repeated from Table 2 of the main text.",
                "Conditional variables are defined only on a subset of videos. "
                "NA: not assessable."]}
    levels = {"technique": "Nominal, 8 levels",
              "visual_breathing_guide": "Binary",
              "breathing_cadence_bpm": "Continuous, conditional",
              "visual_verbal_congruence": "Nominal, conditional",
              "presenter_visibility": "Nominal, 3 levels",
              "setting_imagery": "Nominal, 5 levels",
              "nature_imagery_present": "Binary",
              "posture_or_mudra_shown": "Binary",
              "background_sound_type": "Nominal, 6 levels",
              "onscreen_text_overlay": "Binary"}
    for k in coded_order(rel):
        a = rel["inter_model"][k]
        spec["rows"].append((CODED_LABELS[k], levels[k],
                             f"{a:.3f}" if isinstance(a, (int, float)) else "NA",
                             GATE_STATUS[rel["variable_flags"][k]["status"]]))
    add_table(doc, "A1", spec, widths=[1.85, 1.95, 1.45, 1.25])

    heading(doc, "B. Full technique-by-feature interaction model", 1)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "The table reports every interaction term retained after the "
             "minimum-support rule of Amendment 5. Columns that were constant or "
             "exactly aliased were dropped first, and the rule then removed a "
             "further 14 of 69 interaction columns per outcome, leaving the 55 "
             "listed here for each of the two primary outcomes.")
    rq3 = pd.read_csv(ROOT / "data_main/06_results/rq3_interactions.csv")
    inter = rq3[rq3.term.str.contains(":")].sort_values(["outcome", "p_fdr"])
    spec = {"caption": "All estimable technique-by-feature interaction terms.",
            "columns": ["Outcome", "Term", "Coefficient", "95% CI", "P value"],
            "anchors": [("header", 4), ("header", 3)],
            "rows": [(r.outcome.replace("_", " ").capitalize(),
                      pretty_term(r.term),
                      f"{r.beta:.3f}", f"{r.ci_low:.3f} to {r.ci_high:.3f}",
                      _p(r.p_fdr)) for _, r in inter.iterrows()],
            "footnotes": ["P values are Benjamini-Hochberg adjusted across the "
                          "prespecified feature set.",
                          "CI: confidence interval."]}
    add_table(doc, "A2", spec, widths=[1.00, 2.55, 0.95, 1.30, 0.70])

    heading(doc, "C. Post-hoc precision analysis", 1)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "No formal power calculation was performed before data collection. The "
             "originating protocol selected the target sample pragmatically and "
             "deferred a formal justification to the analysis plan, where none was "
             "completed (Amendment 6). The minimum detectable effect below is "
             "therefore a property of the realized design, computed from the achieved "
             "cluster-robust standard error of each term as 2.802 times that standard "
             "error, the smallest true coefficient detectable with 80% power at a "
             "two-sided alpha of .05 before multiplicity correction.")
    d = pd.read_csv(ROOT / "data_main/06_results/rq2_associations.csv")
    lr = d[d.outcome == "like_rate"].copy()
    Z, ZB, mu = 1.959963985, 0.8416212336, 0.01835
    lr["se"] = (lr.ci_high - lr.ci_low) / (2 * Z)
    lr["mde"] = (Z + ZB) * lr.se
    lr = lr.sort_values("mde")
    spec = {"caption": "Minimum detectable effect for the primary like-rate model.",
            "columns": ["Term", "SE", "MDE, logit", "MDE, % of mean like rate"],
            "anchors": [("header", 1), ("header", 3)],
            "rows": [(pretty_term(r.term),
                      f"{r.se:.3f}", f"{r.mde:.3f}", f"{r.mde*(1-mu)*100:.1f}")
                     for _, r in lr.iterrows()],
            "footnotes": ["MDE: minimum detectable effect; SD: standard deviation; SE: standard error.",
                          "The mean like rate is 0.018; relative change is the "
                          "average marginal effect expressed against that mean."]}
    add_table(doc, "A3", spec, widths=[2.70, 0.70, 1.05, 2.05])

    heading(doc, "D. Attrition: coded versus uncoded eligible videos", 1)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "Of 1,769 eligible videos, 134 (7.6%) could not be coded because frame or "
             "transcript extraction failed. The comparison below supports treating the "
             "loss as non-differential with respect to the outcomes.")
    e = pd.read_parquet(ROOT / "data_main/02_eligible/eligible.parquet")
    s = pd.read_parquet(ROOT / "data_main/04_coded/codes_session.parquet")
    coded = set(s[(s.prompt_variant == "v1") & (s.replicate == 1)].video_id)
    e["coded"] = e.video_id.isin(coded)
    rows = []
    for col, lab, nd in [("view_count", "Views", 0), ("like_count", "Likes", 0),
                         ("comment_count", "Comments", 0),
                         ("like_rate", "Like rate", 4),
                         ("comment_rate", "Comment rate", 4),
                         ("session_length_min", "Session length, minutes", 1)]:
        if col not in e:
            continue
        a = pd.to_numeric(e.loc[e.coded, col], errors="coerce").dropna()
        b = pd.to_numeric(e.loc[~e.coded, col], errors="coerce").dropna()
        fmt = (lambda x: f"{x:,.0f}") if nd == 0 else (lambda x: f"{x:.{nd}f}")
        rows.append((lab, fmt(a.median()), fmt(b.median())))
    spec = {"caption": "Median values among coded and uncoded eligible videos.",
            "columns": ["Measure", "Coded (n=1,635)", "Not coded (n=134)"],
            "anchors": [("header", 1), ("header", 2)],
            "rows": rows,
            "footnotes": ["Values are medians.",
                          "Exclusion was driven by extraction failure, not by any "
                          "outcome-dependent rule."]}
    add_table(doc, "A4", spec, widths=[2.40, 2.05, 2.05])

    heading(doc, "E. Protocol amendments and corrections", 1)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "Eleven dated amendments and one correction are reproduced here in "
             "full; the Methods carry a summary of each. Amendments 1 to 4 were filed before the "
             "corresponding confirmatory estimates were examined. Amendments 5 "
             "to 7 and the correction were filed after the interaction estimates "
             "had been read, and are labelled in the record as documented "
             "deviations rather than pre-specifications.")
    for title, body in AMENDMENTS:
        p = _para(doc, indent=True, spacing=2.0)
        _set_font(p.add_run(title + " "), BODY_PT, bold=True)
        _runs(p, body)
    out = ROOT / "manuscript/Multimedia_Appendix_1.docx"
    doc.save(out)
    return out


STROBE = [
 ("Title and abstract", "1", "(a) Indicate the study design with a commonly used term in the title or the abstract. (b) Provide in the abstract an informative and balanced summary of what was done and what was found.", "Title; Abstract"),
 ("Introduction", "", "", ""),
 ("Background/rationale", "2", "Explain the scientific background and rationale for the investigation being reported.", "Introduction, paragraphs 1-5"),
 ("Objectives", "3", "State specific objectives, including any prespecified hypotheses.", "Introduction, paragraph 6 (RQ1-RQ4, H1-H3)"),
 ("Methods", "", "", ""),
 ("Study design", "4", "Present key elements of study design early in the paper.", "Methods, Study design and sample"),
 ("Setting", "5", "Describe the setting, locations, and relevant dates, including periods of recruitment, exposure, follow-up, and data collection.", "Methods, Study design and sample"),
 ("Participants", "6", "Give the eligibility criteria, and the sources and methods of selection of participants.", "Methods, Study design and sample; Figure 1"),
 ("Variables", "7", "Clearly define all outcomes, exposures, predictors, potential confounders, and effect modifiers. Give diagnostic criteria, if applicable.", "Methods, Measurement"),
 ("Data sources/measurement", "8", "For each variable of interest, give sources of data and details of methods of assessment. Describe comparability of assessment methods if there is more than one group.", "Methods, Measurement; Table 2"),
 ("Bias", "9", "Describe any efforts to address potential sources of bias.", "Methods, Reliability and statistical analysis; Results, Corpus and sample flow; Discussion, Limitations"),
 ("Study size", "10", "Explain how the study size was arrived at.", "Methods, Study design and sample; Multimedia Appendix 1, Section C"),
 ("Quantitative variables", "11", "Explain how quantitative variables were handled in the analyses. If applicable, describe which groupings were chosen and why.", "Methods, Reliability and statistical analysis"),
 ("Statistical methods", "12", "(a) Describe all statistical methods, including those used to control for confounding. (b) Describe any methods used to examine subgroups and interactions. (c) Explain how missing data were addressed. (d) Describe any sensitivity analyses.", "Methods, Reliability and statistical analysis; Deviations from the protocol"),
 ("Results", "", "", ""),
 ("Participants", "13", "(a) Report numbers of individuals at each stage of the study. (b) Give reasons for non-participation at each stage. (c) Consider use of a flow diagram.", "Results, Corpus and sample flow; Figure 1"),
 ("Descriptive data", "14", "(a) Give characteristics of study participants and information on exposures and potential confounders. (b) Indicate number of participants with missing data for each variable of interest.", "Results, Corpus and sample flow and Technique and presentation landscape; Tables 1 and 3; Figure 3"),
 ("Outcome data", "15", "Report numbers of outcome events or summary measures.", "Results, Corpus and sample flow; Table 1"),
 ("Main results", "16", "(a) Give unadjusted and confounder-adjusted estimates and their precision. (b) Report category boundaries when continuous variables were categorized. (c) If relevant, consider translating estimates of relative risk into absolute risk.", "Results, Associations with engagement; Table 4; Figure 4"),
 ("Other analyses", "17", "Report other analyses done, such as analyses of subgroups and interactions, and sensitivity analyses.", "Results, Technique moderation; Table 5; Multimedia Appendix 1, Section B"),
 ("Discussion", "", "", ""),
 ("Key results", "18", "Summarise key results with reference to study objectives.", "Discussion, Principal results"),
 ("Limitations", "19", "Discuss limitations of the study, taking into account sources of potential bias or imprecision. Discuss both direction and magnitude of any potential bias.", "Discussion, Limitations"),
 ("Interpretation", "20", "Give a cautious overall interpretation of results considering objectives, limitations, multiplicity of analyses, results from similar studies, and other relevant evidence.", "Discussion, Comparison with prior work; Interpretation and implications; Conclusions"),
 ("Generalisability", "21", "Discuss the generalisability (external validity) of the study results.", "Discussion, Limitations, items 7 and 8"),
 ("Other information", "", "", ""),
 ("Funding", "22", "Give the source of funding and the role of the funders for the present study and, if applicable, for the original study on which the present article is based.", "Funding"),
]


def strobe():
    doc = base_doc()
    p = _para(doc, spacing=2.0, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(p.add_run("Multimedia Appendix 2. STROBE checklist for "
                        "cross-sectional studies"), 13, bold=True)
    p = _para(doc, indent=True, spacing=2.0)
    _runs(p, "The Strengthening the Reporting of Observational Studies in Epidemiology "
             "(STROBE) checklist is reported for a cross-sectional, retrospective "
             "content analysis of public platform data with no human participants. "
             "Items phrased in terms of participants are reported in terms of videos, "
             "the unit of analysis. Transparent Reporting of a multivariable prediction "
             "model for Individual Prognosis Or Diagnosis (TRIPOD) is not applicable, "
             "because no prediction model is developed or validated.")
    spec = {"caption": "Location of each STROBE item in the manuscript.",
            "columns": ["Section and item", "No", "Recommendation", "Reported in"],
            "rows": [(a, b, c, d) for a, b, c, d in STROBE],
            "bold_rows": [i for i, r in enumerate(STROBE) if not r[1]],
            "anchors": [("header", 1)],
            "footnotes": ["Rows without an item number are section headers."]}
    add_table(doc, "B1", spec, widths=[1.55, 0.35, 2.85, 1.75])
    out = ROOT / "manuscript/Multimedia_Appendix_2.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    import sys
    want = set(sys.argv[1:]) or {"--appendix1", "--appendix2"}
    if want & {"--appendix1", "--appendix"}:
        print("wrote", appendix())
    if want & {"--appendix2", "--strobe"}:
        print("wrote", strobe())
