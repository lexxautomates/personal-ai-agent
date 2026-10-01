"""Real tool implementations for Jarvis. Pure logic, no livekit imports,
so this module is unit-testable. `tools.py` wraps these with @function_tool.

Every external write goes through policy.check() first. Confirm-first tools
(gmail_send, calendar_create) record a pending confirmation and return an
ask-aloud sentence; confirm_action() executes after Alexandria approves.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

import requests

from . import memory, nat, policy

logger = logging.getLogger("jarvis.tools")

_MAIL_UNREACHABLE = "the mail room is unreachable at the moment, ma'am"
_CAL_UNREACHABLE = "the calendar office is unreachable at the moment, ma'am"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Notes (local, reversible -> auto-allowed by policy)
# ---------------------------------------------------------------------------

def notes_jot(db: sqlite3.Connection, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "I didn't catch what to note down, ma'am."
    db.execute("INSERT INTO notes (text, created_at) VALUES (?, ?)", (text, _now()))
    db.commit()
    return "Noted, ma'am."


def notes_list(db: sqlite3.Connection, limit: int = 10) -> str:
    rows = db.execute(
        "SELECT id, text, created_at FROM notes ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 50)),),
    ).fetchall()
    if not rows:
        return "No notes on file, ma'am."
    lines = [f"#{r['id']}: {r['text']}" for r in rows]
    return "Your recent notes, ma'am: " + " ... ".join(lines)


def notes_search(db: sqlite3.Connection, query: str) -> str:
    rows = db.execute(
        "SELECT id, text FROM notes WHERE text LIKE ? ORDER BY id DESC LIMIT 10",
        (f"%{query}%",),
    ).fetchall()
    if not rows:
        return f"Nothing in your notes about {query}, ma'am."
    return "I found: " + " ... ".join(f"#{r['id']}: {r['text']}" for r in rows)


# ---------------------------------------------------------------------------
# Reminders (local -> auto-allowed; the watcher fires them into due_outbox)
# ---------------------------------------------------------------------------

def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def reminder_add(db: sqlite3.Connection, note: str, at_iso: str) -> str:
    dt = _parse_iso(at_iso)
    if not dt:
        return ("I couldn't make sense of that time, ma'am. "
                "Try something like 2026-10-02 09:00.")
    if dt <= datetime.now(timezone.utc):
        return "That time is already past, ma'am. Pick a future moment."
    db.execute(
        "INSERT INTO reminders (note, scheduled_at, created_at) VALUES (?, ?, ?)",
        (note, dt.isoformat(), _now()),
    )
    db.commit()
    spoken = dt.strftime("%A, %B %-d at %-I:%M %p")
    return f"Very good, ma'am. I'll remind you {spoken}."


def reminder_list(db: sqlite3.Connection) -> str:
    rows = db.execute(
        "SELECT id, note, scheduled_at FROM reminders WHERE fired = 0 ORDER BY scheduled_at"
    ).fetchall()
    if not rows:
        return "No reminders pending, ma'am."
    parts = []
    for r in rows:
        dt = _parse_iso(r["scheduled_at"])
        when = dt.strftime("%a %b %-d, %-I:%M %p") if dt else r["scheduled_at"]
        parts.append(f"#{r['id']} {r['note']} ({when})")
    return "Pending reminders, ma'am: " + " ... ".join(parts)


def reminder_cancel(db: sqlite3.Connection, reminder_id: int) -> str:
    cur = db.execute(
        "UPDATE reminders SET fired = 2 WHERE id = ? AND fired = 0", (reminder_id,)
    )
    db.commit()
    if cur.rowcount:
        return "Cancelled, ma'am."
    return "I couldn't find a pending reminder with that number, ma'am."


def check_due_reminders(db: sqlite3.Connection) -> str:
    rows = db.execute(
        "SELECT id, note, due_at FROM due_outbox WHERE announced = 0 ORDER BY id"
    ).fetchall()
    if not rows:
        return ""
    db.execute("UPDATE due_outbox SET announced = 1 WHERE announced = 0")
    db.commit()
    notes = "; ".join(r["note"] for r in rows)
    n = len(rows)
    return (f"Ma'am, {n} reminder{'s' if n > 1 else ''} came due while you were away: "
            f"{notes}.")


# ---------------------------------------------------------------------------
# Gmail via the Nat bridge (reads auto-allowed, send confirm-first)
# ---------------------------------------------------------------------------

def _fmt_messages(messages: list[dict]) -> str:
    if not messages:
        return "Nothing found, ma'am."
    parts = []
    for m in messages[:5]:
        frm = m.get("from", "unknown sender")
        subj = m.get("subject", "(no subject)")
        date = m.get("date", "")
        parts.append(f"From {frm}: {subj}" + (f", {date}" if date else ""))
    return "Here's what I found, ma'am: " + " ... ".join(parts)


def gmail_search(query: str, max_results: int = 5) -> str:
    try:
        res = nat.call("gmail_search", {"query": query, "max_results": max_results})
    except nat.BridgeError as e:
        return str(e)
    return _fmt_messages(res.get("messages", []))


def gmail_read(message_id: str) -> str:
    try:
        res = nat.call("gmail_read", {"message_id": message_id})
    except nat.BridgeError as e:
        return str(e)
    body = (res.get("body") or res.get("snippet") or "").strip()
    if not body:
        return "The message came back empty, ma'am."
    if len(body) > 1500:
        body = body[:1500] + " ... (truncated, ma'am)"
    subj = res.get("subject", "")
    frm = res.get("from", "")
    head = f"From {frm}, subject {subj}. " if (frm or subj) else ""
    return head + body


def gmail_draft(to: str, subject: str, body: str) -> str:
    try:
        nat.call("gmail_draft", {"to": to, "subject": subject, "body": body})
    except nat.BridgeError as e:
        return str(e)
    return f"Draft saved for {to}, ma'am. It's waiting in your drafts, unsent."


def gmail_send(db: sqlite3.Connection, to: str, subject: str, body: str) -> str:
    verdict, reason = policy.check("gmail_send", f"to={to} subject={subject}")
    if verdict == policy.REFUSE:
        return reason
    if verdict == policy.CONFIRM:
        cid = policy.request_confirmation(
            db, "gmail_send", {"to": to, "subject": subject, "body": body},
            detail=f"Send email to {to} with subject '{subject}'",
        )
        return (f"Before I send that, ma'am — just to confirm: email to {to}, "
                f"subject '{subject}'. Shall I send it? "
                f"(confirmation {cid})")
    try:
        nat.call("gmail_send", {"to": to, "subject": subject, "body": body})
    except nat.BridgeError as e:
        return str(e)
    return f"Sent to {to}, ma'am."


# ---------------------------------------------------------------------------
# Calendar via the Nat bridge (list auto-allowed, create confirm-first)
# ---------------------------------------------------------------------------

def calendar_list(days: int = 7) -> str:
    try:
        res = nat.call("calendar_list", {"days": max(1, min(days, 60))})
    except nat.BridgeError as e:
        return str(e).replace("mail room", "calendar office")
    events = res.get("events", [])
    if not events:
        return "Your calendar is blissfully empty, ma'am."
    parts = []
    for ev in events[:10]:
        start = ev.get("start", "")
        title = ev.get("title", "(no title)")
        parts.append(f"{title} at {start}" if start else title)
    return "On your calendar, ma'am: " + " ... ".join(parts)


def calendar_create(
    db: sqlite3.Connection, title: str, start_iso: str, end_iso: str,
    description: str = "",
) -> str:
    verdict, reason = policy.check("calendar_create", f"title={title}")
    if verdict == policy.REFUSE:
        return reason
    params = {"title": title, "start": start_iso, "end": end_iso,
              "description": description}
    if verdict == policy.CONFIRM:
        cid = policy.request_confirmation(
            db, "calendar_create", params,
            detail=f"Create calendar event '{title}' starting {start_iso}",
        )
        return (f"Before I book that, ma'am — just to confirm: '{title}' "
                f"starting {start_iso}. Shall I add it? "
                f"(confirmation {cid})")
    try:
        nat.call("calendar_create", params)
    except nat.BridgeError as e:
        return str(e).replace("mail room", "calendar office")
    return f"'{title}' is on your calendar, ma'am."


def confirm_action(db: sqlite3.Connection, confirmation_id: int) -> str:
    """Execute a pending confirm-first action after Alexandria's approval."""
    row = policy.get_pending(db, confirmation_id)
    if not row or row["status"] != "pending":
        return "There's nothing waiting on that number, ma'am."
    params = json.loads(row["params_json"])
    op = row["op"]
    policy.resolve_confirmation(db, confirmation_id, "approved")
    try:
        nat.call(op, params)
    except nat.BridgeError as e:
        return str(e)
    policy.resolve_confirmation(db, confirmation_id, "executed")
    if op == "gmail_send":
        return f"Sent to {params.get('to')}, ma'am."
    if op == "calendar_create":
        return f"'{params.get('title')}' is on your calendar, ma'am."
    return "Done, ma'am."


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo instant answers — free, no key)
# ---------------------------------------------------------------------------

_DDG_URL = "https://api.duckduckgo.com/"


def _parse_ddg(data: dict) -> str:
    abstract = (data.get("AbstractText") or "").strip()
    topics = []
    for t in data.get("RelatedTopics", []):
        if isinstance(t, dict) and t.get("Text"):
            topics.append(t["Text"].strip())
        elif isinstance(t, dict):
            for sub in t.get("Topics", []):
                if sub.get("Text"):
                    topics.append(sub["Text"].strip())
        if len(topics) >= 3:
            break
    parts = []
    if abstract:
        parts.append(abstract)
    parts.extend(topics[:3])
    if not parts:
        return "I came up empty on that one, ma'am. Shall I try phrasing it differently?"
    out = " ... ".join(parts)
    return out if len(out) <= 900 else out[:900] + " ..."


def web_search(query: str) -> str:
    try:
        resp = requests.get(
            _DDG_URL,
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": "jarvis-personal-agent/1.0"},
            timeout=20,
        )
        resp.raise_for_status()
        return _parse_ddg(resp.json())
    except Exception:
        logger.exception("web search failed")
        return "The web search came up empty-handed, ma'am. Perhaps try again shortly."


# ---------------------------------------------------------------------------
# Weather (Open-Meteo — free, no key)
# ---------------------------------------------------------------------------

_WMO = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "icy fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers",
    81: "showers", 82: "violent showers", 85: "light snow showers",
    86: "snow showers", 95: "thunderstorms", 96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}


def weather(place: str) -> str:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1, "language": "en", "format": "json"},
            timeout=20,
        ).json()
        results = geo.get("results") or []
        if not results:
            return f"I couldn't find a place called {place}, ma'am."
        loc = results[0]
        fc = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                           "weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
            timeout=20,
        ).json()
        cur = fc["current"]
        desc = _WMO.get(cur.get("weather_code"), "unsettled skies")
        name = loc.get("name", place)
        country = loc.get("country", "")
        where = f"{name}, {country}" if country else name
        return (
            f"In {where}, ma'am: {desc}, {round(cur['temperature_2m'])} degrees, "
            f"feels like {round(cur['apparent_temperature'])}. "
            f"Humidity {cur['relative_humidity_2m']} percent, "
            f"wind {round(cur['wind_speed_10m'])} miles per hour."
        )
    except Exception:
        logger.exception("weather lookup failed")
        return "The weather vane seems stuck, ma'am. Shall I try again shortly?"


# ---------------------------------------------------------------------------
# Status / memory helpers exposed as tools
# ---------------------------------------------------------------------------

def get_status(db: sqlite3.Connection) -> str:
    pending = db.execute(
        "SELECT COUNT(*) c FROM reminders WHERE fired = 0").fetchone()["c"]
    unannounced = db.execute(
        "SELECT COUNT(*) c FROM due_outbox WHERE announced = 0").fetchone()["c"]
    return (f"All systems nominal, ma'am. {pending} reminder{'s' if pending != 1 else ''} "
            f"pending, {unannounced} awaiting announcement.")


# ---------------------------------------------------------------------------
# CallCovered knowledge base (local, read-only -> auto-allowed)
# ---------------------------------------------------------------------------

def kb_search(db: sqlite3.Connection, query: str) -> str:
    from . import kb as kbmod
    hits = kbmod.search_kb(db, query, limit=3)
    if not hits:
        return ("Nothing in the CallCovered handbook on that, ma'am. "
                "Shall I look it up on the web instead?")
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower())
             if t not in kbmod._STOPWORDS and len(t) > 1]
    parts = []
    for h in hits:
        snippet = _best_snippet(h["body"], terms)
        parts.append(f"{h['title']}: {snippet}")
    return "From the handbook, ma'am: " + " ... ".join(parts)


def _best_snippet(body: str, terms: list[str], max_chars: int = 450) -> str:
    """Pick the sentences with the most query-term overlap (voice-friendly)."""
    text = body.replace("\n", " ")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return text[:max_chars]
    def score(s: str) -> int:
        low = s.lower()
        return sum(low.count(t) for t in terms)
    ranked = sorted(sentences, key=score, reverse=True)
    if not terms or score(ranked[0]) == 0:
        chosen = sentences[:2]
    else:
        chosen = [s for s in ranked if score(s) > 0][:3]
    out = " ".join(chosen)
    return out if len(out) <= max_chars else out[:max_chars] + " ..."


# ---------------------------------------------------------------------------
# CallCovered client onboarding (local records -> auto-allowed)
# ---------------------------------------------------------------------------

_STAGES = ["intake", "a2p", "subaccount", "snapshot", "forwarding",
           "voice_config", "test_call", "live", "paused"]

_STAGE_NEXT = {
    "intake": ("a2p", "collect their business details, then start A2P registration — "
               "texts can't go out until the carrier approves it"),
    "a2p": ("subaccount", "provision their CallCovered sub-account"),
    "subaccount": ("snapshot", "deploy the roofing snapshot"),
    "snapshot": ("forwarding", "get call forwarding or the tracking number live"),
    "forwarding": ("voice_config", "configure the AI voice agent and greeting"),
    "voice_config": ("test_call", "place a live test call and verify booking"),
    "test_call": ("live", "go live, then set day-1, day-3 and day-7 check-in reminders"),
    "live": ("live", "they're live — keep up the check-ins"),
    "paused": ("intake", "resume them back at intake"),
}


def client_add(db: sqlite3.Connection, business_name: str, owner_name: str = "",
               phone: str = "", email: str = "", tier: str = "") -> str:
    business_name = (business_name or "").strip()
    if not business_name:
        return "I need the business name to start onboarding, ma'am."
    cur = db.execute(
        """INSERT INTO clients
           (business_name, owner_name, phone, email, tier, stage, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'intake', ?, ?)""",
        (business_name, owner_name.strip(), phone.strip(), email.strip(),
         tier.strip(), _now(), _now()),
    )
    db.commit()
    cid = cur.lastrowid
    return (f"{business_name} is in the onboarding pipeline as client #{cid}, ma'am, "
            f"at the intake stage. Next: {_STAGE_NEXT['intake'][1]}, ma'am.")


def client_stage(db: sqlite3.Connection, client_id: int, stage: str) -> str:
    stage = (stage or "").strip().lower()
    if stage not in _STAGES:
        return (f"That isn't a pipeline stage, ma'am. The stages are: "
                f"{', '.join(_STAGES[:-1])}, or paused.")
    row = db.execute("SELECT id, business_name FROM clients WHERE id = ?",
                     (client_id,)).fetchone()
    if not row:
        return f"No client #{client_id} on file, ma'am."
    db.execute("UPDATE clients SET stage = ?, updated_at = ? WHERE id = ?",
               (stage, _now(), client_id))
    db.commit()
    nxt, hint = _STAGE_NEXT[stage]
    if stage == "live":
        return (f"{row['business_name']} is live, ma'am. {hint}.")
    return (f"{row['business_name']} moved to {stage}, ma'am. Next: {hint}.")


def client_list(db: sqlite3.Connection, stage: str = "") -> str:
    stage = (stage or "").strip().lower()
    if stage and stage not in _STAGES:
        return f"That isn't a pipeline stage, ma'am."
    q = "SELECT id, business_name, owner_name, tier, stage FROM clients ORDER BY id"
    args: tuple = ()
    if stage:
        q = ("SELECT id, business_name, owner_name, tier, stage FROM clients "
             "WHERE stage = ? ORDER BY id")
        args = (stage,)
    rows = db.execute(q, args).fetchall()
    if not rows:
        return "No clients in the pipeline, ma'am."
    parts = [f"#{r['id']} {r['business_name']} ({r['stage']})"
             + (f" — {r['tier']}" if r['tier'] else "") for r in rows]
    return "Onboarding pipeline, ma'am: " + " ... ".join(parts)


def client_get(db: sqlite3.Connection, client_id: int) -> str:
    row = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        return f"No client #{client_id} on file, ma'am."
    notes = db.execute(
        "SELECT note, created_at FROM client_notes WHERE client_id = ? "
        "ORDER BY id DESC LIMIT 3", (client_id,)).fetchall()
    bits = [f"{row['business_name']}", f"stage: {row['stage']}"]
    if row["owner_name"]:
        bits.append(f"owner: {row['owner_name']}")
    if row["tier"]:
        bits.append(f"tier: {row['tier']}")
    if row["phone"]:
        bits.append(f"phone: {row['phone']}")
    detail = ", ".join(bits)
    if notes:
        detail += ". Recent notes: " + " ... ".join(n["note"] for n in notes)
    return detail + ", ma'am."


def client_note(db: sqlite3.Connection, client_id: int, note: str) -> str:
    note = (note or "").strip()
    if not note:
        return "I didn't catch the note, ma'am."
    row = db.execute("SELECT business_name FROM clients WHERE id = ?",
                     (client_id,)).fetchone()
    if not row:
        return f"No client #{client_id} on file, ma'am."
    db.execute(
        "INSERT INTO client_notes (client_id, note, created_at) VALUES (?, ?, ?)",
        (client_id, note, _now()),
    )
    db.execute("UPDATE clients SET updated_at = ? WHERE id = ?", (_now(), client_id))
    db.commit()
    return f"Logged against {row['business_name']}, ma'am."
