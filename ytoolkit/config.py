"""
Central config. Reads from environment variables (loaded from a .env file
if present) so you never hardcode keys into the code.

Copy .env.example -> .env and fill in what you need.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed -> fall back to real env vars only
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# Default matches how a normal browser download behaves: your OS's real
# Downloads folder, in a "ytoolkit" subfolder so it doesn't clutter it.
# Override with YTOOLKIT_DOWNLOAD_DIR in .env if you want it elsewhere
# (e.g. back to the project folder, or Desktop instead of Downloads).
_DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "ytoolkit"
DOWNLOAD_DIR = Path(os.getenv("YTOOLKIT_DOWNLOAD_DIR", "") or _DEFAULT_DOWNLOAD_DIR)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- AI provider settings -------------------------------------------------
# AI_PROVIDER: "gemini" | "ollama" | "none"
AI_PROVIDER = os.getenv("YTOOLKIT_AI_PROVIDER", "none").lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

# --- yt-dlp settings --------------------------------------------------
# Path to a browser cookies file (Netscape format) or a browser name
# (e.g. "chrome", "firefox") for yt-dlp's --cookies-from-browser.
# Only needed for age-restricted / login-required videos, or when
# YouTube starts demanding a login from a datacenter IP (common once
# deployed to a host like Render).
COOKIES_FROM_BROWSER = os.getenv("YTOOLKIT_COOKIES_FROM_BROWSER", "")

_raw_cookies_file = os.getenv("YTOOLKIT_COOKIES_FILE", "")
COOKIES_FILE = ""
if _raw_cookies_file:
    _src = Path(_raw_cookies_file)
    if _src.is_file():
        # yt-dlp doesn't just read this file — it rewrites it in place
        # after each run to persist any refreshed session cookies. That
        # write fails with "Read-only file system" if the source is a
        # read-only mount, which is exactly what Render's Secret Files
        # are. Copy it once to a writable temp location at startup and
        # point yt-dlp at the copy instead — same cookies, just somewhere
        # yt-dlp is actually allowed to update.
        import shutil
        import tempfile
        _writable_copy = Path(tempfile.gettempdir()) / "ytoolkit_cookies.txt"
        try:
            shutil.copyfile(_src, _writable_copy)
            COOKIES_FILE = str(_writable_copy)
        except OSError:
            # Fall back to the original path rather than crash at import
            # time — yt-dlp will surface its own clear error if this path
            # turns out to be unusable too.
            COOKIES_FILE = str(_src)
    else:
        COOKIES_FILE = _raw_cookies_file