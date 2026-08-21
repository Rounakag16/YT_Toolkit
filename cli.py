#!/usr/bin/env python3
"""
ytoolkit CLI — personal-use local YouTube toolkit.

Examples:
  python cli.py download "https://youtube.com/watch?v=..." --format mp3
  python cli.py download "https://youtube.com/playlist?list=..." --format mp4 --quality 720p
  python cli.py info "https://youtube.com/watch?v=..."
  python cli.py playlist "https://youtube.com/playlist?list=..." --csv out.csv
  python cli.py transcript "https://youtube.com/watch?v=..." --timestamps --out transcript.txt
  python cli.py transcript "URL" --summarize
"""
import argparse
import csv
import json
import sys

from ytoolkit import core, transcript as tr, ai, report as rpt


def cmd_download(args):
    def hook(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "").strip()
            fn = d.get("filename", "")
            print(f"\r  {pct}  {fn}", end="", flush=True)
        elif d["status"] == "finished":
            print()  # newline after progress

    print(f"Downloading ({args.format}, {args.quality}) ...")
    files = core.download(args.url, fmt=args.format, quality=args.quality,
                           output_dir=args.output, progress_hook=hook)
    print(f"\nDone. {len(files)} file(s):")
    for f in files:
        print(f"  {f}")


def cmd_info(args):
    info = core.get_video_info(args.url)
    print(json.dumps(info, indent=2, ensure_ascii=False))


def cmd_playlist(args):
    data = core.get_playlist_info(args.url)
    print(f"Playlist: {data['playlist_title']}")
    print(f"Videos: {data['video_count']}  Total duration: {data['total_duration_str']}\n")
    for v in data["videos"]:
        print(f"  [{v['duration_str']:>8}]  {v['title']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "title", "url", "duration_str", "view_count", "channel"])
            w.writeheader()
            for v in data["videos"]:
                w.writerow({k: v[k] for k in w.fieldnames})
        print(f"\nSaved CSV -> {args.csv}")

    if args.report:
        print(f"\nBuilding full report (transcripts={not args.no_transcript}, "
              f"summaries={args.summarize})... this can take a while.")

        def progress(i, total, entry):
            print(f"  [{i}/{total}] {entry['title']}")

        report = rpt.build_playlist_report(
            args.url,
            include_transcript=not args.no_transcript,
            include_summary=args.summarize,
            progress_cb=progress,
        )
        out_path = rpt.save_report(report, args.report, fmt=args.report.rsplit(".", 1)[-1])
        print(f"Saved report -> {out_path}")

    if args.download_all:
        fmt = args.download_all
        print(f"\nDownloading all videos as {fmt}...")
        files = core.download(args.url, fmt=fmt)
        print(f"Downloaded {len(files)} files.")


def cmd_transcript(args):
    result = tr.get_transcript(args.url, with_timestamps=args.timestamps)
    if not result["available"]:
        print(f"No transcript available: {result['reason']}", file=sys.stderr)
        sys.exit(1)

    print(f"Language: {result['language']} ({'auto-generated' if result['is_generated'] else 'manual'})\n")

    if args.summarize:
        print("Summarizing with AI...\n")
        try:
            summary = ai.summarize(result["text"])
            print(summary)
        except ai.AIError as e:
            print(f"AI error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(result["text"])

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result["text"])
        print(f"\nSaved -> {args.out}")


def main():
    p = argparse.ArgumentParser(description="ytoolkit — local personal YouTube toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="Download video as mp4 or extract audio as mp3")
    d.add_argument("url")
    d.add_argument("--format", choices=["mp3", "mp4"], default="mp4")
    d.add_argument("--quality", choices=["best", "1080p", "720p", "480p"], default="best")
    d.add_argument("--output", default=None, help="Output directory")
    d.set_defaults(func=cmd_download)

    i = sub.add_parser("info", help="Show metadata for a single video")
    i.add_argument("url")
    i.set_defaults(func=cmd_info)

    pl = sub.add_parser("playlist", help="List all videos + totals for a playlist")
    pl.add_argument("url")
    pl.add_argument("--csv", default=None, help="Optional path to save a CSV export")
    pl.add_argument("--report", default=None,
                     help="Save a combined report (metadata+transcript+summary) — "
                          "path ext decides format: report.json / report.csv / report.md")
    pl.add_argument("--no-transcript", action="store_true", help="Skip transcripts in --report")
    pl.add_argument("--summarize", action="store_true", help="Include AI summaries in --report")
    pl.add_argument("--download-all", choices=["mp3", "mp4"], default=None,
                     help="Also download every video in the playlist in this format")
    pl.set_defaults(func=cmd_playlist)

    t = sub.add_parser("transcript", help="Get a video's transcript")
    t.add_argument("url")
    t.add_argument("--timestamps", action="store_true")
    t.add_argument("--out", default=None, help="Save transcript text to a file")
    t.add_argument("--summarize", action="store_true", help="Summarize with configured AI provider")
    t.set_defaults(func=cmd_transcript)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
