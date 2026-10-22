# Progress

Tracks implementation of the protocol pipeline. Updated as stages land.

## Stage 0 — Specification (codebook & config)  ✅ done
- [x] README with pipeline map
- [x] A priori codebook (`codebook/codebook.md`) from Table 1
- [x] Strict VLM output schema (`codebook/schema.json`)
- [x] Technique seed queries (`config/seed_queries.yaml`)
- [x] Eligibility rules (`config/eligibility.yaml`)
- [x] Config template + loader (`config/config.example.yaml`, `src/.../config.py`)

## Stage 1 — Retrieval (YouTube Data API v3)  ✅ done · ✅ pilot run
- [x] Search + metadata + dedup + manifest (`src/.../retrieval.py`)
- [x] Runner (`scripts/01_retrieve.py`)
- [x] Pilot retrieval RUN: 122 videos / 75 channels, ~1605 quota units.
      Note: only ~20% have captions -> Stage 3 will lean on Whisper ASR.

## Stage 2 — Screening / eligibility  ✅ code done · ⏳ needs keys to run
- [x] Deterministic metadata gates (`src/.../screening.py`)
- [x] VLM eligibility classifier (thumbnail + title/description, no download)
- [x] Human subsample flagging
- [x] Runner (`scripts/02_screen.py`)

## Stage 3 — Extraction (frames + transcript)  ✅ code done · ⏳ needs ffmpeg/yt-dlp
- [x] yt-dlp + ffmpeg frame sampling, opening-boosted (`src/.../extraction.py`)
- [x] Transcript via captions (youtube-transcript-api) / Whisper ASR fallback
- [x] Runner (`scripts/03_extract.py`)
- [ ] Install OS deps: `brew install ffmpeg yt-dlp`

## Stage 4 — VLM coding  ✅ code done · ⏳ needs keys to run
- [x] Pluggable provider interface — Anthropic (Claude) + OpenAI (GPT) (`src/.../vlm.py`)
- [x] Structured output validated against schema.json (`src/.../coding.py`)
- [x] >=2 models for inter-model agreement
- [x] Prompt-sensitivity variants (v1/v2); test-retest subsample
- [x] Runner (`scripts/04_code.py`)

## Stage 5 — Reliability  ✅ code done · ✅ logic tested
- [x] Krippendorff's alpha / ICC (`src/.../reliability.py`)
- [x] Test-retest, prompt sensitivity, human agreement
- [x] Low-reliability variable flagging
- [x] Derived vars (`src/.../derived.py`): silence ratio, wpm, recency, VPI
- [x] Runner (`scripts/05_reliability.py`)

## Stage 6 — Analysis  ✅ code done · ✅ logic tested
- [x] Fractional-logit GLMs for engagement rates (`src/.../analysis.py`)
- [x] Channel cluster-robust SEs, with HC1 fallback when clusters < params
- [x] technique×feature interactions (RQ3)
- [x] FDR control (Benjamini-Hochberg); effect sizes + CIs
- [x] Runner (`scripts/06_analyze.py`)

## Tests
- [x] `tests/smoke_test.py` — network-free validation of stages 5-6 on synthetic
      data. PASSES (derived, reliability metrics, RQ1-3 models all produce output).

## Environment notes
- Python 3.9.6 + venv at `.venv`; logic + retrieval + Gemini deps installed.
- ffmpeg 8.1.2 (brew) + yt-dlp 2025.10.14 (venv) INSTALLED — Stage 3 ready.
- Model route = FREE: Claude Opus 4.8 in-session (Claude Code / Max sub) +
  Gemini 2.0 Flash free-tier API. Second-model swap from OpenAI -> Gemini.
- Only remaining blocker: GOOGLE_API_KEY (Gemini free key) in config.yaml.

## Pilot: COMPLETE ✅  (see PILOT_RESULTS.md)
- 122 retrieved → 30 screened → 29 coded by both models → reliability + analysis.
- Visual report published as artifact (pilot_report.html in scratchpad).

## Post-pilot hardening: DONE ✅
- coding_v2.md output shape pinned (Gemini nesting fix)
- reliability.py distinguishes not_assessable (no variance) from low_reliability
- extraction.py: audio samples saved (data/*/03_audio_samples), resume +
  checkpoint + inter-video delay for multi-day runs
- config.main.yaml: main-run profile, data_dir=data_main (pilot data preserved)

## MAIN RUN (in progress)
- [x] Stage 1 retrieval: 2,641 unique videos (1,949 in 2-60min window),
      quota 8,273 units → data_main/01_raw/
- [ ] Stage 2 screening (~2,300 Gemini calls) — awaiting free-vs-paid decision
- [ ] Stage 3 extraction (~2,000 videos, multi-day background, resumable)
- [ ] Stage 4 coding — awaiting Claude route decision (in-session vs API batches)
- [ ] Stages 5-6 reliability + analysis

## 2026-09-14 — extraction unblocked (yt-dlp staleness, not a bot block)

Frame extraction had stalled at 1,278/1,769 videos. The visible symptom was the
earlier `Sign in to confirm you're not a bot` message, so the run was paused.
On re-probe the block was gone, but extraction still returned `0 frames` for
every video. Root cause was different:

- the project venv is Python 3.9 → yt-dlp pinned at **2025.10.14**;
- YouTube has since retired progressive format **18**, so the configured format
  string resolved to nothing;
- `tv` / `web_safari` clients now fail with *"The page needs to be reloaded"*,
  and `android` returns a truncated 262-byte file (GVS PO token required).

**Fix.** `~/.ytdlp-venv` (Homebrew python3.11) carries a current yt-dlp
(2026.08.19). `extraction.py` gained `_ytdlp_bin()` (prefers the side venv,
overridable with `$YTDLP_BIN`) and now requests video-only + audio-only streams
muxed by yt-dlp:
`134+140/230+140/bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/18/b[height<=480]`
with `--merge-output-format mp4`, client list `[None, web_safari, mweb, ios, tv]`.
Verified: `2iH_gqDaEv8` → 24 frames.

The four videos processed during the broken window were written with
`n_frames = 0`; the resume logic only retains rows with `n_frames > 0`, so they
are retried automatically — no manifest pollution.

`scripts/extract_watcher.sh` now supervises extraction: it probes YouTube with a
single metadata-only request, backs off 45 min while blocked and 90 min if a
block appears mid-run, and stops when every eligible video has frames.

## 2026-09-14 — mid-study self-review (are we on track for the paper?)

Run at n=738 dual-coded videos / N=1,201 in the analytic frame / 512 channels.
Confirmatory **outcome** estimates were deliberately NOT inspected, so the
preregistration can still be amended without peeking.

### Healthy
- **Inter-model agreement (Krippendorff α, n=738 overlap)** is strong for 7/9
  variables: technique .90, nature_imagery .90, posture_or_mudra .86,
  setting_imagery .82, visual_breathing_guide .82, visual_verbal_congruence .82,
  presenter_visibility .77. All clear the preregistered .60 gate.
- **RQ1** is well powered: 8 technique categories with a wide spread
  (visualization 437, breath 365, metta 291, body-scan 290, yoga-nidra 277,
  open-monitoring 167, walking 87, other 25).
- **H2's predictor** (silence_to_voice_ratio) has good variance on the
  transcript-bearing sample: n=1,203, mean .169, sd .169.
- Stages 5 and 6 execute end to end: 32 RQ2 terms, 228 RQ3 terms, channel
  cluster-robust SEs (512 clusters, no HC1 fallback).

### Two bugs found and fixed
1. **`silence_to_voice_ratio` fabricated H2's predictor.** With no transcript,
   `segments=[]` → speech 0 → ratio **1.0**, scoring 566 videos (32% of the
   corpus) as "100% silence" instead of missing. Fixed: no segments → `None`.
2. **`breathing_cadence_bpm` was mislabelled "low reliability."** Its ICC is
   `None` because the variable is null wherever no on-screen pacer exists
   (2.7% non-null), i.e. *not estimable*, not *disagreed on*. The three-state
   flag now separates `no_variance` from `insufficient_overlap`, and reports
   `n_observations`.

### Live risk to the headline hypothesis — H1
`visual_breathing_guide` is **true for 32/1,201 videos (2.7%)** at consensus;
`visual_verbal_congruence` is non-N/A for 33. Extrapolated to the full sample
that is ~45 positives. The GLM already emits overflow/separation warnings on
these terms. H1 as specified is a **rare-event** problem: ordinary fractional
logit will give unstable estimates, and FDR across 32 RQ2 terms will bury it.

Options, to decide **before** any outcome analysis is run:
- **(a) Amend the preregistration now** (dated amendment, legitimate while
  outcomes are unseen) to estimate H1 with **Firth penalized likelihood** and
  report profile-likelihood CIs, keeping ordinary logit as a sensitivity.
- **(b) Keep H1 exactly as written** and report it as underpowered with exact
  CIs and the observed prevalence.
- **(c) Add a pre-specified secondary composite** ("any visual pacing cue")
  with greater prevalence, reported alongside the primary test.

### Excluded by the preregistered gate (as expected)
- `background_sound_type` (α .30) — neither model receives audio (input
  symmetry, §4.5), so both are guessing. Correctly excluded; must be reported
  as a limitation, not as a coded finding.
- `onscreen_text_overlay` (α .38) — definitional drift between branding/title
  cards and guiding text. Excluded; the cause should be named in Limitations.

### Still outstanding for the paper
- Claude-side coding: 738/1,201 ready videos (session-limited, resumes 14:20).
- Extraction: 96/516 of the remaining backlog recovered after the yt-dlp fix.
- 566 videos have no transcript yet and therefore cannot enter the analytic
  frame; ASR backfill governs the final N.
- `ANALYSIS_PLAN.md` still carries `[fill]` placeholders (authors,
  retrieval dates, power analysis, model version strings, commit hash).
- No manuscript skeleton exists yet.

## 2026-09-14 — Amendment 1 implemented + three analysis bugs fixed

Following the self-review, the user chose option (a): amend the preregistration
to estimate H1 with Firth penalized likelihood.

**Firth estimator** (`src/meditation_vlm/firth.py`). Jeffreys-prior penalty on
the binomial-logit score, so it is valid for the fractional (quasi-binomial)
responses used here, with step-halving for stability under separation and
profile-likelihood CIs. Validated on synthetic data: recovers a true β=0.80 as
0.747 at 2.7% predictor prevalence, and returns a finite estimate (6.31,
CI 4.34–11.15) in a fully separated case where ML diverges. Wired into
`analysis.run()` as `h1_firth.csv`; the unpenalized RQ2 term for the same
feature is retained as the amendment's sensitivity analysis.

**Three bugs found while dry-running the analysis stage** — all would have
corrupted the paper:

1. **RQ2 sample collapse, N=1,201 → 34.** `breathing_cadence_bpm` is observed
   for 2.8% of videos and the GLM deletes rows listwise, so it silently took the
   whole model down with it, producing "Singular matrix". `_excluded_vars()` was
   only reading `low_reliability_excluded` and ignoring `not_assessable`; both
   now exclude, plus a hard 50%-coverage guard and a warning whenever a model
   loses half the sample.
2. **Near-collinear nested predictor.** `visual_verbal_congruence` is defined
   only when a breathing guide exists, so it duplicates the H1 feature. Removed
   from the main model; reported in the guide-present subsample.
3. **Wrong family for `video_power_index`.** VPI ranges 0–32, but the
   fractional-logit path filtered outcomes to [0, 1], leaving **3 of 1,201
   rows**. Non-proportion outcomes now take a Gaussian/identity fit; the family
   is recorded per term.

After the fixes: N=1,201, RQ2 42 terms across three outcomes, RQ3 196 terms,
H1 2 Firth terms, no sample-loss warnings. Filed as Amendments 1–3.

**Also fixed:** extraction hung for ~2h on an unbounded `yt-dlp` child. All
`yt-dlp`/`ffmpeg` subprocesses now run through `_run_bounded()` (600s download,
120s frame, 180s audio); a timeout is treated as a per-video failure.

## 2026-09-14 — codebook gap: rapid breathwork exceeds the cadence scale

Two videos in one batch (`fCD57zIPs-s`, `fgQhn7L4dZs`) carry an on-screen pacer
for **breath of fire / "double speed" breathwork**, whose rate is well above the
schema's `breathing_cadence_bpm` range of 2–20. The schema has no valid
representation for it, so a coder can only cap at 20 — which invents a boundary
value and would drag the cadence distribution downward.

**Rule applied:** an out-of-range pacer rate is recorded as `null` (schema-valid,
meaning "not estimable on this scale") with an extra `cadence_out_of_range: true`
flag, never capped. `breathing_cadence_bpm` is already `not_assessable` and out
of the confirmatory models, so this affects RQ1 descriptives only.

**For the manuscript:** report this as a measurement limitation — the cadence
scale was designed for slow-breathing pacers and cannot represent rapid
breathwork, a genre that does occur in the corpus.

**Cadence-scale note (update).** The out-of-range rule now also fires at the LOW
end: `lEzaFx8k7Ew` runs a 4-7-8 pacer at ~1.9 bpm, below the schema minimum of 2.
The 2-20 bpm window is therefore too narrow on both sides — rapid breathwork
above it, long-exhale 4-7-8 patterns below it. Both are recorded as `null` with
`cadence_out_of_range: true`, never clipped to a boundary.

## 2026-09-17 — the registered instrument was never the instrument we ran

Writing the Methods section forced a check that should have happened earlier:
what does the preregistration say the coders are, and what are they actually?

- §4.5 prose: Claude Opus 4.8 + **Gemini 2.5 Flash**.
- `config/config.example.yaml`, listed in §8 as registered material: Claude
  Opus 4.8 + **OpenAI GPT-4o**.
- What ran: Claude Opus 4.8 **in-session** + **`gpt-5.6-sol` via the Codex CLI**,
  with Gemini 2.5 Flash kept only for stage-2 eligibility screening.

The registration contradicted itself *and* neither version matched the run. The
cause is the $0 constraint — corpus-scale coding does not fit any free API tier,
so both raters moved onto subscriptions the user already has. That is a
resourcing decision with no outcome dependence, but it changes the measurement
instrument, so it is filed as **Amendment 4** rather than quietly written up.

Three consequences the manuscript has to carry, not bury:
1. RQ4 agreement is Claude↔Codex, so the pilot's Claude↔Gemini α values
   (including `background_sound_type` α = 0.17) do not transfer.
2. `temperature = 0` is enforced for rater 2 and the screening classifier but
   **not** for rater 1 — an interactive session exposes no temperature control.
   The 10% test–retest arm is the honest check on that, and gets reported.
3. Rater 1 runs inside a session that also does engineering work. Outcome
   blinding is real but procedural (the coding prompt carries frames+transcript
   only, never engagement metrics), not architectural. Declared as such.

## 2026-09-17 — codex_watcher.sh: stop hand-restarting the second rater

Stage 4 aborts after 5 consecutive quota errors, which is correct behaviour but
means the Codex rater stalls silently every time the ChatGPT usage window closes;
twice now it sat dead for hours before anyone noticed. `scripts/codex_watcher.sh`
re-runs the stage, compares ok-row counts before and after, sleeps 60 min when a
pass makes no progress (the window is still shut — retrying sooner only burns
failed calls against it), and exits on its own once every coding-ready video has
a Codex row. Same shape as `extract_watcher.sh`.

## 2026-09-17 — why `onscreen_text_overlay` failed its gate (and why we did not fix it)

A10 defines the variable as "guiding **text overlays** burned into the video
(distinct from platform closed captions, which are metadata)". The only contrast
the definition draws explicitly is *against platform captions*. Channel branding,
burned-in title cards, watermarks and "do not listen while driving" disclaimers
fall in a gap the rule never resolves.

The coding logs show the split happening in plain sight — raters coding the same
class of stimulus in opposite directions while *stating in their own evidence
strings* that the text was branding, not guidance:

- `uI0oMw-ncZo` → `true`, evidence: "(title/disclaimer, not in-practice guidance)"
- `uTN29kj7e-w` → `true`, evidence: "opening title cards ..., not guiding text"
- `u0jFKzAW-Ww` → `false`, evidence: "intro branding, not guiding overlay"
- `tw7XBKhZJh4` → `false`, evidence: "Burned-in text is title/branding, not guidance"

So the α ≈ .38 is a **specification failure in the codebook, not a perception
failure in the models** — a distinction worth making in the paper, because it
points at the fix: code burned-in text on two axes (presence; whether it guides
the practice) instead of one.

**Not fixed mid-run, deliberately.** The codebook is frozen preregistered
material. Tightening A10 now would make the ~1,000 already-coded videos
incomparable to the rest and would be a post-hoc rule change on a variable whose
reliability we have already looked at. It goes in Limitations and in the
recommendations for a revised instrument.

## 2026-09-17 — H2's predictor was still fabricated, one level deeper

The earlier fix made `silence_to_voice_ratio` return `None` when a video has **no
transcript**. It turns out a transcript can exist and still carry no speech: on
wordless or music-only videos the ASR emits timed segments whose text is a bare
`"."`. Those segments have real start/end stamps, so they sailed past the
`if not segments` guard and produced a ratio computed from timestamps that
represent no speech at all.

Scale: **15 of 1,635** coding-ready transcripts have zero word-like tokens; 25
have fewer than 20. Small, but they are systematically the *non-verbal* videos —
exactly the high-silence tail H2 is about. And the error mostly ran the wrong
way: `Htr_SGGuelg` and `qLbt6KzsFo8` scored **0.0 silence** and `LcBTCrpXHRk`
0.006 — wordless videos entering H2 as the most talkative in the corpus.
`voice_pacing_wpm` was equally wrong, counting `"."` tokens as words.

**Fix:** `_real_words()` counts only tokens containing a letter or digit. A
transcript with zero of them yields `None` for both variables. We cannot
distinguish an ASR failure from a genuinely wordless video from the transcript
alone, and neither is measurable, so both are missing rather than guessed.
Observed `silence_to_voice_ratio` goes 1,635 → 1,620.

Not a preregistration matter — it is a measurement bug in a computed variable,
fixed before any H2 estimate was inspected, changing no analytic decision rule.

**Related, not acted on:** `ulJC1IOsbxg` (one of the 15) looks like a genuine
eligibility false positive — static album art, no spoken guidance, i.e. the
"music-only with no guidance" case the screener is supposed to exclude. Post-hoc
exclusion of individual videos is not ours to make; the registered human-verified
subsample is the mechanism for estimating the screener's error rate, and that
rate gets reported.

## 2026-09-17 — the frame-sampling rate caps measurable breathing cadence (Nyquist)

A coder working `unHk50NBsns` spotted the real reason cadence behaves badly:
frames are sampled every **5 s** through the opening window and every **30 s**
after it. A breathing pacer is a periodic signal with period `T = 60 / bpm`.
Resolving it needs a sampling interval below `T/2`, so:

| sampling interval | resolvable period | resolvable cadence |
|---|---|---|
| 5 s (first 2 min)  | ≥ 10 s | **≤ 6 bpm** |
| 30 s (thereafter)  | ≥ 60 s | ≤ 1 bpm |

Anything faster aliases. On that video the coder found a clean sinusoid in the
pixel data and correctly refused to report a rate, noting that 13.1 s, 8.1 s and
3.6 s periods all fit the same 5 s-sampled frames.

**So cadence values above ~6 bpm in this dataset are not measurements of the
pacer's motion.** They are inferences from a different source — a transcript
count (`uttz-TKTQF4`: ~30 breaths over 110 s → "16 bpm", self-rated confidence
0.3) or an on-screen breath counter (`tybOi4hjZFQ`: 18 bpm read off a counter).
Those are defensible readings, but they are a different instrument from
frame-based observation, and mixing them makes the variable heterogeneous in
kind, not just noisy.

This explains the variable's status better than rarity does: `breathing_cadence_bpm`
is `not_assessable / insufficient_overlap` because the raters are often measuring
different things when they do report a number.

**Not fixable post hoc** — re-extracting 1,769 videos at a cadence-resolving
frame rate (≥2 Hz) is a different study, and the frame schedule is frozen
preregistered material. It goes in Limitations with the arithmetic shown, and in
the recommendations: a study that wants cadence must sample frames at a rate
chosen from the cadence range it intends to measure, or read the pacer from the
video stream directly rather than from sampled stills.

## 2026-09-18 — the Codex block was never an hourly window

`codex_watcher.sh` ran 4 passes overnight, every one `+0 rows`, then died with the
machine when `caffeinate` expired. Reading the error text actually stored in the
parquet rather than trusting the log's own "QUOTA/RATE" label:

> ERROR: You've hit your usage limit. ... or try again at **Sep 19th, 2026 6:32 PM**.

So it is not a rolling hourly window at all — the ChatGPT allowance is exhausted
until a fixed timestamp ~31 hours out. A 60-minute retry would have burned ~30
pointless passes against a door that does not open.

**Fix:** the watcher now parses `try again at <date>` out of the stored error and
sleeps until that time (+2 min), capped at 36 h so a bad parse cannot park the
loop forever; it falls back to 60 minutes only when no reset time is given.
Verified against the live error: parsed 112,393 s ≈ 31 h. `caffeinate` restarted
with a 48 h window so the machine stays awake across the whole wait.

**Consequence for the study:** rater 2 is frozen at **1,467 / 1,635** until
2026-09-19 18:32. The Claude arm is unaffected and continues. Dual coding cannot
complete — and therefore neither can the final reliability and analysis run —
before that timestamp.

## 2026-09-18 — the corpus is not an English-language corpus

A coder flagged `vOHy9_IqBQY` as a Hindi session with "garbled Hindi ASR". Checking
the assumption rather than the video: `config/eligibility.yaml` has **no language
gate at all**. "English" in the registration describes the *seed queries*, not the
videos. `default_audio_language` across the 1,635 coding-ready videos:

| declared | n | share |
|---|---|---|
| English (`en*`) | 1,181 | 72.2% |
| undeclared | 422 | 25.8% |
| non-English (de, hi, es, it, nl) | 30 | 1.8% |
| `zxx` (no linguistic content) | 1 | — |
| `ase` (American Sign Language) | 1 | — |

Small, but it has to be stated correctly in Methods: this is "videos returned by
English seed queries in the US region," not "English-language videos." For those
30, an English-leaning `base` ASR yields a garbled transcript, so both
transcript-derived variables and the coders' own reading of the transcript are
degraded — and a quarter of the corpus declares no language at all, so we cannot
even count the true figure.

Worth noting the `ase` case on its own: a signed meditation carries full visual
guidance and no speech, which the codebook's speech-centric variables cannot
represent.

**Checked and ruled out:** the 15 zero-word transcripts from yesterday's fix are
*not* the non-English ones — they are 4 English and 11 undeclared. The two
problems are independent, so the `_real_words()` fix is not masking a language
issue.

Not acted on beyond reporting: adding a language filter now would be a post-hoc
change to the frozen eligibility rules on a corpus already three-quarters coded.

## 2026-09-20 — rater 2 (Codex) is COMPLETE

`codex_watcher.sh` rode out the 31-hour block and finished on its own:

```
2026-09-20 00:23:32 pass 7 starting (ok rows=2411, remaining=1)
2026-09-20 00:40:11 pass 7 done: +28 rows, remaining=0
2026-09-20 00:40:11 DONE
```

**`codex_cli:gpt-5.6-sol` has coded all 1,635 coding-ready videos** (2,439 ok
rows including the prompt-sensitivity variant). The reset-time parser earned its
keep: the fixed 60-minute retry it replaced would have spent that window on ~30
failed passes and still needed a hand restart afterwards.

The study is now single-threaded on the Claude arm: **1,078 / 1,635**, 557 to go.
Nothing else blocks the final reliability and analysis run.

Note the watcher's pass 6 line — "no reset time given, sleeping 60m" — that is
the fallback path working as designed: once the provider stopped restating a
reset timestamp, the loop dropped back to short retries and caught the window
17 minutes into the next hour.

## 2026-09-21 — an accidental duplicate became a test-retest data point

`session_coding.pending()` excludes videos already *merged*, not videos currently
*in flight*, so `AdHuY-Fi0LQ` reappeared in a NEXT list while its first agent was
still running and got coded twice. Same model, same prompt, independent runs —
which is exactly the design of the pre-registered test-retest arm (replicate 1 vs
2). Rather than discard it, the second coding is stored as **replicate 2**.

The two runs are a small but pointed result:

| variable | run 1 | run 2 |
|---|---|---|
| technique, secondary, guide, cadence, congruence, presenter, setting, nature, posture, overlay | *identical* | *identical* |
| `background_sound_type` | `music` | `none` |

**10 of 11 variables reproduced exactly; the one that moved is the one already
failing the reliability gate.** That matters for the write-up: it shows
`background_sound_type`'s instability is not only *between* the two models but
*within* one model across runs, which is what you would expect if the raters are
inferring an unheard channel from visual and verbal cues rather than observing
it. Both runs rated their own confidence on that variable at 0.25-0.35, so the
instrument was honest about it.

**Provenance noted for the final test-retest set:** this video entered
replicate 2 by scheduling accident, not by the pre-registered random 10% draw.
It must be reported as an opportunistic addition, not folded silently into the
random subsample.

**Fix going forward:** build each batch from `pending()` *minus* the IDs still in
flight.

## 2026-09-22 — when the sound source is visible, `background_sound_type` stops guessing

`Ap6AkhvTKfM` is one of the 15 wordless-transcript videos, and the coder handled
it correctly: it stated the transcript carried no words and coded from frames
alone. But the interesting part is its `background_sound_type`.

Almost every other video in this corpus gets that variable rated at **0.2-0.4
self-confidence** — the raters are inferring an unheard channel from visuals and
narration. Here the coder gave **0.75**, because the frames show a man seated
behind a semicircle of lit crystal singing bowls, striking them with a mallet.
The sound's *source* is on screen, so the code is an observation, not a guess.

That is a clean illustration of the input-asymmetry diagnosis for the paper: the
variable is not intrinsically unreliable, it is unobservable **given these
inputs**. Where the inputs happen to contain the answer — a visible instrument,
or an explicit line in the narration ('the music will continue for just a bit',
`uKytADx_OQc`, conf 0.75) — confidence and presumably accuracy rise sharply.

**Reporting consequence:** rather than only saying `background_sound_type` failed
its gate, the Results can show that the rater's own confidence on it is bimodal
and tracks whether the sound source is visible or named. That converts a bare
"this variable failed" into evidence about *why*, and into a concrete instrument
fix (give the coder audio) rather than a shrug.

## 2026-09-22 — flag-semantics slip caught on `cadence_out_of_range`

`CTS6E_0oAJg` came back with `visual_breathing_guide: false` **and**
`cadence_out_of_range: true` — a contradiction. The flag means "a pacer exists
but its rate falls outside the codebook's 2-20 bpm scale"; it is the evidence
base for the Limitations claim that the scale is too narrow. This video has no
pacer at all: the coder's own evidence says the centred circle is a 15-minute
session countdown, "a timer, not a breathing pacer". Cadence is null here because
the *feature is absent*, not because its rate is unrepresentable.

Merged with the flag dropped and everything else intact. That is not overriding
the coder's judgement — it is removing a flag that contradicts the coder's own
prose.

Audited the rest: **all 6 previously flagged rows** (`fgQhn7L4dZs`,
`jaX8m9UJ64Q`, `lEzaFx8k7Ew`, `sJ3YzmDiIzA`, `u8j7Ir_cg0M`, `A-bm1KKOCvU`) have
`visual_breathing_guide = True`, so the flag is clean. Had this one gone in
unchecked it would have inflated the out-of-range count by 1/7 on a variable
whose whole job is to support a measurement-limitation claim.

**Invariant to keep checking before the final run:** `cadence_out_of_range`
implies `visual_breathing_guide == True`.

**Language addendum (2026-09-22).** The non-English ASR failure mode is now
*observed*, not inferred. `D5rO5e6ILmo` (declared Spanish) did not merely garble:
the pipeline **machine-translated the Spanish audio into broken English and then
reverted to Spanish mid-transcript** ('repugio' for refugio). So the transcript
for these 30 videos is not simply noisy — it is partly a translation artefact,
which is a different and worse problem for any transcript-derived variable.
The coder flagged it and dropped `technique` confidence to 0.72. Worth stating
precisely in Limitations rather than as generic "ASR is unreliable for
non-English".
