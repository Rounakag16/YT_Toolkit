# ffmpeg is required for both MP4 merging and MP3 extraction, and it is
# NOT preinstalled on most PaaS Python runtimes (including Vercel's and
# Render's native/non-Docker environment) — so we build our own image
# with it installed via apt, which guarantees it's there regardless of
# what the platform's base image happens to include.
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Downloaded files live here for the life of the running container —
# no persistent disk needed, since files only need to survive long
# enough to be served back to whoever just requested them.
ENV YTOOLKIT_DOWNLOAD_DIR=/app/downloads
RUN mkdir -p /app/downloads

# Render (and most PaaS hosts) inject $PORT at runtime; gunicorn's
# --timeout is set high because video downloads/merges can legitimately
# take minutes, not the ~30s a web server usually expects a request to take.
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --timeout 900 --workers 2 --threads 4
