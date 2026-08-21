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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

# --- yt-dlp settings --------------------------------------------------
# Path to a browser cookies file (Netscape format) or a browser name
# (e.g. "chrome", "firefox") for yt-dlp's --cookies-from-browser.
# Only needed for age-restricted / login-required videos.
COOKIES_FROM_BROWSER = os.getenv("YTOOLKIT_COOKIES_FROM_BROWSER", "")
COOKIES_FILE = os.getenv("YTOOLKIT_COOKIES_FILE", "")
