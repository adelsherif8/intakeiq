"""IntakeIQ — voice AI intake & booking agent. API + browser UI."""

import os
import json
import time

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app import llm, tracing
from app.agent import process_turn
from app.booking import BUSINESS_NAME

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_HERE, "templates"))

app = FastAPI(title="IntakeIQ")
LEADS: list[dict] = []          # in-memory captured leads (demo)
LATENCIES: list[int] = []       # end-to-end turn latencies (ms)


def _run_turn(prior: dict, user_text: str, stt_ms: int = 0) -> dict:
    t0 = time.perf_counter()
    out = process_turn(prior, user_text)
    tts_b64, tts_ms = "", 0
    if llm.live() and out.get("reply"):
        try:
            tts_b64, tts_ms = llm.speak(out["reply"])
        except Exception:
            tts_b64, tts_ms = "", 0
    total = int((time.perf_counter() - t0) * 1000) + stt_ms
    latency = {"stt": stt_ms, "llm": out.get("llm_ms", 0), "tts": tts_ms, "total": total}
    if stt_ms:
        LATENCIES.append(total)

    booking = out.get("booking")
    if booking and not any(l.get("phone") == booking.get("phone")
                           and l.get("slot_label") == booking.get("slot_label") for l in LEADS):
        LEADS.append({k: booking[k] for k in
                      ("name", "reason", "phone", "email", "slot_label")})

    trace_url = tracing.trace_turn(user_text, out, latency)
    return {
        "user_text": user_text,
        "reply": out["reply"],
        "reply_audio": tts_b64,
        "stage": out["stage"],
        "action": out.get("action", "none"),
        "collected": out.get("collected", {}),
        "slots": out.get("slots", []),
        "booking": booking,
        "state": {"messages": out["messages"], "collected": out.get("collected", {}),
                  "stage": out["stage"], "slots": out.get("slots", [])},
        "latency": latency,
        "trace_url": trace_url,
        "mode": llm.mode(),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "mode": llm.mode(), "langfuse": tracing.configured(), "business": BUSINESS_NAME,
    })


@app.post("/turn/voice")
async def turn_voice(audio: UploadFile = File(...), state: str = Form("{}")):
    if not llm.live():
        return JSONResponse({"error": "Voice needs OPENAI_API_KEY. Use text mode."}, status_code=400)
    data = await audio.read()
    try:
        text, stt_ms = llm.transcribe(data, audio.filename or "audio.webm")
    except Exception as e:
        return JSONResponse({"error": f"Transcription failed: {e}"}, status_code=500)
    if not text:
        return JSONResponse({"error": "Didn't catch that — please try again."}, status_code=200)
    return _run_turn(json.loads(state or "{}"), text, stt_ms)


@app.post("/turn/text")
async def turn_text(request: Request):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty"}, status_code=400)
    return _run_turn(body.get("state") or {}, text)


@app.get("/leads")
def leads():
    n = len(LATENCIES)
    avg = round(sum(LATENCIES) / n) if n else 0
    return {"leads": LEADS, "count": len(LEADS),
            "turns_measured": n, "avg_latency_ms": avg}


@app.get("/health")
def health():
    return {"ok": True, "mode": llm.mode(), "langfuse": tracing.configured()}
