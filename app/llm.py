"""OpenAI voice + reasoning wrapper: Whisper STT, GPT-4o, OpenAI TTS.

Everything degrades gracefully: with no OPENAI_API_KEY the app still runs in a
text + browser-speech fallback (handled client-side), so the demo never hard-fails.
Each call returns latency so the UI can show the STT -> LLM -> TTS breakdown.
"""

import os
import time
import json
import base64

CHAT_MODEL = os.getenv("IQ_MODEL", "gpt-4o")
TTS_MODEL = os.getenv("IQ_TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("IQ_TTS_VOICE", "onyx")
STT_MODEL = os.getenv("IQ_STT_MODEL", "whisper-1")


def live() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def mode() -> str:
    return "openai" if live() else "mock"


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, int]:
    """Whisper STT -> (text, latency_ms)."""
    t0 = time.perf_counter()
    resp = _get_client().audio.transcriptions.create(
        model=STT_MODEL, file=(filename, audio_bytes),
    )
    return resp.text.strip(), int((time.perf_counter() - t0) * 1000)


def converse(system: str, messages: list[dict]) -> tuple[dict, dict, int]:
    """GPT-4o JSON turn -> (parsed, usage, latency_ms)."""
    t0 = time.perf_counter()
    resp = _get_client().chat.completions.create(
        model=CHAT_MODEL, temperature=0.5,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}] + messages,
    )
    latency = int((time.perf_counter() - t0) * 1000)
    data = json.loads(resp.choices[0].message.content)
    u = resp.usage
    usage = {"in": u.prompt_tokens, "out": u.completion_tokens}
    return data, usage, latency


def speak(text: str) -> tuple[str, int]:
    """OpenAI TTS -> (base64 mp3, latency_ms)."""
    t0 = time.perf_counter()
    resp = _get_client().audio.speech.create(
        model=TTS_MODEL, voice=TTS_VOICE, input=text[:800],
    )
    audio = resp.content if hasattr(resp, "content") else resp.read()
    b64 = base64.b64encode(audio).decode()
    return b64, int((time.perf_counter() - t0) * 1000)
