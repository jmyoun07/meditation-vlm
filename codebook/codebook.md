# A Priori Codebook (v0.1)

Operationalization of Table 1 of the protocol. This is the preregisterable
coding manual. Each variable lists: its **role**, **how it is obtained**
(VLM-coded vs computed-from-transcript vs metadata), allowed **values**, the
**operational definition**, and the **reliability metric** used in RQ4.

Two obtaining methods matter for validity:
- **VLM-coded** — judged by the vision-language model from sampled frames +
  transcript. Subject to inter-model agreement, test-retest, prompt sensitivity.
- **Computed** — deterministic from transcript timestamps or metadata. Not a VLM
  judgment; reliability is mechanical (reported but not part of agreement panel).

Reliability metric key: **α** = Krippendorff's alpha (categorical/ordinal);
**ICC** = intraclass correlation (continuous); **n/a** = deterministic.

---

## A. Independent variables — VLM-coded

### A1. `technique` *(nominal, VLM)*
The primary meditation technique demonstrated. Coded from frames + transcript
against the a priori taxonomy. Exactly one primary label; a `technique_secondary`
field is allowed for clearly mixed sessions.
- Values: `focused_attention_breath`, `body_scan`, `loving_kindness`,
  `open_monitoring_mindfulness`, `visualization_imagery`,
  `yoga_nidra_body_relaxation`, `movement_walking`, `other`.
- Reliability: **α** (nominal).

### A2. `visual_breathing_guide` *(binary, VLM)*
Presence of an on-screen animated breathing pacer (e.g., expanding/contracting
shape, dot moving along a path) intended to pace inhale/exhale.
- Values: `true` / `false`.
- Reliability: **α**.

### A3. `breathing_cadence_bpm` *(continuous, VLM; conditional on A2)*
If a visual breathing guide is present, the pacer's cadence in **breaths per
minute**, estimated from one full expand→contract cycle of the animation.
- Range: 2–20 bpm; `null` when A2 is false.
- Reliability: **ICC**.

### A4. `visual_verbal_congruence` *(nominal, VLM; conditional on A2)*
Agreement between the on-screen pacer cadence (A3) and the verbally cued
breathing rate.
- Values: `concordant`, `discordant`, `not_applicable` (no verbal cue or no
  pacer).
- Reliability: **α** (ordinal/nominal).

### A5. `presenter_visibility` *(nominal, VLM)*
Whether a human presenter appears on screen.
- Values: `on_screen_presenter`, `visuals_only_voiceover`, `mixed`.
- Reliability: **α**.

### A6. `setting_imagery` *(nominal, VLM)*
Dominant visual backdrop of the session.
- Values: `studio`, `nature`, `abstract_animated`, `text_only`, `other`.
- Reliability: **α**.

### A7. `nature_imagery_present` *(binary, VLM)*
Presence of nature imagery anywhere (independent of dominant setting).
- Values: `true` / `false`.
- Reliability: **α**.

### A8. `posture_or_mudra_shown` *(binary, VLM)*
Whether a seated/lying meditation posture or a specific hand position (mudra) is
demonstrated on screen.
- Values: `true` / `false`.
- Reliability: **α**.

### A9. `background_sound_type` *(nominal, VLM + audio cue)*
Dominant non-voice background sound.
- Values: `none`, `ambient_nature`, `singing_bowls`,
  `binaural_isochronic_tones`, `music`, `other`.
- Reliability: **α**.

### A10. `onscreen_text_overlay` *(binary, VLM)*
Presence of guiding **text overlays** burned into the video (distinct from
platform closed captions, which are metadata — see C-group).
- Values: `true` / `false`.
- Reliability: **α**.

---

## B. Independent / structural — computed from transcript

### B1. `silence_to_voice_ratio` *(continuous, computed)*
Proportion of session duration without spoken guidance, from transcript
timestamps: `1 − (sum of speech-segment durations / video duration)`.
- Range: 0–1. Requires word/segment-level timestamps (ASR) for accuracy;
  caption-only sources flagged `timing_source = captions`.
- Reliability: **n/a** (deterministic).

### B2. `voice_pacing_wpm` *(continuous, computed)*
Speaking rate in words per minute over **spoken** time:
`total spoken words / (total speech-segment minutes)`.
- Reliability: **n/a**.

### B3. `session_length_min` *(continuous, metadata)*
Video duration in minutes (ISO 8601 `contentDetails.duration`).
- Reliability: **n/a**.

---

## C. Contextual — metadata

### C1. `channel_type` *(nominal)*
- Values: `individual`, `organization`, `unknown`. Heuristic + VLM/branding cue;
  flagged for the human subsample.
### C2. `subscriber_count` *(count, metadata)* — channel subscriberCount.
### C3. `recency_days` *(count, computed)* — days between upload date and the
fixed extraction date.
### C4. `closed_captions_available` *(binary, metadata)* — caption track present.

---

## D. Dependent variables — engagement (metadata)

### D1. `like_rate` *(continuous, primary)* = `likeCount / viewCount`.
### D2. `comment_rate` *(continuous, primary)* = `commentCount / viewCount`.
### D3. `video_power_index` *(continuous, secondary)* — composite popularity
index from views and likes; exact formula fixed at preregistration and recorded
in `config/config.yaml` (`vpi_formula`).
### D4. `comment_completion_effect_signal` *(exploratory, LLM-coded)* — presence
of viewer comments indicating completion or self-reported effect (calm, sleep).
Treated as **audience expression, not clinical outcome**. Reported descriptively
only.

> **Measurement caveat (protocol):** The YouTube Data API does not expose
> per-video watch time or retention for third-party videos. True
> completion/retention is therefore *not* measured directly; D1–D3 are
> engagement proxies and D4 is an exploratory audience signal.

---

## Coding procedure notes

- **Frame sampling:** fixed rate across the session with **denser sampling at the
  opening segment** (engagement is most strongly shaped early). Exact rates in
  `config/config.yaml` (`extraction.frame_rate`, `extraction.opening_boost`).
- **Multi-model:** every video coded independently by **≥2 VLMs**; a third may
  adjudicate (RQ4). Model versions + temperature recorded per run.
- **Low-reliability handling:** any variable failing its preregistered agreement
  threshold (default α or ICC < 0.60, set in config) is reported as
  low-reliability and **excluded from confirmatory models**.
- **Missing data:** hidden like counts → listwise handling per preregistered
  rule; flagged not imputed silently.

## Version log
- v0.1 — initial operationalization from protocol Table 1. Thresholds and VPI
  formula to be frozen at OSF preregistration.
