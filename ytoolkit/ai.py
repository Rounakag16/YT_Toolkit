"""
Pluggable AI layer for transcript summarization / Q&A.
Set YTOOLKIT_AI_PROVIDER in .env to "gemini", "ollama", or "none".

- gemini: uses Google's free-tier Gemini Flash model via the
  google-generativeai SDK. Needs GEMINI_API_KEY.
- ollama: uses a locally-running Ollama server (default model
  gpt-oss:20b). Needs Ollama installed and `ollama pull gpt-oss:20b`
  run once. No API key, fully offline.
"""
from __future__ import annotations

import requests

from . import config

DEFAULT_PROMPT = (
    "Summarize the following YouTube video transcript. Give:\n"
    "1) A 2-3 sentence overview\n"
    "2) 5-8 bullet key points\n"
    "3) Any notable quotes or figures mentioned\n\n"
    "Transcript:\n{transcript}"
)


class AIError(RuntimeError):
    pass


def summarize(transcript_text: str, prompt_template: str | None = None) -> str:
    provider = config.AI_PROVIDER
    prompt = (prompt_template or DEFAULT_PROMPT).format(transcript=transcript_text[:120_000])

    if provider == "gemini":
        return _summarize_gemini(prompt)
    if provider == "ollama":
        return _summarize_ollama(prompt)
    raise AIError(
        "No AI provider configured. Set YTOOLKIT_AI_PROVIDER=gemini or "
        "YTOOLKIT_AI_PROVIDER=ollama in your .env file."
    )


def _summarize_gemini(prompt: str) -> str:
    if not config.GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY is not set in .env")
    try:
        import google.generativeai as genai
    except ImportError:
        raise AIError("Run: pip install google-generativeai")

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text


def _summarize_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=600,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise AIError(
            f"Couldn't reach Ollama at {config.OLLAMA_HOST}. "
            "Is `ollama serve` running, and did you `ollama pull "
            f"{config.OLLAMA_MODEL}`?"
        )
    return resp.json().get("response", "").strip()
