"""Stage 1 — Retrieval via the YouTube Data API v3.

Protocol: "Data source and search strategy." For each technique we run its seed
queries, cap results per query before deduplication, fetch full metadata
(statistics, contentDetails, snippet, channel subscriberCount), deduplicate by
video id, and write a retrieval manifest recording every query string, the
retrieval date, ranking, and quota usage for reproducibility.

Requires a YouTube Data API v3 key (config.retrieval.youtube_api_key or env
YOUTUBE_API_KEY).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

import isodate
import pandas as pd
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config as cfg_mod

# Approx. quota cost per call (YouTube Data API v3 units), for manifest logging.
_COST_SEARCH = 100
_COST_VIDEOS = 1
_COST_CHANNELS = 1


def _client(api_key: str):
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _search_page(yt, query: str, region_code: str, page_token: str | None,
                 published_after: str | None, published_before: str | None):
    params = dict(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=50,
        regionCode=region_code,
        relevanceLanguage=None,
        safeSearch="none",
    )
    if page_token:
        params["pageToken"] = page_token
    if published_after:
        params["publishedAfter"] = published_after
    if published_before:
        params["publishedBefore"] = published_before
    return yt.search().list(**params).execute()


def _search_query(yt, query: str, max_results: int, region_code: str,
                  published_after, published_before, quota: dict) -> list[dict]:
    """Return ranked search hits (id + rank) for one query, capped."""
    hits: list[dict] = []
    page_token = None
    rank = 0
    while len(hits) < max_results:
        resp = _search_page(yt, query, region_code, page_token,
                            published_after, published_before)
        quota["units"] += _COST_SEARCH
        quota["search_calls"] += 1
        for item in resp.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if not vid:
                continue
            hits.append({
                "video_id": vid,
                "query": query,
                "api_rank": rank,
                "channel_id": item["snippet"]["channelId"],
            })
            rank += 1
            if len(hits) >= max_results:
                break
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return hits


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _videos_details(yt, ids: list[str]):
    return yt.videos().list(
        part="snippet,contentDetails,statistics,status",
        id=",".join(ids),
        maxResults=50,
    ).execute()


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _channels_details(yt, ids: list[str]):
    return yt.channels().list(
        part="snippet,statistics",
        id=",".join(ids),
        maxResults=50,
    ).execute()


def _chunks(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _duration_minutes(iso_duration: str) -> float | None:
    try:
        return isodate.parse_duration(iso_duration).total_seconds() / 60.0
    except Exception:
        return None


def fetch_metadata(yt, video_ids: list[str], quota: dict) -> pd.DataFrame:
    """Fetch full video + channel metadata for a list of ids."""
    rows: list[dict] = []
    for batch in _chunks(video_ids, 50):
        resp = _videos_details(yt, batch)
        quota["units"] += _COST_VIDEOS
        quota["video_calls"] += 1
        for v in resp.get("items", []):
            stats = v.get("statistics", {})
            content = v.get("contentDetails", {})
            snip = v.get("snippet", {})
            status = v.get("status", {})
            thumbs = snip.get("thumbnails", {})
            thumb_url = (thumbs.get("high") or thumbs.get("medium")
                         or thumbs.get("default") or {}).get("url")
            rows.append({
                "video_id": v["id"],
                "title": snip.get("title"),
                "description": (snip.get("description") or "")[:1500],
                "thumbnail_url": thumb_url,
                "channel_id": snip.get("channelId"),
                "channel_title": snip.get("channelTitle"),
                "published_at": snip.get("publishedAt"),
                "duration_iso": content.get("duration"),
                "session_length_min": _duration_minutes(content.get("duration", "")),
                "caption": content.get("caption"),                 # 'true'/'false'
                "closed_captions_available": content.get("caption") == "true",
                "view_count": _to_int(stats.get("viewCount")),
                "like_count": _to_int(stats.get("likeCount")),     # may be hidden
                "comment_count": _to_int(stats.get("commentCount")),
                "default_audio_language": snip.get("defaultAudioLanguage"),
                "made_for_kids": status.get("madeForKids"),
                "privacy_status": status.get("privacyStatus"),
                "live_broadcast": snip.get("liveBroadcastContent"),  # 'none'/'live'/'upcoming'
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Attach channel subscriber count + type heuristic.
    chan_ids = sorted(df["channel_id"].dropna().unique().tolist())
    chan_rows: list[dict] = []
    for batch in _chunks(chan_ids, 50):
        resp = _channels_details(yt, batch)
        quota["units"] += _COST_CHANNELS
        quota["channel_calls"] += 1
        for c in resp.get("items", []):
            cstats = c.get("statistics", {})
            chan_rows.append({
                "channel_id": c["id"],
                "subscriber_count": _to_int(cstats.get("subscriberCount")),
                "channel_video_count": _to_int(cstats.get("videoCount")),
                "subscriber_hidden": cstats.get("hiddenSubscriberCount"),
            })
    if chan_rows:
        df = df.merge(pd.DataFrame(chan_rows), on="channel_id", how="left")
    return df


def _to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def run(cfg: dict) -> pd.DataFrame:
    """Execute full retrieval per config; write raw table + manifest."""
    rcfg = cfg["retrieval"]
    api_key = rcfg.get("youtube_api_key")
    if not api_key:
        raise RuntimeError(
            "No YouTube Data API key. Set retrieval.youtube_api_key in "
            "config.yaml or the YOUTUBE_API_KEY environment variable."
        )
    yt = _client(api_key)
    seed = cfg_mod.load_seed_queries()
    languages = rcfg.get("languages", ["english"])
    max_per_query = int(rcfg.get("max_results_per_query", 200))
    region = rcfg.get("region_code", "US")
    pub_after = rcfg.get("published_after")
    pub_before = rcfg.get("published_before")

    quota = {"units": 0, "search_calls": 0, "video_calls": 0, "channel_calls": 0}
    all_hits: list[dict] = []
    query_log: list[dict] = []

    for lang in languages:
        for technique, queries in seed.get(lang, {}).items():
            for q in queries:
                hits = _search_query(yt, q, max_per_query, region,
                                     pub_after, pub_before, quota)
                for h in hits:
                    h["seed_technique"] = technique
                    h["language"] = lang
                all_hits.extend(hits)
                query_log.append({
                    "language": lang, "seed_technique": technique,
                    "query": q, "n_hits": len(hits),
                })

    hits_df = pd.DataFrame(all_hits)
    if hits_df.empty:
        raise RuntimeError("Retrieval returned no results — check key/quota/queries.")

    # Deduplicate by video id, keeping best (lowest) api_rank and recording how
    # many queries surfaced each video (a crude popularity/centrality signal).
    surfaced = (hits_df.groupby("video_id")
                .agg(n_queries_surfaced=("query", "nunique"),
                     seed_techniques=("seed_technique", lambda s: sorted(set(s))),
                     best_api_rank=("api_rank", "min"))
                .reset_index())
    dedup_ids = surfaced["video_id"].tolist()

    meta = fetch_metadata(yt, dedup_ids, quota)
    raw = meta.merge(surfaced, on="video_id", how="left")

    # Engagement ratios (NaN-safe; like_count may be hidden -> None).
    raw["like_rate"] = raw["like_count"] / raw["view_count"]
    raw["comment_rate"] = raw["comment_count"] / raw["view_count"]

    out = cfg_mod.data_path(cfg, "01_raw", "videos.parquet")
    raw.to_parquet(out, index=False)

    manifest = {
        "run_label": cfg.get("run", {}).get("label"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "extraction_date_config": cfg.get("run", {}).get("extraction_date"),
        "languages": languages,
        "region_code": region,
        "max_results_per_query": max_per_query,
        "published_after": pub_after,
        "published_before": pub_before,
        "queries": query_log,
        "n_hits_total": int(len(hits_df)),
        "n_unique_videos": int(len(raw)),
        "quota_usage": quota,
    }
    man_path = cfg_mod.data_path(cfg, "01_raw", "retrieval_manifest.json")
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    print(f"[retrieve] {len(raw)} unique videos -> {out}")
    print(f"[retrieve] quota ~{quota['units']} units -> manifest {man_path}")
    return raw
