#!/usr/bin/env python3
"""
Web UI for ytoolkit. Run with: python app.py
Then open http://127.0.0.1:5000

Every file produced by a "download" action (video, transcript, report)
is generated on the server and then served back over HTTP with
Content-Disposition: attachment, so the browser triggers a normal save-
to-device download — the same way any other file download on the web
works. That's true whether you're running this locally or after you
deploy it; nothing depends on you personally having filesystem access
to the machine running Flask.
"""
from pathlib import Path
from urllib.parse import quote

from flask import Flask, render_template, request, jsonify, send_file, abort

from ytoolkit import core, transcript as tr, ai, config, report as rpt

app = Flask(__name__)


def _serve_url(abs_path: Path) -> str:
    """Build a /downloads/... URL for a file inside DOWNLOAD_DIR, with each
    path segment percent-encoded so filenames containing spaces, &, |,
    non-ASCII characters, etc. always produce a valid, unambiguous URL —
    rather than relying on the browser to guess how to encode a raw
    string dropped into an href."""
    rel = abs_path.resolve().relative_to(config.DOWNLOAD_DIR.resolve())
    return "/downloads/" + "/".join(quote(part) for part in rel.parts)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def api_info():
    url = request.json.get("url", "").strip()
    try:
        return jsonify(core.get_video_info(url))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/playlist", methods=["POST"])
def api_playlist():
    url = request.json.get("url", "").strip()
    try:
        return jsonify(core.get_playlist_info(url))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/transcript", methods=["POST"])
def api_transcript():
    data = request.json
    url = data.get("url", "").strip()
    timestamps = bool(data.get("timestamps"))
    try:
        result = tr.get_transcript(url, with_timestamps=timestamps)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    text = request.json.get("text", "")
    try:
        summary = ai.summarize(text)
        return jsonify({"summary": summary})
    except ai.AIError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.json
    url = data.get("url", "").strip()
    fmt = data.get("format", "mp4")
    quality = data.get("quality", "best")
    try:
        files = core.download(url, fmt=fmt, quality=quality)
        items = [{"name": Path(f).name, "url": _serve_url(Path(f))} for f in files]
        return jsonify({"files": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/playlist/report", methods=["POST"])
def api_playlist_report():
    """
    Builds a combined report (metadata + optional transcript + optional
    AI summary) for every video in a playlist and saves it to the
    downloads folder. Can take a while for large playlists, especially
    with summaries on (one AI call per video).
    """
    data = request.json
    url = data.get("url", "").strip()
    include_transcript = bool(data.get("include_transcript", True))
    include_summary = bool(data.get("include_summary", False))
    fmt = data.get("format", "json")
    try:
        report = rpt.build_playlist_report(
            url, include_transcript=include_transcript, include_summary=include_summary
        )
        fname = f"{rpt.safe_filename(report['playlist_title'])}_report.{fmt}"
        out_path = config.DOWNLOAD_DIR / fname
        rpt.save_report(report, out_path, fmt=fmt)
        return jsonify({"file": fname, "url": _serve_url(out_path),
                         "video_count": report["video_count"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/downloads/<path:filename>")
def serve_download(filename):
    target = (config.DOWNLOAD_DIR / filename).resolve()
    # Guard against path traversal escaping the downloads directory.
    if config.DOWNLOAD_DIR.resolve() not in target.parents and target != config.DOWNLOAD_DIR.resolve():
        abort(404)
    if not target.is_file():
        abort(404)
    return send_file(target, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
