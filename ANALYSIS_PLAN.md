# Analysis Plan

**Technique-Specific Audiovisual Features of Guided Meditation Videos on YouTube
and Their Association With Viewer Engagement: A Vision-Language Model–Based
Infodemiology Study**

> Preregistration template: OSF Preregistration (adapted for a secondary-data,
> no-human-participants infodemiology content analysis; reporting per STROBE).
> This document **freezes** all confirmatory decisions before the analytic
> dataset is locked. Fields marked *[fill at registration]* require a final value
> before submission. A ~30-video English pilot was run to validate the pipeline
> and refine rules; the pilot data are **not** part of the confirmatory dataset.

---

## 1. Study information

### 1.1 Authors
[Author 1], [Author 2], [Author 3] · Corresponding author: [name, email]

### 1.2 Description
Guided meditation is among the most widely consumed self-management practices on
video platforms, and YouTube is a primary access point. Whether a viewer engages
with and completes a session is a prerequisite for any benefit, yet little is
known about which *meditation-specific* audiovisual characteristics sustain
engagement. We will use vision-language models (VLMs) to code guided meditation
videos by technique and by audiovisual features that neither metadata nor
transcripts capture (e.g., on-screen breathing pacers, posture demonstration,
silence-to-voice structure, background-sound type), and relate these to objective
platform engagement metrics, stratified by technique. No clinician scoring is
used: outcomes are objective platform metrics and predictors are objectively
codable presentation attributes. Validity rests on the reproducibility of
automated coding.

**Scope statement.** All findings describe *engagement*, not clinical efficacy.
Nothing here assesses the therapeutic accuracy or safety of any video.

### 1.3 Hypotheses (directional, confirmatory)
- **H1.** Presence of a synchronized on-screen visual breathing guide is
  positively associated with engagement (like_rate and comment_rate).
- **H2.** A higher silence-to-voice ratio is positively associated with
  engagement among relaxation/sleep-oriented techniques (yoga-nidra/body-based
  relaxation, body scan) but **not** among instruction-heavy techniques
  (loving-kindness, open-monitoring, visualization).
- **H3.** The magnitude and/or direction of feature–engagement associations vary
  by meditation technique (significant technique × feature interactions).

Research questions RQ1 (landscape, descriptive) and RQ4 (reliability of VLM
coding) are addressed without directional hypotheses.

---

## 2. Design plan

### 2.1 Study type
Observational; cross-sectional, retrospective content analysis of existing public
platform data. VLMs serve as the measurement instrument. No experimental
manipulation; no human participants.

### 2.2 Blinding
Not applicable (no intervention). Coding models are blind to engagement outcomes:
models receive only frames + transcript and never see view/like/comment counts.

### 2.3 Study design
Videos are retrieved via the YouTube Data API v3 using technique-specific seed
queries, screened for eligibility, sampled for frames + transcript, and coded
independently by ≥2 VLMs against an a priori codebook. Engagement outcomes and
covariates come from platform metadata. Associations are modeled with
multivariable regressions including a channel-level random effect and
technique × feature interactions.

---

## 3. Sampling plan

### 3.1 Existing data
Data exist but have **not** been accessed/coded for the confirmatory analysis at
the time of registration. (The pilot used a separate, small, discarded sample.)

### 3.2 Data collection procedures
- **Source:** YouTube Data API v3, single fixed retrieval window
  *[fill: calendar dates]*, `regionCode` *[fill; pilot used US]*.
- **Seed queries:** frozen in `config/seed_queries.yaml` (English primary; Korean
  retrieved in parallel for an exploratory cross-language comparison only).
- **Retrieval rules:** cap results per query before deduplication
  (`max_results_per_query` *[fill; e.g., 200]*); record API ranking and all
  metadata; deduplicate by video id; log every query string, retrieval date, and
  quota usage to `data/01_raw/retrieval_manifest.json`.

### 3.3 Sample size
Target **~2,000 eligible videos**, distributed across the seven techniques at
roughly **250–350 per technique**.

### 3.4 Sample-size rationale
Chosen to (a) give stable estimates for multivariable count/ratio regression with
~12 predictors plus interaction terms, (b) tolerate listwise exclusions (e.g.,
hidden like counts), (c) detect small standardized associations with adequate
power, and (d) retain a held-out subsample for reliability. The pilot (n≈29)
confirmed that confirmatory models are singular/underpowered below this target.

> **Correction (2026-10-04, Amendment 6).** This section originally asserted
> that "a formal power/precision calculation for the primary like_rate model is
> recorded in `docs/power_analysis`." No such calculation was performed, and no
> such file existed. The protocol document that this registration derives from
> states that the ~2,000 target was "chosen pragmatically" and that a formal
> justification "will be finalized at preregistration"; it was not. The sample
> size was fixed by the pragmatic per-technique target alone. A **post-hoc
> precision analysis** of the realized design is now recorded in
> `docs/power_analysis.md` and is labelled post-hoc there. It reports the
> minimum detectable effect per model term so that null findings can be read
> against a stated detection limit.

### 3.5 Stopping rule
Retrieval stops when the fixed window is exhausted for all seed queries and the
per-technique targets are met (or the query pool is exhausted). No outcome-
dependent stopping.

---

## 4. Variables

The full a priori codebook is frozen in `codebook/codebook.md`; the machine
contract is `codebook/schema.json`; coding prompts are `codebook/prompts/`.

### 4.1 Independent variables — VLM-coded (codebook group A)
technique (7-level nominal + optional secondary); visual_breathing_guide
(binary); breathing_cadence_bpm (continuous, conditional); visual_verbal_
congruence (nominal); presenter_visibility (nominal); setting_imagery (nominal);
nature_imagery_present (binary); posture_or_mudra_shown (binary);
background_sound_type (nominal); onscreen_text_overlay (binary).

### 4.2 Independent/structural — computed (group B)
silence_to_voice_ratio and voice_pacing_wpm (from transcript timestamps),
session_length_min (metadata).

### 4.3 Contextual — metadata (group C)
channel_type, subscriber_count, recency_days, closed_captions_available.

### 4.4 Dependent — engagement (group D)
- **Primary:** like_rate = likeCount/viewCount; comment_rate = commentCount/viewCount.
- **Secondary:** video_power_index (composite). **VPI formula frozen here:**
  `views_weight*log1p(view_count) + likes_weight*log1p(like_count)` with weights
  `views_weight=1.0, likes_weight=1.0` (config `analysis.vpi_formula`).
- **Exploratory:** comment_completion_effect_signal (LLM-coded audience
  expression; descriptive only, not a clinical outcome).

> **Measurement caveat (registered):** the YouTube Data API exposes no per-video
> watch-time/retention for third-party videos; D1–D3 are engagement proxies and
> D4 is exploratory.

### 4.5 Instrument (VLM measurement) — frozen
- **Models (≥2 for inter-model agreement):** Claude Opus 4.8 (`claude-opus-4-8`)
  and Gemini 2.5 Flash (`gemini-2.5-flash`). Exact API/model version strings and
  decoding settings recorded at registration; **temperature = 0** for all coding.
- **Inputs per video:** 12 opening-weighted sampled frames (selection rule frozen
  in `coding.select_frames`) + transcript excerpt (captions or faster-whisper
  ASR). Both models receive identical inputs.
- **Prompts:** primary `codebook/prompts/coding_v1.md`; sensitivity variant
  `codebook/prompts/coding_v2.md` (to be hardened to pin output shape before the
  run — see §7).

---

## 5. Analysis plan

### 5.1 Statistical models
- **RQ1 (landscape):** descriptive distributions of techniques and features with
  uncertainty intervals.
- **RQ2 (association):** engagement rates modeled with fractional-logit
  (GLM Binomial, logit link) for like_rate and comment_rate; negative-binomial
  with a log(views) offset as a robustness check for counts. Covariates:
  session_length_min, log(subscriber_count), channel_type, recency_days (all
  continuous predictors standardized). **A channel-level random effect** accounts
  for clustering; where the mixed GLM does not converge, channel **cluster-robust
  SEs** are used and reported as such (HC1 fallback only when clusters ≤
  parameters, which will not occur at the target n).
- **RQ3 (moderation):** add technique × feature interaction terms; report
  technique-stratified estimates.

### 5.2 Transformations
Rates bounded to [0,1]; counts use a log(views) offset; subscriber_count →
log1p; continuous predictors z-standardized. Zero-variance predictors are dropped.

### 5.3 Inference criteria
Report standardized effect sizes with 95% confidence intervals rather than
relying on significance thresholds. Control the false discovery rate across the
feature set with **Benjamini-Hochberg** (`analysis.fdr_method`). H1–H2 are
directional; H3 is tested via interaction terms.

### 5.4 Reliability gate (RQ4) — confirmatory-set rule
Each VLM-coded variable is assessed for inter-model agreement (Krippendorff's α
for categorical/ordinal; ICC for continuous), test-retest, and prompt-sensitivity.
**Pre-registered threshold: α or ICC ≥ 0.60.** A variable is carried into
confirmatory models only if it meets threshold. **Distinction (registered):** a
variable whose α is *undefined due to no variance* in the analytic sample is
reported as "not assessable," **not** as low-reliability, and is handled per its
base rate (if a feature is near-absent, its hypothesis test is reported as
underpowered rather than the variable being silently dropped). A human-verified
subsample (n≈150, two trained non-expert raters) provides VLM–human agreement.

### 5.5 Data exclusion
Exclude videos failing eligibility (`config/eligibility.yaml`: 2–60 min, public,
not age-restricted, not live, audio/captions available, is a guided session not
music-only/lecture). Exclude a VLM-coded variable from confirmatory models if it
fails the §5.4 reliability gate. Pre-specified sensitivity analyses: exclude
outliers and very new uploads; restrict to high-reliability variables.

### 5.6 Missing data
Hidden like counts (and other hidden metrics) are handled by pre-registered
listwise deletion for affected models and flagged (not silently imputed).
Transcript-derived variables are missing only if no transcript could be obtained;
such videos are flagged and excluded from transcript-dependent models.

### 5.7 Exploratory (clearly labeled non-confirmatory)
Korean cross-language comparison; comment-derived completion/effect signal;
alternative outcome definitions; any association not covered by H1–H3.

---

## 6. Ethics and data governance
Public platform data, no human participants, no PII; IRB exemption will be sought.
Collection complies with YouTube API Services ToS. No original video/audio is
redistributed; the shared dataset contains only video identifiers and derived
feature codes. Comment-derived analyses report aggregate patterns only and do not
quote or identify individuals.

---

## 7. Pilot-informed refinements to apply BEFORE locking the run
(These are registered as planned pipeline changes, not post-hoc analytic choices.)
1. **Harden the prompt-sensitivity variant** (`coding_v2.md`) so all models emit
   the exact schema shape (the pilot showed it induced a nested `{value,…}`
   structure in one model).
2. **Code `background_sound_type` from actual audio**, not frames+transcript
   (pilot inter-model α = 0.17); if audio coding is not feasible, pre-declare this
   variable exploratory.
3. **Retrieval/transcript robustness** is fixed operationally (yt-dlp
   `player_client=android` + combined format + inter-request delays;
   faster-whisper ASR when captions are unavailable/blocked). These do not affect
   analytic decisions.

---

## 8. Materials (version-controlled, to be frozen at registration)
- Codebook: `codebook/codebook.md`
- Output schema: `codebook/schema.json`
- Coding prompts: `codebook/prompts/coding_v1.md`, `coding_v2.md`, `eligibility_v1.md`
- Seed queries: `config/seed_queries.yaml`
- Eligibility rules: `config/eligibility.yaml`
- Analysis configuration (thresholds, VPI formula, covariates, FDR):
  `config/config.reported.yaml`, the configuration that produced the
  reported results with credentials replaced by environment-variable
  placeholders. `config/config.example.yaml` is a template and does not
  reproduce the study: its extraction date, per-query cap and frame counts
  differ from the run.
- Pipeline code: `src/meditation_vlm/`, `scripts/`
- **Repository version record (revised 2026-10-04, Amendment 6).** This line
  originally promised "a tagged commit hash of this repository recorded at
  registration." The project was not under version control at registration, so
  no such hash exists and none can be reconstructed. Version control was
  initialized on 2026-10-04, after coding (completed 2026-10-02) and analysis.
  The materials above are recorded two ways, both explicitly post-hoc:
  commit `bfc68dfee989285a91a4dc197a69f92e18bf8ff0`, tag
  `materials-frozen-2026-10-04`; and a SHA-256 manifest of every frozen file in
  `docs/materials_manifest.md`. The manifest is regenerated whenever a listed
  file changes, and its tag table names the state that produces the reported
  numbers, which after the correction of 2026-10-18 is
  `analysis-reported-2026-10-19` rather than the earlier analysis tag. Both
  records support reproduction of the reported analysis. **Neither establishes that any material was frozen before the
  analytic dataset was locked, and neither is offered as such.**

---

## Amendment 1 — 2026-09-14: rare-event estimation for H1

**Status when filed.** Data collection was still in progress (738 of an expected
~1,700 videos dual-coded). The reliability arm and the *predictor* distributions
had been inspected; **no outcome model estimates, coefficients, or p-values for
H1–H3 had been examined at the time this amendment was written.** This amendment
therefore precedes any confirmatory result.

**Reason.** H1 concerns the presence of a synchronized on-screen visual
breathing guide. In the accumulating sample that feature is far rarer than
anticipated: `visual_breathing_guide` is true for **32 of 1,201** consensus-coded
videos (2.7%), and `visual_verbal_congruence` is non-`not_applicable` for 33.
The planned fractional-logit GLM already emits overflow/near-separation warnings
on these terms. Maximum-likelihood estimates for a predictor at this prevalence
are biased away from the null and have unstable standard errors, so the
originally specified estimator is not fit for H1.

**Change.** H1 will be estimated with **Firth penalized likelihood** (Jeffreys-
prior penalty on the binomial-logit score), with **profile-likelihood confidence
intervals** rather than Wald intervals. The penalty is applied to the same model
specification as preregistered — same outcome definitions, same covariates
(session length, channel size, channel type, recency), same channel clustering.

**Unchanged.**
- H2 and H3, and all RQ2 terms other than the H1 feature, remain on the
  preregistered fractional-logit GLM with cluster-robust SEs.
- The Benjamini-Hochberg FDR family is unchanged.
- The reliability gate (α/ICC ≥ 0.60) is unchanged.

**Sensitivity.** The original unpenalized fractional-logit estimate for H1 will
be reported alongside the Firth estimate, so the effect of the amendment is
visible to the reader.

**Reporting commitment.** The observed prevalence of `visual_breathing_guide`
will be reported in the Results regardless of the outcome of the test, and H1
will be described as prevalence-limited.

### Amendment 2 — 2026-09-14: `not_assessable` clarified

`breathing_cadence_bpm` is undefined whenever no on-screen pacer is present, so
its ICC is not estimable from insufficient rater overlap rather than from low
agreement. §5.4's `not_assessable` state is hereby split into two recorded
reasons — `no_variance` and `insufficient_overlap` — and variables in either
state are reported as **underpowered, not unreliable**. No variable's inclusion
or exclusion changes as a result; only the label and its stated reason do.

### Amendment 3 — 2026-09-14: model specification corrections

Filed at the same time as Amendment 1, before any outcome estimate was
inspected. Three specification errors were found while dry-running the analysis
stage on the accumulating sample; each is corrected here.

1. **Structurally-missing variables are excluded from the main model.**
   `breathing_cadence_bpm` is defined only when an on-screen pacer is present,
   so it is observed for 2.8% of videos. Because the GLM deletes rows listwise,
   including it reduced the RQ2 model from N=1,201 to **N=34** and produced a
   singular design. Any variable observed for less than 50% of the analytic
   frame is now excluded from confirmatory models and reported descriptively.
   The stage also warns whenever a model is fitted on fewer than half the rows.

2. **`visual_verbal_congruence` is analysed conditionally, not jointly.**
   It is definitionally conditional on a visual breathing guide and is therefore
   near-deterministically nested in the H1 feature (1,163 of 1,169 non-guide
   videos are `not_applicable`). Entering both in one model is a specification
   error, so congruence leaves the main RQ2 model and is reported within the
   guide-present subsample.

3. **`video_power_index` is fitted as a linear model.** VPI is a weighted sum of
   logged counts on a 0–32 scale, not a proportion; the preregistered
   fractional-logit family restricted it to [0, 1] and left 3 of 1,201 rows.
   Rate outcomes (`like_rate`, `comment_rate`) stay on fractional logit with a
   binomial family; VPI is fitted with a Gaussian family and identity link,
   keeping the same covariates and channel-clustered SEs. The family used is
   recorded per term in the results tables.

None of these changes alters a hypothesis, an outcome definition, the covariate
set, or the FDR family. They correct estimator/specification choices that the
original preregistration under-specified.

### Amendment 4 — 2026-09-17: measurement instrument as actually run

**Status when filed.** Dual coding was still in progress (1,001 of 1,635
coding-ready videos coded by rater 1; 1,467 by rater 2). No confirmatory
coefficient table has been read. The analysis stage has been *executed* on the
accumulating sample to verify that it runs and to fix the specification errors
recorded in Amendment 3; that execution wrote result files to `06_results/`,
and this amendment's no-peeking claim rests on the fact that those coefficient
files were not opened. Term counts, model families, sample sizes and the
prevalence of `visual_breathing_guide` were inspected; effect estimates,
confidence intervals and p-values were not.

**The record being corrected.** §4.5 of this registration names the two coding
models as Claude Opus 4.8 and Gemini 2.5 Flash. The configuration file listed in
§8 as registered material (`config/config.example.yaml`) instead names Claude
Opus 4.8 and OpenAI GPT-4o. These two statements were inconsistent with each
other at registration. Neither describes what was run.

**What was actually run.**

| Role | Registered | As run |
|---|---|---|
| Eligibility classifier (stage 2) | *unspecified* | `google / gemini-2.5-flash`, temperature 0 |
| Coding rater 1 | `claude-opus-4-8` via API, temperature 0 | `claude-opus-4-8` **via an interactive Claude Code session**, temperature not settable |
| Coding rater 2 | `gemini-2.5-flash` (§4.5) / `gpt-4o` (§8 config) | `gpt-5.6-sol` via the Codex CLI, temperature 0 |

**Reason.** The study is run under a hard constraint of zero marginal cost, on
consumer subscriptions the authors already hold, with no paid API budget. Coding
~1,635 videos at 12 frames each is far outside the free tiers of the registered
APIs. Gemini's free tier was retained for the cheaper per-item screening step;
the second coding rater was moved to a model reachable through an existing
subscription. The substitution is a resourcing decision, made independently of
any outcome, and is not conditioned on any observed association.

**Consequences that must be reported in the manuscript.**
1. **RQ4 reliability is agreement between `claude-opus-4-8` and `gpt-5.6-sol`.**
   The pre-registered gate (α or ICC ≥ 0.60) and every downstream inclusion rule
   are unchanged; only the identity of the second instrument changes. Reliability
   estimates are therefore not comparable to the pilot's Claude–Gemini values,
   and the pilot α for `background_sound_type` (0.17) is superseded.
2. **Decoding is not pinned for rater 1.** An interactive Claude Code session
   exposes no temperature control, so "temperature = 0 for all coding" holds for
   rater 2 and the screening classifier but not for rater 1. The pre-registered
   test–retest arm (`test_retest_fraction = 0.10`) is the check on this rater's
   stochasticity and will be reported as such rather than assumed away.
3. **Rater 1 is not a blinded automated API call in the strict sense.** It runs
   inside a session that also contains pipeline engineering work. Blinding to
   outcomes is preserved operationally — the coding prompt supplies only sampled
   frames and the transcript, and engagement metrics are never placed in the
   coding context — but this is a procedural guarantee, not an architectural one,
   and is declared here as such.

**Unchanged.** Hypotheses H1–H3, the outcome definitions, the covariate set, the
channel clustering, the Benjamini–Hochberg family, the reliability threshold, and
the exclusion rules are all exactly as registered and as amended in 1–3.

---

## Amendment 5 — 2026-10-04: minimum support for interaction cells (RQ3)

**Status when filed.** Coding was complete (1,635 videos, both raters) and the
Stage 5 reliability gate had been applied. The RQ3 interaction model had been
executed and its coefficient table inspected. This amendment is therefore filed
**with knowledge of the RQ3 estimates** and is a documented deviation, not a
pre-specification.

**The problem.** Section 6 registers RQ3 as "add technique × feature
interaction terms." No minimum cell size was specified. Executed as written on
the full sample, the specification is not estimable:

- `visual_breathing_guide` is positive in 40 of 1,635 videos (2.4%) and occurs
  in only 2 of 8 technique levels (focused attention on the breath, n = 38;
  visualization and imagery, n = 1). Six of its eight interaction columns are
  identically zero.
- The `like_rate` interaction model failed outright (singular cluster
  covariance). The `comment_rate` model converged but returned aliased
  coefficients for the structurally empty columns, which were indistinguishable
  in the output from estimated ones.
- Cells holding a single video produced quasi-separation artefacts. The term
  `setting_imagery[text_only] × technique[movement_walking]` rests on **one**
  video whose comment_rate is 0, and returned beta = -14.66 with the smallest
  P value in the entire interaction table (P(FDR) = 1.7e-25).

**The deviation.** Two guards are added to the interaction model:

1. Design columns that are constant or exactly linearly dependent on retained
   columns are dropped before fitting.
2. Interaction columns supported by fewer than **10** observations are dropped.
   Those videos contribute to the corresponding main effect instead.

The threshold of 10 was chosen as a round minimum before inspecting which terms
it would remove, but it was chosen after the unguarded table had been seen, and
is reported as such.

**Effect on the reported results.** Interaction terms surviving FDR fall from 12
to 3, and the largest surviving interaction coefficient falls from |beta| =
14.66 to 4.69. Specifically:

| Removed term | Supporting cell |
|---|---|
| setting_imagery[text_only] × movement_walking | 1 video |
| setting_imagery[other] × movement_walking | 7 videos |
| nature_imagery_present × technique[other] | 13 of 19 videos |
| six visual_breathing_guide × technique columns | 0 videos each |

**Interpretive consequence that must be reported.** Once the empty
`visual_breathing_guide × technique` columns are dropped, the
`visual_breathing_guide` main effect in the RQ3 model is no longer the effect
within the reference technique (body scan contains no videos with a breathing
guide); it is a weighted blend across the pooled levels. The RQ2 model, which
carries no interactions, is the estimate to quote for H1. RQ3 is reported as
exploratory.

**Unchanged.** H1-H3, outcome definitions, the covariate set, channel
clustering, the Benjamini-Hochberg family, the reliability threshold, the
exclusion rules, and the RQ1 and RQ2 specifications.

---

## Amendment 6 — 2026-10-04: corrections to two false statements in this registration

**Status when filed.** After completion of coding and analysis. Both items
below are corrections of record, not analytic changes.

1. **Section 3.4 claimed a power calculation that does not exist.** The text
   asserted that a formal power/precision calculation was "recorded in
   `docs/power_analysis`." No calculation was performed and the file did not
   exist. The originating protocol states the ~2,000 target was chosen
   pragmatically with a formal justification deferred to preregistration, where
   it was never completed. A post-hoc precision analysis of the realized design
   is now recorded in `docs/power_analysis.md`, labelled post-hoc, reporting
   minimum detectable effects per term. Section 3.4 is corrected in place.

2. **Section 8 promised a registration-time commit hash that does not exist.**
   The project was not under version control at registration. Version control
   was initialized 2026-10-04. The snapshot (commit
   `bfc68dfee989285a91a4dc197a69f92e18bf8ff0`, tag
   `materials-frozen-2026-10-04`) and the SHA-256 manifest in
   `docs/materials_manifest.md` are reproducibility records only and do not
   evidence pre-lock freezing. Section 8 is corrected in place.

**Why these are recorded rather than silently fixed.** Both statements, left
standing, would have represented the study as having pre-data safeguards it did
not have. The reliability gate, the exclusion rules, and the H1 estimator
(Amendment 1) were genuinely specified before the outcome models were read; the
power calculation and the version-control freeze were not.

---

## Amendment 7 — 2026-10-18: the human-verified subsample was never coded

**Status.** Filed after analysis was complete and after the interaction
estimates had been read. A documented deviation, not a pre-specification.

**What was registered.** Section 5.4 states: "A human-verified subsample
(n≈150, two trained non-expert raters) provides VLM–human agreement."

**What happened.** A random 10% subsample (n=189) was drawn at the screening
stage and set aside, and the directory reserved for the human codes
(`data_main/06_human/`) remains empty. No human coding was performed. Under the
same zero-marginal-cost constraint recorded in Amendment 4, no trained raters
were available, and the planned comparison was not carried out.

**Consequence, stated plainly.** Every reliability figure in this study is
model-to-model or model-to-itself: inter-model agreement between
`claude-opus-4-8` and `gpt-5.6-sol`, test-retest within rater 1, and prompt
sensitivity within rater 1. These establish that the instrument is reproducible.
They do not establish that it is accurate. A bias shared by both models — a
systematic misreading of what counts as a posture, say — would raise inter-model
agreement rather than lower it, and would be invisible in all three arms. The
reliability gate of 0.60 therefore screens for reproducibility, and the
manuscript's claims are phrased as claims about reproducible coding rather than
about validated coding.

**Why this is recorded rather than quietly dropped.** The registered subsample
was the study's only planned link to a human reference standard. Removing the
sentence from the methods would have left a reader with no way to tell that the
link was planned and is missing.

---

## Correction — 2026-10-18: false discovery rate family restored to the registered feature set

**Status.** A correction of implementation, not a change of plan. It restores
what section 5.3 registers; it does not amend it. Recorded because the broader,
incorrect numbers had already been read.

**What was registered.** Section 5.3: "Control the false discovery rate across
the feature set with **Benjamini-Hochberg**."

**What was implemented.** `analysis._tidy` passed every estimated term of each
model to `multipletests`, so the family included the covariates
(`session_length_min_z`, `log_subscribers_z`, `recency_days_z`,
`C(channel_type)`) and, in the RQ3 model, the technique main effects.

**Why the direction matters.** This was not a neutral widening. Under
Benjamini-Hochberg a term's adjusted value is `p * m / rank`. The covariates
carry some of the smallest P values in these models (video age and channel
subscribers are at 1e-18 and below), so adding them raised `m` by a few but
raised the rank of every feature by as much, and the ratio moved toward the raw
P value. The too-large family therefore made the features look more significant,
not less.

**Effect on the results.** No coefficient, standard error, or confidence
interval changes; only the multiplicity correction does.

- RQ2: unchanged at the feature level. Like rate keeps three associations
  (posture or mudra, silence-to-voice ratio, visual breathing guide), comment
  rate still has none, and the composite index keeps the breathing guide. The
  terms that lose an adjusted value are covariates, now reported unadjusted and
  marked as such.
- RQ3: interaction terms surviving correction fall from 3 to 1. Surviving:
  setting "other" x open-monitoring mindfulness on comment rate (q = .007).
  No longer surviving: posture or mudra x loving-kindness on comment rate
  (q .035 -> .061) and voice pacing x technique "other" on like rate
  (q .047 -> .068).

**Restating Amendment 5 under the corrected family.** Amendment 5 recorded
that the minimum-support rule took interaction terms surviving correction from
12 to 3. Recomputed with the registered family, the same rule takes them from
12 to 1; the largest surviving coefficient still falls from 14.66 to 4.69. The
Amendment 5 entry above is left as filed, because it records what was observed
on 2026-10-04; the manuscript carries the restated figure.

Both defensible readings of "the feature set" for the RQ3 model — interactions
alone, or feature main effects together with interactions — give the same
surviving set, so the correction does not depend on which is chosen.

**Where this lands in the paper.** The Results now report one surviving
interaction; the Discussion reports the loving-kindness direction as a direction
worth testing rather than as a finding; Table 4 and Table 5 are rebuilt from the
corrected output; the covariate rows carry a "(u)" marker.

### Also of this date: technique-stratified estimates are not reported

Section 5.1 registers, for RQ3, "add technique × feature interaction terms;
report technique-stratified estimates." The interaction terms are reported, in
Table 5 and in full in Multimedia Appendix 1. The stratified estimates are not.

Fitting the feature model within a technique level needs roughly 15 parameters.
The levels hold 337, 330, 270, 265, 216, 126, 71 and 20 videos, so the smaller
ones cannot carry the model at all, and the larger ones would carry it only
marginally once channel-clustered standard errors are applied. Amendment 5 had
already established, on the pooled interaction model, that cells of this size
produce quasi-separation artefacts rather than estimates. Reporting eight
stratified models per outcome would have reproduced that failure in a longer
table.

The manuscript states in the Methods that the stratified estimates were
registered and are not reported, and why. Nothing is estimated differently as a
result; the registered interaction specification is what the moderation claims
rest on.

---

## Amendment 8 — 2026-10-20: two registered covariates are not in the models

**Status.** A correction of record, filed after analysis. The models were
never fitted with these covariates; the error was in what the manuscript said
about them.

**What was registered.** Section 5.1 lists the covariates as
`session_length_min`, `log(subscriber_count)`, `channel_type` and
`recency_days`. Section 4 also lists `closed_captions_available` among the
metadata captured.

**What happened.** `channel_type` was never collected. It is absent from
`data_main/01_raw/videos.parquet` and from every downstream frame, so no
model could have adjusted for it and none did. `closed_captions_available`
was collected and is present in the raw and eligible frames, but it was never
carried into the analytic frame and never entered a model either.

The covariates actually fitted, in every reported model, are
`session_length_min`, `log_subscribers` and `recency_days`, each
z-standardized, with channel cluster-robust standard errors.

**What the manuscript said.** Three places asserted adjustment for channel
type: the abstract's Methods, the metadata covariate list in the Methods, and
footnote a of Table 4. All three are corrected. Nothing else changes, because
nothing was ever estimated with the variable.

**Why it cannot be repaired.** Channel type is not derivable from the
retrieved metadata. Recovering it would require a fresh retrieval against the
YouTube API, which would return today's metadata for a corpus retrieved on
2026-07-27 and would not reproduce the analysed sample. The covariate is
therefore recorded as missing rather than added.

**What this costs.** Channel type would have absorbed between-channel
composition that the remaining covariates do not. Channel cluster-robust
standard errors still account for the dependence among videos from one
channel, but they do not adjust the point estimates for channel composition.
The adjusted associations should be read accordingly.

---

## Amendment 9 — 2026-10-20: what was fixed when, and three protocol items not delivered

**Status.** A correction of record, filed after analysis. Nothing is estimated
differently; this entry states what can and cannot be dated.

**The protocol.** `유튜브_meditation_vlm_protocol.docx` was prepared on
2026-06-14, six weeks before the first retrieval on 2026-07-27. It fixed:

- the four research questions and the three directional hypotheses, marked in
  the document as "to be registered before data analysis";
- the eligibility rules, in the form reported in the manuscript: public, a
  guided session, extractable audio or captions, 2 to 60 minutes, excluding
  music-only, lectures, live streams and age-restricted videos;
- the retrieval design: YouTube Data API v3, technique-specific seed queries, a
  single fixed window, a per-query cap before deduplication;
- the coding design: opening-weighted frames with the transcript, a fixed JSON
  schema, every video coded independently by at least two models;
- the three reliability arms, and the rule that a variable failing an agreement
  threshold is reported as low-reliability and excluded from the confirmatory
  models;
- fractional-logit models for the rates, channel-level clustering, false
  discovery rate control across the feature set, standardized effect sizes with
  confidence intervals in place of thresholds;
- reporting under STROBE, and the scope statement that the study speaks to
  engagement and not to clinical merit.

**What cannot be dated.** Neither the protocol nor this registration was
deposited in a public repository. The protocol's own file metadata gives
2026-06-14 and the first retrieval manifest gives 2026-07-27, but a file date is
evidence only of itself. The protocol is submitted with the manuscript as
Multimedia Appendix 2 so that a reader can see what it contains rather than
take its date on trust.

**Four things in the report that the protocol does not fix.**

1. **The threshold value of 0.60.** The protocol specifies a threshold and its
   consequence but leaves the number to registration, and that registration
   postdates the data. The manuscript no longer calls the value preregistered;
   it calls the rule preregistered and states where the number came from.
2. **The video power index.** The composite of logged views and likes appears
   first in the registration, not in the protocol.
3. **A negative-binomial robustness check** on counts with a views offset,
   specified in the protocol's analysis section, is not reported.
4. **The parallel Korean-language retrieval** for exploratory cross-language
   comparison was never carried out. The manuscript reports English and the
   United States region as a limitation but had not said that a second language
   was planned.

**A fourth unfulfilled verification.** The protocol also specified that the
screening classifier would be verified on a random subsample by trained raters,
with a third adjudicating disagreements. The subsample was drawn (n=189) and
never coded. This is separate from the human coding subsample of Amendment 7:
one would have checked eligibility screening, the other the coding itself.
Neither was done.
