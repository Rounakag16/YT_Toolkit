"""
Builds a combined report across every video in a playlist: metadata,
optionally transcript, optionally an AI summary — then writes it out
as JSON, CSV, or Markdown.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from . import core, transcript as tr, ai


def safe_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name or "playlist")
    name = name.strip().strip(".")
    return (name[:max_len] or "playlist")


def build_playlist_report(url: str, include_transcript: bool = True,
                           include_summary: bool = False,
                           languages: list[str] | None = None,
                           progress_cb=None) -> dict:
    pl = core.get_playlist_info(url)
    videos_out = []

    for i, v in enumerate(pl["videos"], start=1):
        entry = dict(v)
        if include_transcript or include_summary:
            t = tr.get_transcript(v["url"], languages=languages)
            entry["transcript_available"] = t["available"]
            if t["available"]:
                entry["transcript_language"] = t["language"]
                entry["transcript_is_generated"] = t["is_generated"]
                entry["transcript"] = t["text"]
                if include_summary:
                    try:
                        entry["summary"] = ai.summarize(t["text"])
                    except ai.AIError as e:
                        entry["summary"] = ""
                        entry["summary_error"] = str(e)
            else:
                entry["transcript"] = ""
                entry["transcript_reason"] = t.get("reason")
        videos_out.append(entry)
        if progress_cb:
            progress_cb(i, pl["video_count"], entry)

    return {
        "playlist_title": pl["playlist_title"],
        "playlist_id": pl["playlist_id"],
        "video_count": pl["video_count"],
        "total_duration_str": pl["total_duration_str"],
        "videos": videos_out,
    }


def save_report(report: dict, out_path: str | Path, fmt: str = "json") -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    elif fmt == "csv":
        fields = ["id", "title", "url", "duration_str", "view_count", "channel",
                  "transcript_available", "transcript_language", "transcript", "summary"]
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for v in report["videos"]:
                w.writerow(v)

    elif fmt == "md":
        lines = [f"# {report['playlist_title']}", "",
                 f"{report['video_count']} videos · total duration {report['total_duration_str']}", ""]
        for v in report["videos"]:
            lines.append(f"## {v['title']}")
            lines.append(f"- URL: {v['url']}")
            lines.append(f"- Duration: {v['duration_str']}")
            if v.get("view_count") is not None:
                lines.append(f"- Views: {v['view_count']}")
            if "summary" in v and v["summary"]:
                lines.append("")
                lines.append("**Summary:**")
                lines.append(v["summary"])
            if v.get("transcript"):
                lines.append("")
                lines.append("<details><summary>Transcript</summary>")
                lines.append("")
                lines.append(v["transcript"])
                lines.append("")
                lines.append("</details>")
            elif v.get("transcript_reason"):
                lines.append(f"- Transcript: not available ({v['transcript_reason']})")
            lines.append("")
        out_path.write_text("\n".join(lines), encoding="utf-8")

    else:
        raise ValueError(f"Unknown report format: {fmt}")

    return out_path
