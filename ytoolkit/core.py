"""
Core operations built on yt-dlp: metadata lookup, playlist listing,
and local mp3/mp4 download. Everything here runs 100% locally on your
machine, for your own personal use.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import yt_dlp

from . import config


def base_opts(extra: dict | None = None) -> dict:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "skip_download": True,
    }
    if config.COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (config.COOKIES_FROM_BROWSER,)
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    if extra:
        opts.update(extra)
    return opts


def _fmt_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "00:00"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def get_video_info(url: str) -> dict:
    """Return key metadata for a single video."""
    with yt_dlp.YoutubeDL(base_opts({"noplaylist": True})) as ydl:
        info = ydl.extract_info(url, download=False)

    upload_date = info.get("upload_date")  # "YYYYMMDD"
    if upload_date:
        upload_date = _dt.datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "duration": info.get("duration"),
        "duration_str": _fmt_duration(info.get("duration")),
        "upload_date": upload_date,
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "tags": info.get("tags") or [],
        "categories": info.get("categories") or [],
        "description": info.get("description"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url"),
        "resolution": info.get("resolution"),
        "fps": info.get("fps"),
        "has_captions": bool(info.get("subtitles") or info.get("automatic_captions")),
    }


def get_playlist_info(url: str) -> dict:
    """Return metadata for every video in a playlist plus running totals."""
    with yt_dlp.YoutubeDL(base_opts({"extract_flat": "in_playlist"})) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") or []
    videos = []
    total_seconds = 0
    for e in entries:
        if e is None:
            continue
        dur = e.get("duration") or 0
        total_seconds += dur
        videos.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
            "duration": dur,
            "duration_str": _fmt_duration(dur),
            "view_count": e.get("view_count"),
            "channel": e.get("channel") or e.get("uploader"),
        })

    return {
        "playlist_title": info.get("title"),
        "playlist_id": info.get("id"),
        "video_count": len(videos),
        "total_duration": total_seconds,
        "total_duration_str": _fmt_duration(total_seconds),
        "videos": videos,
    }


# ---------------------------------------------------------------------------
# Download (mp3 / mp4) — LOCAL, personal-use only
# ---------------------------------------------------------------------------
def download(url: str, fmt: str = "mp4", quality: str = "best",
             output_dir: str | Path | None = None,
             progress_hook=None) -> list[str]:
    """
    Download a video (mp4) or extract audio (mp3) to your local disk.
    Works for a single video URL or a full playlist URL.

    Returns list of resulting file paths — read directly from yt-dlp's
    own postprocessor callback rather than guessed from the pre-download
    filename. Guessing (e.g. swapping the extension ourselves) breaks on
    titles that already contain a "." in them (a title ending in
    "...Details.htm" is a real example), so we let yt-dlp tell us what
    it actually wrote instead of predicting it.
    """
    out_dir = Path(output_dir) if output_dir else config.DOWNLOAD_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / "%(playlist_title|)s/%(title)s.%(ext)s")

    final_files: list[str] = []

    def _pp_hook(d: dict) -> None:
        if d.get("status") == "finished":
            fp = (d.get("info_dict") or {}).get("filepath") or d.get("filename")
            if fp:
                final_files.append(fp)

    hooks = [_pp_hook]

    opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "skip_download": False,
        "noplaylist": False,
        "ignoreerrors": True,
        "postprocessor_hooks": hooks,
    }
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    if fmt == "mp3":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:  # mp4
        height = {"best": None, "1080p": 1080, "720p": 720, "480p": 480}.get(quality)
        fmt_str = "bestvideo+bestaudio/best" if not height else \
            f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        opts.update({
            "format": fmt_str,
            "merge_output_format": "mp4",
        })

    opts = base_opts(opts)
    opts["skip_download"] = False

    fallback_files: list[str] = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        entries = info.get("entries") if info.get("entries") is not None else [info]
        for e in entries:
            if e is None:
                continue
            try:
                fallback_files.append(ydl.prepare_filename(e))
            except Exception:
                pass

    if final_files:
        # De-dupe while preserving order (postprocessor_hooks can fire more
        # than once per file across chained postprocessors).
        seen = set()
        deduped = []
        for f in final_files:
            if f not in seen:
                seen.add(f)
                deduped.append(f)
        return deduped

    # Nothing went through a postprocessor (e.g. a native mp4 that needed
    # no merge/extraction) — the pre-download filename is already correct
    # in that case since no extension swap was needed.
    return fallback_files
