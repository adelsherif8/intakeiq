# IntakeIQ — AI Voice Intake & Booking Agent

A browser-based **voice agent** that answers like a receptionist: it greets the
caller, qualifies them (name, reason, contact), offers real appointment slots,
books one, and sends a **real calendar invite** — all by voice, in the browser.

**Live demo:** _(deployed on Vercel)_ · speak to it, or type.

## How it works — one spoken turn

```
Caller speaks (browser mic)
      │  Whisper STT
      ▼
LangGraph state machine + GPT-4o
   greeting → qualifying → scheduling → confirming → done
      │  (books only a slot the caller explicitly confirms)
      ▼
Book → real .ics calendar invite   ──►  OpenAI TTS → agent speaks back
```

- **Voice I/O:** OpenAI **Whisper** (STT) + **OpenAI TTS** (onyx voice).
- **Reasoning:** **GPT-4o** driven by a **LangGraph** state machine that enforces
  the intake flow so the agent never skips steps or books a phantom appointment.
- **Booking:** on confirmation, a dedicated graph node generates a standards-
  compliant **.ics invite** (works with Google / Apple / Outlook). A live Google
  Calendar API path is production-ready with service-account credentials.
- **Observability:** every turn traced in **Langfuse** (STT / LLM / TTS spans,
  tokens, latency). The UI shows the per-turn STT → LLM → TTS breakdown.
- **Reliability:** push-to-talk turn-taking; graceful text fallback; the booking
  only fires on an explicit slot pick.

## Modes
- **Voice live** — set `OPENAI_API_KEY` (+ `LANGFUSE_*`). Real Whisper, GPT-4o, TTS.
- **Text demo** — no key needed; type to the agent, browser speech reads replies.

## Run locally
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000
```

## Stack
Python · FastAPI · LangGraph · GPT-4o · Whisper · OpenAI TTS · Langfuse

Built by **Adel Atya** — adelatya.vercel.app
