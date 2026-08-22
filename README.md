# ILoveYT 💛

*by Rounak*

A YouTube toolkit (CLI + web app) for you and your friends/family: download
video/audio, pull video/playlist metadata, and fetch transcripts, with
optional AI summarization via Gemini (free tier) or a local Ollama model.

**A note on scope.** This is built for a small, trusted group — not as a
public product. Video/audio download specifically runs into YouTube's Terms
of Service regardless of who's hosting it or how many people use it; that
doesn't go away just because it's "friends and family" rather than the
general public. Worth keeping in mind if you ever expand who has access.

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
Open http://127.0.0.1:5000 in your browser.

The frontend is a **React app** (sidebar navigation: Home, Download, Video
Info, Playlist, Transcript, AI Summary, History) served as a single
`templates/index.html`. It loads React, Babel, and Tailwind from CDNs and
compiles the JSX right in the browser — there's no `npm install` or build
step, so deployment is still exactly `python app.py`. The trade-off is a
bit more work for the browser on first load (in-browser JSX compilation)
versus a pre-built bundle; for a small personal/family deployment that's a
reasonable trade, but if this ever needs to scale to a lot of concurrent
users, moving to a proper Vite build would be the next step.

Every download (video, transcript export, playlist report) is generated on
the server and then served back to your browser with a real
`Content-Disposition: attachment` response — clicking the link in the UI
triggers a normal browser save-to-device download, the same as downloading
anything else off the web. This also means it behaves the same after you
deploy it somewhere, not just on localhost.

Every action panel (Download, Info, Transcript, Summary, each playlist row)
follows the same rule: only one request in flight at a time, and the moment
you change *any* input — URL, format, quality, checkboxes — the previous
result is cleared and the button re-enables. That's what stops a stale MP4
link from lingering on screen after you've switched the format to MP3, and
what stops a double-click from firing two downloads.

Recent actions are kept in a **History** tab (and "Recent Tools" on Home),
stored in your browser's local storage — it's per-browser, not shared
across devices or people using the deployment.

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
  The Video Info and Transcript tabs also have their own direct download
  buttons now, so you don't have to go through the playlist view for a
  single video.
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
- **"ffmpeg was not found on PATH"** — both MP4 merging and MP3 extraction
  require ffmpeg; the app now checks for it up front and fails with this
  clear message instead of silently producing a `.webm`/partial file where
  the real output should be. Install it (see Prerequisites above) and make
  sure `ffmpeg` works in a *new* terminal window (PATH changes need a
  fresh shell).
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

## 7. Deploying (Render)

This app is a real, persistent Flask process with ffmpeg subprocess calls
and local disk writes — that rules out serverless hosts like Vercel, whose
functions time out after 10–60s and don't ship ffmpeg. **Render** (or
Railway, Fly.io, a plain VPS — anything that runs a normal long-lived
container) fits it properly. Steps for Render:

1. Push this repo to GitHub if it isn't already.
2. In the Render dashboard: **New → Blueprint**, point it at the repo. It
   picks up `render.yaml` and `Dockerfile` automatically — the Dockerfile
   installs ffmpeg via apt, which Render's plain Python runtime doesn't
   include.
3. Set environment variables in the Render dashboard (the blueprint marks
   these `sync: false` so they're not stored in the repo):
   - `ILOVEYT_USER` / `ILOVEYT_PASS` — **do this** before sharing the link.
     Once it's deployed it's a public URL; without these, anyone who finds
     it can trigger downloads and AI calls on your bill. Leave both unset
     only if you're fine with that.
   - `YTOOLKIT_AI_PROVIDER=gemini` + `GEMINI_API_KEY` if you want AI
     summaries. **Ollama won't work here** — it'd need to run on the same
     machine as the app, and Render's servers aren't your machine. Gemini
     (cloud API) is the option that actually works once deployed.
4. Deploy. Free tier spins the instance down after inactivity, so the
   first request after a quiet period takes ~30–60s to wake back up —
   normal for free hosting, not a bug.

If you specifically want Vercel anyway — e.g. to try it — Info/Transcript/
Summary alone (no downloading) might work within its timeout, but expect
MP4/MP3 downloads to fail intermittently or outright on anything but very
short clips, since there's no way around the execution time limit or the
missing ffmpeg binary on that platform. Happy to put together a
lightweight-only Vercel config if you want to see for yourself, but Render
is the one that matches what this app actually does.

## Project structure

```
ytoolkit/
  ytoolkit/
    core.py        # yt-dlp wrapper: download, video info, playlist info
    transcript.py   # caption/transcript fetching
    ai.py           # pluggable Gemini / Ollama summarization
    config.py       # env-based settings
    report.py       # playlist report builder
  cli.py            # command-line interface
  app.py            # Flask web app (with optional Basic Auth gate)
  templates/index.html
  downloads/        # default local output folder
  requirements.txt
  Dockerfile        # for Render/Docker-based deployment
  .dockerignore
  render.yaml       # Render Blueprint
  .env.example
```
