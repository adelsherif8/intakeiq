"""Langfuse tracing for a voice turn: STT (span) -> LLM (generation) -> TTS (span).
Returns the public trace URL, or None if not configured. Never breaks a turn.
"""

import os

_lf = None


def configured() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _client():
    global _lf
    if _lf is None:
        from langfuse import Langfuse
        _lf = Langfuse()
    return _lf


def trace_turn(user_text: str, out: dict, latency: dict) -> str | None:
    if not configured():
        return None
    try:
        lf = _client()
        with lf.start_as_current_observation(
            as_type="span", name="voice-intake-turn",
            input={"user": user_text, "stage_in": out.get("stage")},
        ) as root:
            if latency.get("stt"):
                with lf.start_as_current_observation(
                        as_type="span", name="whisper-stt",
                        input={"audio": "user speech"}) as s:
                    s.update(output={"transcript": user_text, "ms": latency["stt"]})
            with lf.start_as_current_observation(
                    as_type="generation", name="gpt-4o-converse",
                    model=os.getenv("IQ_MODEL", "gpt-4o"),
                    input={"user": user_text}) as g:
                g.update(output={"reply": out.get("reply"), "stage": out.get("stage"),
                                 "action": out.get("action")},
                         usage_details={"input": out.get("usage", {}).get("in", 0),
                                        "output": out.get("usage", {}).get("out", 0)})
            if latency.get("tts"):
                with lf.start_as_current_observation(
                        as_type="span", name="openai-tts",
                        input={"text": out.get("reply")}) as t:
                    t.update(output={"ms": latency["tts"]})
            root.update(output={"reply": out.get("reply"), "stage": out.get("stage"),
                                "booked": bool(out.get("booking")),
                                "total_ms": latency.get("total")})
            url = lf.get_trace_url()
        lf.flush()
        return url
    except Exception:
        return None
