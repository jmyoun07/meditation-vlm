# Pilot Results (run label: pilot-2026)

A ~30-video, English-only pilot executed the full protocol pipeline end to end to
validate the machinery and surface issues before the ~2000-video main run. **All
findings are engagement/feature-descriptive and about tooling reliability — not
clinical claims.**

## Pipeline completion

| Stage | Result |
|------|--------|
| 1. Retrieval | 122 unique videos from 16 technique seed queries (English); ~1,605 API units |
| 2. Screening | metadata gate 106/122 → Gemini eligibility → **30 selected** (1/106 classifier errors) |
| 3. Extraction | **29/30 frame sets** (avg 23 frames, opening-weighted); 1 video blocked by YouTube |
| 3b. Transcripts | **30/30** — 8 platform captions + 22 faster-whisper ASR (captions were IP-blocked) |
| 4. Coding | **29 videos coded by BOTH models** — Gemini 2.5 Flash (API) + Claude Opus 4.8 (in-session) |
| 5. Reliability | inter-model Krippendorff α + test-retest computed |
| 6. Analysis | RQ1 descriptives + RQ2 fractional-logit GLMs (channel cluster-robust SEs) |

Cost: **$0** (Gemini free tier + Claude via subscription).

## RQ4 — Inter-model reliability (the headline pilot finding)

Agreement between Claude Opus 4.8 and Gemini 2.5 Flash on the same 12 frames +
transcript per video (Krippendorff's α):

| Variable | α | Read |
|---|---|---|
| presenter_visibility | **1.00** | perfect |
| technique | **0.92** | excellent |
| nature_imagery_present | **0.86** | strong |
| setting_imagery | **0.82** | strong |
| posture_or_mudra_shown | **0.82** | strong |
| onscreen_text_overlay | 0.38 | low |
| background_sound_type | 0.17 | poor |
| visual_breathing_guide | — | undefined (no variance) |
| breathing_cadence_bpm | — | undefined (no variance) |
| visual_verbal_congruence | — | undefined (no variance) |

Interpretation — matches the protocol's expected pattern:
- **Concrete visual/structural codes are highly reproducible** (α 0.82–1.00):
  technique, presenter visibility, setting, nature imagery, posture. These are the
  variables to carry into confirmatory models.
- **background_sound_type is unreliable (α 0.17)**: audio type is hard to judge
  from frames + a text transcript. → The main run should code sound from **actual
  audio**, not infer it from frames/transcript.
- **Three breathing-guide variables are "undefined," not "unreliable":** almost no
  pilot video had an on-screen animated breathing pacer, so there was no variance
  for α to measure. The full 2,000-video sample will contain enough pacer videos
  to assess these (they carry hypothesis H1).

## RQ1 — Landscape (descriptive, n=29)

- **Technique:** focused-attention/breath 7, visualization 6, loving-kindness 6,
  yoga-nidra 5, body-scan 3, movement/walking 2, open-monitoring 0.
- **Presenter:** 24 voiceover-only, 4 on-screen presenter, 1 mixed.
- **Setting:** nature 10, abstract/animated 10, studio 4, other 3, text-only 2.
- **Nature imagery present:** 12/29. **Posture/mudra shown:** 6/29.
- **Silence-to-voice ratio:** mean 0.12 (SD 0.13) — mostly spoken guidance.
- **Voice pacing:** mean 70 wpm (SD 27) — slow, as expected for meditation.

## RQ2 / RQ3 — Associations (pilot: illustrative only)

RQ2 fractional-logit models for like_rate and comment_rate ran with channel
cluster-robust SEs over the reliable feature set (see `data/06_results/`).
**These estimates are not interpretable at n=29** — the model is near-saturated
(≈20 parameters), and RQ3 technique×feature interactions were singular. This
confirms the a priori need for the ~2,000-video sample; it is not a defect.

## What the pilot changes for the main run

1. **Prompt hardening:** the prompt-sensitivity variant (`coding_v2.md`) made
   Gemini emit a nested `{value, confidence}` structure that broke the schema (all
   29 sens rows lost). Fix the variant to pin the exact output shape before the
   full run. (Claude was unaffected.)
2. **Audio coding:** move `background_sound_type` (and any audio-dependent code)
   to real-audio input; frames+transcript are insufficient (α 0.17).
3. **Retrieval robustness:** YouTube blocks default yt-dlp; use
   `player_client=android` + combined format 18 + inter-request delays. Platform
   caption fetch gets IP-blocked → **faster-whisper ASR is the reliable transcript
   path** (≈38× realtime on CPU here).
4. **Reliability reporting:** distinguish "low α" from "α undefined (no variance)"
   in the report so rare-feature variables aren't wrongly dropped.
5. **Power:** n≈30 cannot support the confirmatory models; proceed to the full
   target for RQ2/RQ3.

## Artifacts
- Codes: `data/04_coded/codes_long.parquet` (92 rows; 29 videos × 2 models + retest)
- Reliability: `data/05_reliability/reliability_report.json`
- Results: `data/06_results/{rq1_descriptives.json, rq2_associations.csv, analysis_summary.json}`
- Derived vars: `data/05_derived/derived.parquet`
