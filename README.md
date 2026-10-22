# Meditation VLM — YouTube Guided Meditation Engagement Study

Implementation of the study protocol *"Technique-Specific Audiovisual Features of
Guided Meditation Videos on YouTube and Their Association With Viewer Engagement:
A Vision-Language Model–Based Infodemiology Study."*

This repository turns the protocol into a reproducible pipeline. No clinician
scoring is required: the reference signals are objective platform metrics plus
objectively codable visual attributes, and validity rests on the reproducibility
of automated (VLM) coding.

The study is reported as protocol-driven, not preregistered. The protocol and
the analysis plan are both here, but neither was deposited in a study registry
and this repository was published after the analysis was complete, so no date
among the materials can be verified independently of the files themselves.

## What is here, and what is not

Here: the pipeline source (`src/`, `scripts/`), the frozen codebook, output
schema and coding prompts (`codebook/`), the configuration with credentials
replaced by environment-variable placeholders (`config/`), the study protocol
and analysis plan, the reliability report and every analysis output
(`data_main/05_reliability/`, `data_main/06_results/`), and the analytic
dataset of 1,635 videos (`data_main/07_share/analytic_dataset.csv`).

Not here, by design:

- **No credentials.** Every config ships `${ENV_VAR}` placeholders. Set
  `YOUTUBE_API_KEY` and the model keys in your environment or in a local
  `config/config.yaml`, which is git-ignored.
- **No video or audio.** The analytic dataset carries video identifiers, the
  codes and the derived measures only. Titles, descriptions, transcripts,
  thumbnails and extracted frames are withheld, so nothing of the original
  media is redistributed, in line with the YouTube API Services Terms of
  Service. Re-running stages 3 and 4 regenerates them locally from the
  identifiers.
- **No manuscript.** The paper is under journal review and its text is not
  published here.

> **Scope statement (carried from the protocol):** All findings describe
> *engagement*, not clinical efficacy. Nothing here assesses the therapeutic
> accuracy or safety of any video.

---

## Pipeline overview

The protocol maps onto six executable stages. Each stage reads the output of the
previous one from `data/` and writes a new artifact, so the run is resumable and
auditable.

| Stage | Script | Protocol section | Input → Output |
|------|--------|------------------|----------------|
| 0. Spec | *(this repo)* | Codebook finalization (mo 1–2) | `codebook/`, `config/` |
| 1. Retrieve | `scripts/01_retrieve.py` | Data source & search strategy | seed queries → `data/01_raw/videos.parquet` |
| 2. Screen | `scripts/02_screen.py` | Eligibility criteria | raw → `data/02_eligible/eligible.parquet` |
| 3. Extract | `scripts/03_extract.py` | Data extraction | eligible → frames + transcripts |
| 4. Code | `scripts/04_code.py` | VLM coding | frames+transcript → `data/04_coded/codes_<model>.parquet` |
| 5. Reliability | `scripts/05_reliability.py` | Reliability & validity | multi-model codes → reliability report |
| 6. Analyze | `scripts/06_analyze.py` | Statistical analysis | coded + metadata → models & figures |

Derived (non-VLM, computed) variables — silence-to-voice ratio, words/min,
engagement ratios, recency — are produced in `src/meditation_vlm/derived.py` and
merged before analysis.

---

## Research questions (from protocol)

- **RQ1 (landscape):** distribution of techniques & audiovisual features.
- **RQ2 (association):** which meditation-specific features predict engagement,
  adjusting for length, channel size, recency.
- **RQ3 (moderation):** do feature–engagement associations differ by technique?
- **RQ4 (validity):** how reliable is VLM coding (inter-model, test-retest,
  prompt sensitivity, human subsample)?

Pre-specified hypotheses: **H1** synchronized on-screen breathing guide → higher
engagement; **H2** higher silence-to-voice ratio → higher engagement for
relaxation/sleep techniques only; **H3** feature effects vary by technique.

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml   # then fill in API keys
```

External tools used at runtime:
- **YouTube Data API v3** key (retrieval; quota-limited)
- **yt-dlp** + **ffmpeg** (frame sampling, audio for ASR)
- One or more **VLM** API keys (coding); ≥2 models required for inter-model
  agreement per the protocol.

Secrets are read from `config/config.yaml` (git-ignored) or environment
variables — never hard-coded.

---

## Reproducibility commitments (preregistration)

- All seed queries, retrieval window, and quota usage are logged to
  `data/01_raw/retrieval_manifest.json`.
- VLM prompts, JSON schema, model versions, and decoding settings (temperature)
  are version-controlled under `codebook/` and `config/`.
- The shared dataset will contain only **video identifiers and derived feature
  codes** — never redistributed video/audio.
- Codebook + analysis plan to be registered on OSF before the analytic dataset
  is locked.

## Status

Stage 0 (spec) is implemented. Stages 1–6 are built incrementally; see
`PROGRESS.md` for the current state.
