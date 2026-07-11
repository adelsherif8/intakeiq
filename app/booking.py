"""Appointment slots + real .ics calendar invite generation.

No external calendar account needed: on booking we emit a standards-compliant
.ics file the caller can open in Google / Apple / Outlook. (A real Google
Calendar API path can be added with service-account creds — see README.)
"""

import base64
from datetime import datetime, timedelta

BUSINESS_NAME = "Bright Smile Dental"
SLOT_MINUTES = 30


def _next_weekday(d: datetime, add_days: int) -> datetime:
    d = d + timedelta(days=add_days)
    while d.weekday() >= 5:  # skip Sat/Sun
        d += timedelta(days=1)
    return d


def generate_slots(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    base = now.replace(minute=0, second=0, microsecond=0)
    specs = [(1, 10), (1, 14), (2, 11)]  # (days ahead, hour)
    slots = []
    for i, (days, hour) in enumerate(specs):
        day = _next_weekday(base, days).replace(hour=hour)
        slots.append({
            "id": f"slot{i+1}",
            "label": day.strftime("%A %b %-d at %-I:%M %p"),
            "start": day.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": (day + timedelta(minutes=SLOT_MINUTES)).strftime("%Y-%m-%dT%H:%M:%S"),
        })
    return slots


def _ics_dt(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%Y%m%dT%H%M%S")


def make_ics(booking: dict) -> str:
    c = booking
    uid = f"{c.get('slot_id','apt')}-{c.get('phone','x')}@intakeiq"
    desc = (f"Reason: {c.get('reason','')}\\n"
            f"Name: {c.get('name','')}\\n"
            f"Phone: {c.get('phone','')}\\n"
            f"Email: {c.get('email','')}")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IntakeIQ//Voice Intake//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{_ics_dt(c['start'])}",
        f"DTEND:{_ics_dt(c['end'])}",
        f"SUMMARY:{BUSINESS_NAME} — appointment for {c.get('name','client')}",
        f"DESCRIPTION:{desc}",
        f"LOCATION:{BUSINESS_NAME}",
        "STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines)


def ics_data_url(ics_text: str) -> str:
    b64 = base64.b64encode(ics_text.encode()).decode()
    return f"data:text/calendar;charset=utf-8;base64,{b64}"
