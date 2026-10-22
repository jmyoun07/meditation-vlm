"""Stage 3 — Extraction of frames + transcript (protocol: Data extraction).

For each eligible video:
- Sample frames at a fixed rate, with denser sampling in the opening window
  (engagement is shaped early). Frames -> data/03_frames/<video_id>/*.jpg.
- Obtain a timestamped transcript: platform captions first (cheap, no download),
  else Whisper ASR on the audio (better word timing). Transcript ->
  data/03_transcripts/<video_id>.json as a list of {start,end,text} segments.

Requires OS tools: ffmpeg and yt-dlp. Whisper is optional (only when captions are
absent and ASR is requested).
"""

from __future__ import annotations

import json
import shutil
import os
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from . import config as cfg_mod


def _require(tool: str):
    if shutil.which(tool) is None:
        raise RuntimeError(
            f"'{tool}' not found on PATH. Install it (e.g. `brew install {tool}`)."
        )


def _frame_timestamps(duration_s: float, ec: dict) -> list[float]:
    """Compute sampling timestamps with an opening boost, capped."""
    base = max(1, int(ec.get("frame_rate_seconds", 30)))
    boost = max(1, int(ec.get("opening_boost_seconds", 5)))
    open_win = float(ec.get("opening_window_minutes", 2)) * 60.0
    cap = int(ec.get("max_frames_per_video", 40))

    ts: list[float] = []
    t = 0.0
    while t < min(open_win, duration_s):
        ts.append(round(t, 2))
        t += boost
    t = max(open_win, base)
    while t < duration_s:
        ts.append(round(t, 2))
        t += base
    ts = sorted(set(ts))
    if len(ts) > cap:  # evenly subsample to the cap, keeping the first frames
        keep_open = [x for x in ts if x < open_win][: cap // 2]
        rest = [x for x in ts if x >= open_win]
        step = max(1, len(rest) // max(1, cap - len(keep_open)))
        ts = keep_open + rest[::step]
        ts = sorted(set(ts))[:cap]
    return ts


# --- yt-dlp binary + format strategy -----------------------------------------
# The project venv is Python 3.9, which pins yt-dlp to 2025.10.14. That build
# can no longer download from YouTube: format 18 (muxed 360p) has been retired
# and the android/tv clients now fail with "page needs to be reloaded" or serve
# truncated files. A side venv on Python 3.11 carries a current yt-dlp; prefer
# it when present (override with $YTDLP_BIN).
def _ytdlp_bin() -> str:
    env = os.environ.get("YTDLP_BIN")
    if env and Path(env).exists():
        return env
    side = Path.home() / ".ytdlp-venv" / "bin" / "yt-dlp"
    return str(side) if side.exists() else "yt-dlp"


# Progressive/muxed formats are gone; request video-only + audio-only and let
# yt-dlp mux them. `None` = yt-dlp's own client rotation, which currently works.
_DL_CLIENTS = [None, "web_safari", "mweb", "ios", "tv"]
_DL_FMT = ("134+140/230+140/bv[height<=480][ext=mp4]+ba[ext=m4a]/"
           "bv[height<=480]+ba/18/b[height<=480]")


def _ytdlp_cmd(client, fmt: str, out: Path, url: str) -> list[str]:
    cmd = [_ytdlp_bin(), "-q", "--no-warnings", "--retries", "3",
           "--merge-output-format", "mp4"]
    if client:
        cmd += ["--extractor-args", f"youtube:player_client={client}"]
    return cmd + ["-f", fmt, "-o", str(out), url]


# Network/transcode children must never block the run indefinitely. Observed in
# the main run: a single yt-dlp call hung for >2h with no output and stalled the
# whole stage. Every child gets a wall clock; a timeout is treated as a failure
# for that video, which the caller already handles (next client, or 0 frames).
def _run_bounded(cmd: list[str], timeout: int) -> bool:
    try:
        subprocess.run(cmd, check=False, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.TimeoutExpired:
        print(f"[extract] TIMEOUT after {timeout}s: {cmd[0]} ...")
        return False


def _download(video_id: str, workdir: Path) -> tuple[Path | None, Path | None]:
    """Download a low-res video (for frames) and audio (for ASR) via yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    media_out = workdir / "media.mp4"
    for client in _DL_CLIENTS:
        _run_bounded(_ytdlp_cmd(client, _DL_FMT, media_out, url), timeout=600)
        # Require a plausibly-complete file (>200KB) to accept it.
        if media_out.exists() and media_out.stat().st_size > 200_000:
            break
        if media_out.exists():  # tiny/broken file — remove and try next client
            media_out.unlink()
    media = media_out if media_out.exists() else None
    return media, media  # same combined file serves frames + audio


def _sample_frames(video_path: Path, timestamps: list[float], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, ts in enumerate(timestamps):
        out = out_dir / f"frame_{i:04d}_{int(ts)}s.jpg"
        _run_bounded(
            ["ffmpeg", "-nostdin", "-y", "-ss", str(ts), "-i", str(video_path),
             "-frames:v", "1", "-q:v", "3", str(out)], timeout=120)
        if out.exists():
            saved.append(out)
    return saved


def _transcript_from_captions(video_id: str) -> list[dict] | None:
    """Fetch caption transcript. Supports both the legacy classmethod API and the
    newer instance API (``YouTubeTranscriptApi().fetch(...)``)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return None
    raw = None
    try:  # newer API (>=0.6.3): instance .fetch(), returns snippet objects
        raw = list(YouTubeTranscriptApi().fetch(video_id, languages=["en"]))
    except Exception:
        try:  # legacy API: classmethod .get_transcript(), returns dicts
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        except Exception:
            return None
    out = []
    for s in raw or []:
        if isinstance(s, dict):
            start, dur, text = s.get("start"), s.get("duration"), s.get("text")
        else:  # FetchedTranscriptSnippet with attributes
            start = getattr(s, "start", None)
            dur = getattr(s, "duration", None)
            text = getattr(s, "text", None)
        if start is None:
            continue
        out.append({"start": float(start),
                    "end": float(start) + float(dur or 0.0),
                    "text": text or ""})
    return out or None


def _download_audio(video_id: str, workdir: Path) -> Path | None:
    """Download media for ASR. Reuses the same client/format strategy as frame
    extraction; faster-whisper decodes the muxed mp4 directly."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    out = workdir / "audio.mp4"
    fmt = "140/ba[ext=m4a]/ba/" + _DL_FMT
    for client in _DL_CLIENTS:
        _run_bounded(_ytdlp_cmd(client, fmt, out, url), timeout=600)
        if out.exists() and out.stat().st_size > 200_000:
            break
        if out.exists():
            out.unlink()
    return out if out.exists() else None


def backfill_transcripts(cfg: dict, model_size: str = "base",
                         delay_s: float = 6.0) -> pd.DataFrame:
    """Transcribe (via faster-whisper) every eligible video that still lacks a
    transcript file. IP-block-immune alternative to platform captions. Loads the
    ASR model once and updates the extraction manifest in place. A delay between
    downloads avoids YouTube throttling rapid successive requests."""
    import time

    from faster_whisper import WhisperModel

    manifest = pd.read_parquet(cfg_mod.data_path(cfg, "03_extraction_manifest.parquet"))
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print(f"[asr] loaded faster-whisper '{model_size}'")

    first = True
    done_since_ckpt = 0
    for idx, r in manifest.iterrows():
        vid = r["video_id"]
        if not r.get("n_frames"):
            continue  # frame extraction failed — no point transcribing yet
        tpath = cfg_mod.data_path(cfg, "03_transcripts", f"{vid}.json")
        if tpath.exists():
            continue
        if not first:
            time.sleep(delay_s)  # space out requests to avoid throttling
        first = False
        with tempfile.TemporaryDirectory() as td:
            audio = _download_audio(vid, Path(td))
            if audio is None:
                print(f"[asr] {vid}: no audio; skipping")
                continue
            segs, info = model.transcribe(str(audio), language="en")
            segments = [{"start": float(s.start), "end": float(s.end),
                         "text": s.text} for s in segs]
        if not segments:
            print(f"[asr] {vid}: empty transcript")
            continue
        with open(tpath, "w", encoding="utf-8") as fh:
            json.dump({"video_id": vid, "timing_source": "asr",
                       "segments": segments}, fh, ensure_ascii=False)
        done_since_ckpt += 1
        print(f"[asr] {vid}: {len(segments)} segments ({info.duration/60:.1f}min)")

    # Deliberately NO manifest write here: the extraction stage may be running
    # concurrently and checkpointing the same parquet — two writers would clobber
    # each other. Transcript FILES are the durable state; coding_ready() and the
    # derived stage recompute transcript availability from disk.
    tdir = cfg_mod.data_path(cfg, "03_transcripts", "_probe.json").parent
    n_files = len(list(tdir.glob("*.json")))
    print(f"[asr] transcripts on disk now: {n_files} (+{done_since_ckpt} this run)")
    return manifest


def _transcript_from_whisper(audio_path: Path, model_name: str) -> list[dict] | None:
    """Single-file ASR helper. Prefers faster-whisper (the installed backend);
    falls back to openai-whisper if that's what the environment has."""
    size = model_name.replace("whisper-", "") or "base"
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(size, device="cpu", compute_type="int8")
        segs, _info = model.transcribe(str(audio_path), language="en")
        return [{"start": float(s.start), "end": float(s.end), "text": s.text}
                for s in segs] or None
    except ImportError:
        pass
    try:
        import whisper
    except Exception:
        return None
    model = whisper.load_model(size)
    result = model.transcribe(str(audio_path), word_timestamps=False)
    return [{"start": seg["start"], "end": seg["end"], "text": seg["text"]}
            for seg in result.get("segments", [])]


def extract_one(cfg: dict, row) -> dict:
    ec = cfg["extraction"]
    vid = row["video_id"]
    duration_s = float(row["session_length_min"]) * 60.0
    frames_dir = cfg_mod.data_path(cfg, "03_frames", vid)
    transcript_path = cfg_mod.data_path(cfg, "03_transcripts", f"{vid}.json")

    # Transcript: captions first (no download), else ASR.
    transcript = None
    timing_source = None
    if ec.get("prefer_captions", True):
        transcript = _transcript_from_captions(vid)
        if transcript:
            timing_source = "captions"

    audio_sample_path = None
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        video_path, audio_path = _download(vid, workdir)
        if transcript is None and audio_path is not None:
            transcript = _transcript_from_whisper(audio_path, ec.get("asr_model", "whisper-base"))
            timing_source = "asr" if transcript else None
        timestamps = _frame_timestamps(duration_s, ec)
        frames = _sample_frames(video_path, timestamps, frames_dir) if video_path else []
        # Save a short audio sample for (exploratory) audio-based
        # background_sound coding — pilot showed frames+transcript are not
        # enough (inter-model alpha 0.17). Taken from mid-session to skip intros.
        if audio_path is not None and ec.get("save_audio_sample", True):
            start = min(90.0, max(0.0, duration_s * 0.25))
            dur = min(60.0, max(10.0, duration_s - start))
            out = cfg_mod.data_path(cfg, "03_audio_samples", f"{vid}.m4a")
            _run_bounded(
                ["ffmpeg", "-nostdin", "-y", "-ss", str(start), "-t", str(dur),
                 "-i", str(audio_path), "-vn", "-acodec", "aac", "-b:a", "64k",
                 str(out)], timeout=180)
            if out.exists() and out.stat().st_size > 10_000:
                audio_sample_path = str(out)

    if transcript is not None:
        with open(transcript_path, "w", encoding="utf-8") as fh:
            json.dump({"video_id": vid, "timing_source": timing_source,
                       "segments": transcript}, fh, ensure_ascii=False)

    return {
        "video_id": vid,
        "n_frames": len(frames),
        "frames_dir": str(frames_dir),
        "transcript_path": str(transcript_path) if transcript is not None else None,
        "timing_source": timing_source,
        "has_transcript": transcript is not None,
        "audio_sample_path": audio_sample_path,
    }


def run(cfg: dict) -> pd.DataFrame:
    """Extract all eligible videos. Resumable: videos already present in the
    manifest with frames are skipped, and the manifest is checkpointed every
    few videos so a multi-day run survives interruption. A polite delay between
    downloads avoids YouTube throttling."""
    import time

    _require("ffmpeg")
    _require("yt-dlp")
    ec = cfg["extraction"]
    delay_s = float(ec.get("inter_video_delay_seconds", 4.0))
    checkpoint_every = int(ec.get("checkpoint_every", 10))

    eligible = pd.read_parquet(cfg_mod.data_path(cfg, "02_eligible", "eligible.parquet"))
    out = cfg_mod.data_path(cfg, "03_extraction_manifest.parquet")

    done: dict[str, dict] = {}
    if out.exists():  # resume: keep rows that already extracted frames
        prev = pd.read_parquet(out)
        for _, r in prev.iterrows():
            if r.get("n_frames", 0) and r["n_frames"] > 0:
                done[r["video_id"]] = r.to_dict()
        if done:
            print(f"[extract] resuming: {len(done)} videos already extracted")

    rows = list(done.values())
    todo = [row for _, row in eligible.iterrows() if row["video_id"] not in done]
    for i, row in enumerate(todo):
        try:
            rec = extract_one(cfg, row)
            rows.append(rec)
            print(f"[extract] ({i+1}/{len(todo)}) {row['video_id']}: "
                  f"{rec['n_frames']} frames, transcript={rec['timing_source']}")
        except Exception as e:
            rows.append({"video_id": row["video_id"], "n_frames": 0,
                         "frames_dir": None, "transcript_path": None,
                         "timing_source": None, "has_transcript": False,
                         "audio_sample_path": None, "error": str(e)})
            print(f"[extract] ({i+1}/{len(todo)}) {row['video_id']}: ERROR {e}")
        if (i + 1) % checkpoint_every == 0:
            pd.DataFrame(rows).to_parquet(out, index=False)
        if i < len(todo) - 1:
            time.sleep(delay_s)

    manifest = pd.DataFrame(rows)
    manifest.to_parquet(out, index=False)
    print(f"[extract] {len(manifest)} videos -> {out}")
    return manifest
