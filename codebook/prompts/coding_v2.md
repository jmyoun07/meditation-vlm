[Prompt-sensitivity variant — semantically equivalent rewording of coding_v1 for
RQ4 robustness checks. Same schema, same decision rules, different surface
phrasing. Hardened after the pilot: the output shape is pinned explicitly so no
model re-nests fields.]

Act as a neutral coder annotating objective audio-visual attributes of one guided
meditation video. Inputs: time-ordered sampled frames (more frequent near the
start) plus a transcript excerpt. Produce structured annotations of observable
attributes only.

Constraints:
- Annotate strictly what is visible/audible. Make no judgment about clinical
  accuracy, benefit, or safety — only how the session is presented.
- When an attribute cannot be determined from the inputs, pick the nearest
  "other"/"not_applicable" option and reduce confidence rather than guessing.
- Return exactly one JSON object conforming to the schema; emit no text outside it.

OUTPUT SHAPE — READ CAREFULLY:
- The JSON object must be FLAT: every coded variable is a TOP-LEVEL key whose
  value is the code itself (a string, boolean, number, or null).
- Do NOT wrap any field in an object. NEVER produce shapes like
  `"technique": {"value": ..., "confidence": ..., "evidence": ...}` — that is
  INVALID. Correct: `"technique": "body_scan"`.
- Confidence goes ONLY inside the single top-level "confidence" object, which
  has exactly these keys: technique, visual_breathing_guide,
  presenter_visibility, setting_imagery, background_sound_type (numbers 0-1).
- Evidence goes ONLY in the single top-level "evidence" string (<=600 chars).
- Do not add any keys beyond those defined in the schema.

Attribute definitions are identical to the primary codebook:
- technique (primary practice) + optional technique_secondary for mixed sessions.
- visual_breathing_guide = animated on-screen breathing pacer (not a static image).
- breathing_cadence_bpm = breaths/minute from one full pacer cycle, else null.
- visual_verbal_congruence = pacer vs spoken-cue match (concordant / discordant /
  not_applicable).
- presenter_visibility = human on screen / voiceover only / mixed
  (on_screen_presenter / visuals_only_voiceover / mixed).
- setting_imagery = studio / nature / abstract_animated / text_only / other.
- nature_imagery_present = any nature imagery (boolean).
- posture_or_mudra_shown = posture or hand position demonstrated (boolean).
- background_sound_type = none / ambient_nature / singing_bowls /
  binaural_isochronic_tones / music / other.
- onscreen_text_overlay = guiding text burned into frames, excluding captions.

Echo the given video_id as the top-level "video_id" string.
