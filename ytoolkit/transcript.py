"""
Transcript extraction — pulled directly through yt-dlp instead of the
youtube-transcript-api package. That package's API has broken across
versions and YouTube fairly often rate-limits/blocks its request
pattern, which is why captions that clearly exist (manual or
auto-generated) would sometimes come back as "no transcript found."
yt-dlp already resolves caption tracks as part of normal metadata
extraction, so we reuse that instead of a second, less reliable path.
"""
from __future__ import annotations

import json
import re

import requests
import yt_dlp

from . import core

PREFERRED_EXTS = ["json3", "vtt", "srv3", "srv1", "ttml"]


def list_available_captions(url: str) -> dict:
    """Return which languages have manual vs. auto captions for a video."""
    with yt_dlp.YoutubeDL(core.base_opts({"noplaylist": True})) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "manual": sorted((info.get("subtitles") or {}).keys()),
        "auto": sorted((info.get("automatic_captions") or {}).keys()),
    }


def _pick_track(tracks: list[dict]) -> dict | None:
    for ext in PREFERRED_EXTS:
        for t in tracks:
            if t.get("ext") == ext:
                return t
    return tracks[0] if tracks else None


def _select_language(subs: dict, auto: dict, languages: list[str]):
    """Returns (lang, track_list, is_generated) or (None, None, None)."""
    for lang in languages:
        if lang in subs:
            return lang, subs[lang], False
    for lang in languages:
        if lang in auto:
            return lang, auto[lang], True
    # relaxed match e.g. "en" matching "en-US"
    for lang in languages:
        for k in subs:
            if k.startswith(lang):
                return k, subs[k], False
    for lang in languages:
        for k in auto:
            if k.startswith(lang):
                return k, auto[k], True
    if subs:
        k = next(iter(subs))
        return k, subs[k], False
    if auto:
        k = next(iter(auto))
        return k, auto[k], True
    return None, None, None


def _parse_json3(raw: str) -> list[dict]:
    data = json.loads(raw)
    segments = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        dur = ev.get("dDurationMs", 0) / 1000
        segments.append({"start": start, "duration": dur, "text": text})
    return segments


def _parse_vtt(raw: str) -> list[dict]:
    ts_re = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3}) --> "
        r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})"
    )

    def to_sec(ts: str) -> float:
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
        else:
            h, (m, s) = "0", parts
        return int(h) * 3600 + int(m) * 60 + float(s)

    segments = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        m = ts_re.search(lines[i])
        if m:
            start, end = to_sec(m.group(1)), to_sec(m.group(2))
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(re.sub(r"<[^>]+>", "", lines[i]).strip())
                i += 1
            text = " ".join(t for t in text_lines if t)
            if text:
                segments.append({"start": start, "duration": max(end - start, 0), "text": text})
        else:
            i += 1

    # de-duplicate consecutive repeated lines (common in auto-caption vtt "roll-up" style)
    deduped = []
    for seg in segments:
        if deduped and deduped[-1]["text"] == seg["text"]:
            continue
        deduped.append(seg)
    return deduped


def get_transcript(url: str, languages: list[str] | None = None,
                    with_timestamps: bool = False) -> dict:
    languages = languages or ["en"]

    with yt_dlp.YoutubeDL(core.base_opts({"noplaylist": True})) as ydl:
        info = ydl.extract_info(url, download=False)

    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    video_id = info.get("id")

    lang, tracks, is_generated = _select_language(subs, auto, languages)
    if not tracks:
        return {
            "video_id": video_id, "available": False,
            "reason": "This video has no manual or auto-generated captions in any language.",
            "segments": [], "text": "",
        }

    track = _pick_track(tracks)
    if not track or not track.get("url"):
        return {
            "video_id": video_id, "available": False,
            "reason": "Caption track metadata was found but no downloadable URL was returned by YouTube.",
            "segments": [], "text": "",
        }

    resp = requests.get(track["url"], timeout=30)
    resp.raise_for_status()

    if track.get("ext") == "json3":
        segments = _parse_json3(resp.text)
    else:
        segments = _parse_vtt(resp.text)

    if not segments:
        return {
            "video_id": video_id, "available": False,
            "reason": "Caption track was fetched but contained no parseable text.",
            "segments": [], "text": "",
        }

    if with_timestamps:
        lines = [f"[{_fmt_ts(s['start'])}] {s['text']}" for s in segments]
        text = "\n".join(lines)
    else:
        text = " ".join(s["text"] for s in segments)

    return {
        "video_id": video_id,
        "available": True,
        "language": lang,
        "language_code": lang,
        "is_generated": is_generated,
        "segments": segments,
        "text": text,
    }


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
