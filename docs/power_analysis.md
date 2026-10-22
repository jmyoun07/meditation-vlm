# Precision analysis for the primary like_rate model

**Status: post-hoc.** No formal power or precision calculation was performed
before data collection. The protocol (`유튜브_meditation_vlm_protocol.docx`,
section "Sampling and sample size") states that the target of approximately
2,000 eligible videos was "chosen pragmatically" and that "a formal
power/precision justification for the primary regression will be finalized at
preregistration." That justification was not completed at preregistration, and
the file referenced by section 3.4 of `ANALYSIS_PLAN.md` did not exist
until this document was written on 2026-10-04, after coding and analysis were
complete. The sample size was therefore fixed by the pragmatic target, not by a
power calculation, and nothing below should be read as a pre-data justification.

What follows is the achieved precision of the realized design, reported so that
null findings can be read against a stated detection limit rather than treated
as evidence of absence.

## Realized design

| Quantity | Value |
|---|---|
| Eligible videos | 1,769 |
| Dual-coded videos | 1,635 |
| Rows in the like_rate model (listwise) | 1,584 |
| Channel clusters | 606 |
| Videos per channel (max) | 177 |
| like_rate mean | 0.01835 |
| like_rate SD | 0.01763 |
| Estimator | fractional logit (GLM binomial, logit link) |
| Standard errors | channel cluster-robust |
| Multiplicity | Benjamini-Hochberg across the feature set |

## Minimum detectable effect

The minimum detectable effect (MDE) is computed from the achieved
cluster-robust standard error of each term as
MDE = (z(0.975) + z(0.80)) x SE = 2.802 x SE,
that is, the smallest true coefficient the design would detect with 80% power
at a two-sided alpha of .05, before multiplicity correction. The logit
coefficient is converted to an average marginal effect at the observed mean
(beta x mean x (1 - mean)) and expressed both in percentage points of like_rate
and as a percentage of the mean like_rate.

| Term | SE | MDE (logit) | MDE (pp) | MDE (% of mean) |
|---|---|---|---|---|
| Session length (per SD) | 0.025 | 0.069 | 0.124 | 6.8 |
| Silence-to-voice ratio (per SD) | 0.025 | 0.069 | 0.125 | 6.8 |
| Voice pacing (per SD) | 0.026 | 0.073 | 0.132 | 7.2 |
| Video age (per SD) | 0.033 | 0.093 | 0.168 | 9.1 |
| Posture or mudra shown | 0.048 | 0.134 | 0.241 | 13.1 |
| Subscriber count (log, per SD) | 0.052 | 0.146 | 0.263 | 14.3 |
| Nature imagery present | 0.072 | 0.201 | 0.361 | 19.7 |
| Presenter: visuals only, voiceover | 0.082 | 0.230 | 0.415 | 22.6 |
| Presenter: on-screen presenter | 0.086 | 0.242 | 0.435 | 23.7 |
| Setting: nature | 0.090 | 0.251 | 0.452 | 24.6 |
| Visual breathing guide (H1 feature) | 0.097 | 0.272 | 0.490 | 26.7 |
| Setting: other | 0.109 | 0.306 | 0.551 | 30.0 |
| Setting: studio | 0.113 | 0.318 | 0.573 | 31.2 |
| Setting: text only | 0.122 | 0.341 | 0.614 | 33.4 |

## Interpretation

Continuous covariates and the two common binary features are estimated with
adequate precision: a change of 7% to 14% in relative like_rate per standard
deviation, or per feature, is detectable. Precision degrades for the sparse
categorical levels and for the H1 feature.

For the H1 feature (visual breathing guide), prevalence is 40 of 1,635 videos
(2.4%). The design detects a relative change in like_rate of about 27% or
larger. An association smaller than that would not be distinguishable from
zero here, so the H1 result is uninformative about small effects and is
reported as such rather than as evidence of no association.

The sparse levels of `setting_imagery` (text only, studio, other) carry MDEs of
30% to 33% of the mean. Null results on those levels should likewise be read as
imprecision rather than absence.

## Relation to the technique-stratified aim

The interaction models (RQ3) are substantially less precise than the main-effect
models because support is distributed across 8 technique levels. The H1 feature
is present in only 2 of the 8 levels (focused attention on the breath, n = 38;
visualization and imagery, n = 1), so a technique-moderated test of H1 is
estimable in one technique level only. The preregistered interaction
specification additionally produced quasi-separation artefacts in cells holding
as few as one video; interaction columns with fewer than 10 supporting
observations are therefore dropped (documented deviation, Amendment 5).
