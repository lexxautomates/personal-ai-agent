"""LiveKit @function_tool wrappers around the real implementations.

Each tool is voice-shaped: short spoken replies, no markdown, no lists.
"""

import sqlite3

from livekit.agents import RunContext, function_tool

from . import db as dbmod
from . import tool_impls as impl

_db_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        dbmod.init_db()
        _db_conn = dbmod.connect()
    return _db_conn


@function_tool()
async def notes_jot(context: RunContext, text: str) -> str:
    """Jot a quick note for Alexandria. text: what she wants remembered."""
    return impl.notes_jot(_db(), text)


@function_tool()
async def notes_list(context: RunContext, limit: int = 10) -> str:
    """List Alexandria's recent notes, newest first."""
    return impl.notes_list(_db(), limit)


@function_tool()
async def notes_search(context: RunContext, query: str) -> str:
    """Search Alexandria's notes for a word or phrase."""
    return impl.notes_search(_db(), query)


@function_tool()
async def reminder_add(context: RunContext, note: str, at_iso: str) -> str:
    """Schedule a reminder. at_iso: ISO datetime like 2026-10-02T09:00:00."""
    return impl.reminder_add(_db(), note, at_iso)


@function_tool()
async def reminder_list(context: RunContext) -> str:
    """List Alexandria's pending reminders."""
    return impl.reminder_list(_db())


@function_tool()
async def reminder_cancel(context: RunContext, reminder_id: int) -> str:
    """Cancel a pending reminder by its number."""
    return impl.reminder_cancel(_db(), reminder_id)


@function_tool()
async def check_due_reminders(context: RunContext) -> str:
    """Read reminders that came due and announce them. Empty when none."""
    return impl.check_due_reminders(_db())


@function_tool()
async def gmail_search(context: RunContext, query: str, max_results: int = 5) -> str:
    """Search Alexandria's Gmail. query: Gmail search string."""
    return impl.gmail_search(query, max_results)


@function_tool()
async def gmail_read(context: RunContext, message_id: str) -> str:
    """Read one Gmail message by its id."""
    return impl.gmail_read(message_id)


@function_tool()
async def gmail_draft(context: RunContext, to: str, subject: str, body: str) -> str:
    """Save a Gmail draft (never sends)."""
    return impl.gmail_draft(to, subject, body)


@function_tool()
async def gmail_send(context: RunContext, to: str, subject: str, body: str) -> str:
    """Send an email. CONFIRM-FIRST: asks Alexandria aloud before sending."""
    return impl.gmail_send(_db(), to, subject, body)


@function_tool()
async def calendar_list(context: RunContext, days: int = 7) -> str:
    """List upcoming calendar events for the next N days."""
    return impl.calendar_list(days)


@function_tool()
async def calendar_create(
    context: RunContext, title: str, start_iso: str, end_iso: str, description: str = ""
) -> str:
    """Create a calendar event. CONFIRM-FIRST: asks Alexandria aloud first."""
    return impl.calendar_create(_db(), title, start_iso, end_iso, description)


@function_tool()
async def confirm_action(context: RunContext, confirmation_id: int) -> str:
    """Execute a pending confirm-first action after Alexandria says yes."""
    return impl.confirm_action(_db(), confirmation_id)


@function_tool()
async def web_search(context: RunContext, query: str) -> str:
    """Look something up on the web (DuckDuckGo instant answers)."""
    return impl.web_search(query)


@function_tool()
async def weather(context: RunContext, place: str) -> str:
    """Current weather for a city or place (Open-Meteo)."""
    return impl.weather(place)


@function_tool()
async def get_status(context: RunContext) -> str:
    """Report the assistant's own status: reminders pending, etc."""
    return impl.get_status(_db())


ALL_TOOLS = [
    notes_jot, notes_list, notes_search,
    reminder_add, reminder_list, reminder_cancel, check_due_reminders,
    gmail_search, gmail_read, gmail_draft, gmail_send,
    calendar_list, calendar_create, confirm_action,
    web_search, weather, get_status,
]
