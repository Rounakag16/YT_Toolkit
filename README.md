# ytoolkit — local personal YouTube toolkit

A local-only tool (CLI + web app) for your own personal use: download
video/audio, pull video/playlist metadata, and fetch transcripts, with
optional AI summarization via Gemini (free tier) or a local Ollama model.

**This is for local personal use only.** It is not built or intended to be
hosted publicly, redistributed to other users, or used to re-share
downloaded content — doing so runs into YouTube's Terms of Service and
copyright law. Keep it on your own machine.

## 1. Prerequisites

- Python 3.9+
- **ffmpeg** installed and on your PATH (required for MP3 extraction and
  merging video+audio into MP4):
  - macOS: `brew install ffmpeg`
  - Windows: `winget install ffmpeg` (or download from ffmpeg.org and add to PATH)
  - Linux: `sudo apt install ffmpeg` (or your distro's equivalent)

## 2. Setup

```bash
cd ytoolkit
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit .env if you want AI summaries
```

If you don't want AI summarization, you can skip editing `.env` entirely —
everything else works with `YTOOLKIT_AI_PROVIDER=none`.

### Optional: AI summarization setup

**Gemini (free tier, cloud):**
1. Get a free API key at https://aistudio.google.com/apikey
2. In `.env`: `YTOOLKIT_AI_PROVIDER=gemini` and `GEMINI_API_KEY=your_key`

**Ollama (fully local, offline):**
1. Install Ollama from https://ollama.com
2. `ollama pull gpt-oss:20b` (needs a decent GPU/RAM — it's a 20B model)
3. In `.env`: `YTOOLKIT_AI_PROVIDER=ollama`
4. Run `ollama serve` before using summarize

## 3. Web app

```bash
python app.py
```
Open http://127.0.0.1:5000 in your browser. Four tabs: Download, Video Info,
Playlist, Transcript (+ Summarize).

Downloaded files land in `./downloads/` by default.

## 4. CLI

```bash
# Download a video as MP4
python cli.py download "https://youtube.com/watch?v=VIDEO_ID" --format mp4 --quality 720p

# Extract audio as MP3
python cli.py download "https://youtube.com/watch?v=VIDEO_ID" --format mp3

# Download an entire playlist (creates a subfolder per playlist)
python cli.py download "https://youtube.com/playlist?list=PLAYLIST_ID" --format mp3

# Video metadata as JSON
python cli.py info "https://youtube.com/watch?v=VIDEO_ID"

# Playlist listing + CSV export
python cli.py playlist "https://youtube.com/playlist?list=PLAYLIST_ID" --csv playlist.csv

# Transcript
python cli.py transcript "https://youtube.com/watch?v=VIDEO_ID" --timestamps --out transcript.txt

# Transcript + AI summary
python cli.py transcript "https://youtube.com/watch?v=VIDEO_ID" --summarize
```

## 5. Playlist page: per-video actions & full reports

- Each row in the playlist table has **MP4 / MP3 / Transcript / Summary**
  buttons — click one to act on just that video without leaving the page.
- Below the table, **Generate Report** builds a combined file (JSON, CSV,
  or Markdown) with every video's metadata, transcript, and (optionally)
  AI summary. You can also trigger a bulk MP3/MP4 download of the whole
  playlist from the same panel. Large playlists + summaries on = slow,
  since it's one AI call per video — that's expected.
- CLI equivalent: `python cli.py playlist <url> --report out.md --summarize --download-all mp3`

## 6. Notes & troubleshooting

- **Transcripts** are pulled directly via yt-dlp's caption resolution
  (not a separate scraping library), so it sees both manual and
  auto-generated tracks in whatever languages YouTube exposes for that
  video. If a video genuinely has no captions of either kind, you'll get
  a clear "no captions" message instead of a silent failure.
- **"No transcript available"** — not every video has captions (manual or
  auto-generated). This is a YouTube-side limitation, not a bug.
- **Age-restricted or private videos** fail without cookies. Set
  `YTOOLKIT_COOKIES_FROM_BROWSER=chrome` (or firefox/edge) in `.env` to reuse
  your logged-in browser session, or point `YTOOLKIT_COOKIES_FILE` at an
  exported cookies.txt.
- **yt-dlp breaks periodically** when YouTube changes something — if
  downloads suddenly fail, run `pip install -U yt-dlp` first; it's updated
  very frequently.
- **Quality option "best"** picks the highest resolution yt-dlp can find
  and merges video+audio with ffmpeg — this can be large/slow for long
  videos; use 720p/480p for faster results.

## Project structure

```
ytoolkit/
  ytoolkit/
    core.py        # yt-dlp wrapper: download, video info, playlist info
    transcript.py   # caption/transcript fetching
    ai.py           # pluggable Gemini / Ollama summarization
    config.py       # env-based settings
  cli.py            # command-line interface
  app.py            # Flask web app
  templates/index.html
  downloads/        # default output folder
  requirements.txt
  .env.example
```
