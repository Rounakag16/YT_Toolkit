"""
Core operations built on yt-dlp: metadata lookup, playlist listing,
and local mp3/mp4 download.
"""
from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path
from typing import Any

import yt_dlp

from . import config

class YTDLPLogger:
    """Log all yt-dlp output to Render logs while collecting errors."""

    def __init__(self):
        self.errors: list[str] = []

    def debug(self, msg):
        print(f"[yt-dlp DEBUG] {msg}", flush=True)

    def info(self, msg):
        print(f"[yt-dlp INFO] {msg}", flush=True)

    def warning(self, msg):
        print(f"[yt-dlp WARNING] {msg}", flush=True)

    def error(self, msg):
        message = str(msg)
        self.errors.append(message)
        print(f"[yt-dlp ERROR] {message}", flush=True)

class DownloadError(RuntimeError):
    pass




def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def base_opts(extra: dict | None = None) -> dict:
    opts: dict[str, Any] = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": False,
        "skip_download": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "default"]
            }
        },
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
# Download (mp3 / mp4)
# ---------------------------------------------------------------------------
def download(url: str, fmt: str = "mp4", quality: str = "best",
             output_dir: str | Path | None = None,
             progress_hook=None) -> list[str]:
    """
    Download a video (mp4) or extract audio (mp3) to disk.
    Works for a single video URL or a full playlist URL.

    Both mp3 extraction and mp4 merging require ffmpeg. Without it,
    yt-dlp doesn't error loudly — it just leaves the raw per-stream
    download in place (e.g. a .webm audio track instead of .mp3, or
    separate video/audio files with no merged .mp4 ever produced). That
    silent degradation is what caused mismatched/missing files before,
    so we check up front and verify the result matches what was asked
    for, raising a clear error instead of quietly serving the wrong
    thing.
    """
    if not ffmpeg_available():
        raise DownloadError(
            "ffmpeg was not found on PATH. It's required for both MP4 "
            "merging and MP3 extraction — install it and make sure the "
            "`ffmpeg` command works in a new terminal, then try again. "
            "(macOS: brew install ffmpeg · Windows: winget install ffmpeg "
            "· Linux: apt install ffmpeg)"
        )

    out_dir = Path(output_dir) if output_dir else config.DOWNLOAD_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / "%(playlist_title|)s/%(title)s.%(ext)s")

    logger = YTDLPLogger()

    opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "skip_download": False,
        "noplaylist": False,

        # IMPORTANT:
        # Don't swallow the real yt-dlp exception while debugging.
        "ignoreerrors": False,

        # Send yt-dlp's complete logging through our logger.
        "logger": logger,

        # Make yt-dlp print its internal debug information.
        "verbose": True,
    }

    error_collector = _ErrorCollector()
    opts["logger"] = error_collector
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    expected_ext = "mp3" if fmt == "mp3" else "mp4"

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

    results: list[str] = []
    failures: list[str] = []

    print("=" * 70, flush=True)
    print("[YTOOLKIT DEBUG] Starting yt-dlp download", flush=True)
    print(f"[YTOOLKIT DEBUG] URL: {url}", flush=True)
    print(f"[YTOOLKIT DEBUG] Format: {fmt}", flush=True)
    print(f"[YTOOLKIT DEBUG] Quality: {quality}", flush=True)
    print(
        f"[YTOOLKIT DEBUG] yt-dlp version: "
        f"{yt_dlp.version.__version__}",
        flush=True
    )

    print(
        f"[YTOOLKIT DEBUG] Cookies configured: "
        f"{bool(config.COOKIES_FILE)}",
        flush=True
    )

    if config.COOKIES_FILE:
        cookie_path = Path(config.COOKIES_FILE)

        print(
            f"[YTOOLKIT DEBUG] Cookie path: {cookie_path}",
            flush=True
        )

        print(
            f"[YTOOLKIT DEBUG] Cookie exists: "
            f"{cookie_path.is_file()}",
            flush=True
        )

        if cookie_path.is_file():
            print(
                f"[YTOOLKIT DEBUG] Cookie size: "
                f"{cookie_path.stat().st_size} bytes",
                flush=True
            )

    print("[YTOOLKIT DEBUG] yt-dlp options:", flush=True)

    safe_opts = dict(opts)

    if "cookiefile" in safe_opts:
        safe_opts["cookiefile"] = "[REDACTED]"

    print(safe_opts, flush=True)
    print("=" * 70, flush=True)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

        if info is None:
            if logger.errors:
                detail = " / ".join(logger.errors)
            else:
                detail = "yt-dlp returned no result and logged no specific error."

            raise DownloadError(f"Download failed: {detail}")

        entries = info.get("entries") if info.get("entries") is not None else [info]

        for e in entries:
            if e is None:
                continue
            title = e.get("title", "unknown")

            # requested_downloads is yt-dlp's own record of the final file
            # it wrote for this entry (populated after download +
            # postprocessing complete) — the canonical source of truth,
            # more reliable than predicting the name ourselves.
            candidate = None
            for rd in (e.get("requested_downloads") or []):
                fp = rd.get("filepath")
                if fp:
                    candidate = fp

            if not candidate:
                try:
                    candidate = ydl.prepare_filename(e)
                except Exception:
                    candidate = None

            path = Path(candidate) if candidate else None

            if path and path.is_file() and path.suffix.lstrip(".") == expected_ext:
                results.append(str(path))
                continue

            # Predicted path is missing or has the wrong extension (e.g.
            # merge/extraction silently didn't happen) — do one last
            # defensive check: is there a same-named file sitting right
            # there with the expected extension anyway?
            if path:
                sibling = path.with_suffix("." + expected_ext)
                if sibling.is_file():
                    results.append(str(sibling))
                    continue

            failures.append(title)

    if failures and not results:
        detail = (
            f" Underlying yt-dlp error(s): {' / '.join(logger.errors)}"
            if logger.errors
            else ""
        )
        raise DownloadError(
            f"Download finished but no .{expected_ext} file was produced for: "
            f"{', '.join(failures)}. This usually means ffmpeg failed partway "
            f"through, or yt-dlp itself failed on that entry.{detail}"
        )

    return results