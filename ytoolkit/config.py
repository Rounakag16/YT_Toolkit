"""
Central config. Reads from environment variables (loaded from a .env file
if present) so you never hardcode keys into the code.

Copy .env.example -> .env and fill in what you need.
"""
import os
from pathlib import Path

import sys

print(f"[debug] Python: {sys.version}")

try:
    import yt_dlp
    print(f"[debug] yt-dlp version: {yt_dlp.version.__version__}")
except Exception as e:
    print(f"[debug] yt-dlp version check failed: {e}")

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

COOKIES_FROM_BROWSER = os.getenv("YTOOLKIT_COOKIES_FROM_BROWSER", "")

_raw_cookies_file = os.getenv("YTOOLKIT_COOKIES_FILE", "")
COOKIES_FILE = ""

if _raw_cookies_file:
    _src = Path(_raw_cookies_file)

    print(f"[cookies] Source: {_src}")
    print(f"[cookies] Exists: {_src.is_file()}")

    if _src.is_file():
        try:
            print(f"[cookies] Size: {_src.stat().st_size} bytes")

            # Check the ORIGINAL Render Secret File.
            with _src.open("rb") as f:
                source_header = f.read(256)

            source_valid = b"Netscape HTTP Cookie File" in source_header
            print(f"[cookies] Source Netscape header: {source_valid}")

            if not source_valid:
                print(
                    "[cookies] ERROR: Source file does not appear "
                    "to be a Netscape cookies file."
                )
            else:
                import shutil
                import tempfile

                # Create a unique writable temporary file.
                fd, temp_path = tempfile.mkstemp(
                    prefix="ytoolkit_cookies_",
                    suffix=".txt"
                )
                os.close(fd)

                _writable_copy = Path(temp_path)

                # Copy byte-for-byte.
                shutil.copyfile(_src, _writable_copy)

                print(f"[cookies] Writable copy: {_writable_copy}")
                print(
                    f"[cookies] Copy size: "
                    f"{_writable_copy.stat().st_size} bytes"
                )

                # Verify the COPY.
                with _writable_copy.open("rb") as f:
                    copy_header = f.read(256)

                copy_valid = b"Netscape HTTP Cookie File" in copy_header
                print(f"[cookies] Copy Netscape header: {copy_valid}")

                if copy_valid:
                    COOKIES_FILE = str(_writable_copy)
                    print("[cookies] Cookie file ready for yt-dlp.")
                else:
                    print(
                        "[cookies] ERROR: Copy is not a valid "
                        "Netscape cookies file."
                    )

        except (OSError, ValueError) as exc:
            print(f"[cookies] ERROR preparing cookies: {exc}")
            COOKIES_FILE = ""

    else:
        print(
            f"[cookies] ERROR: Cookie file does not exist: {_src}"
        )

else:
    print("[cookies] No YTOOLKIT_COOKIES_FILE configured.")