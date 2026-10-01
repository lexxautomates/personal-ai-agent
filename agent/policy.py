"""Permission layer for Jarvis.

Every tool that writes to the outside world must call policy.check() first.

Verdicts:
  allow   - reads and local, reversible writes (notes, reminders, drafts).
  confirm - external writes (sending mail, creating calendar events). The tool
            records a pending confirmation and asks Alexandria aloud; a second
            tool (confirm_action) executes it after her spoken approval.
  refuse  - destructive, irreversible, or out-of-scope actions. Refused with a
            plain-English explanation, never executed.
"""

import json
import sqlite3
from datetime import datetime, timezone

ALLOW = "allow"
CONFIRM = "confirm"
REFUSE = "refuse"

# Reads + local, fully reversible writes. No outside-world effect.
_AUTO_ALLOW = {
    "gmail_search",
    "gmail_read",
    "gmail_draft",
    "calendar_list",
    "notes_jot",
    "notes_list",
    "notes_search",
    "reminder_add",
    "reminder_list",
    "reminder_cancel",
    "check_due_reminders",
    "web_search",
    "weather",
    "confirm_action",
    "get_status",
    "memory_profile_get",
    "memory_follow_ups",
}

# External writes: must be confirmed aloud before execution.
_CONFIRM_FIRST = {
    "gmail_send",
    "calendar_create",
}

# Substrings that mark an action destructive / irreversible / out of scope.
# Matched against the tool/op name for anything not explicitly allow-listed.
_REFUSE_PATTERNS = (
    "delete",
    "destroy",
    "drop_",
    "purge",
    "publish",
    "post_",
    "tweet",
    "pay",
    "transfer",
    "withdraw",
    "trade",
    "buy",
    "sell",
    "order",
    "subscribe",
    "unsubscribe",
    "shell",
    "exec",
    "run_command",
    "sudo",
    "chmod",
    "rm_",
    "shutdown",
    "reboot",
    "password",
    "credential",
    "settings",
    "forward",  # forwarding someone else's mail is a leak risk
)


def check(tool_name: str, detail: str = "") -> tuple[str, str]:
    """Return (verdict, reason) for a tool about to run."""
    name = (tool_name or "").lower()

    if name in _AUTO_ALLOW:
        return ALLOW, "read or local reversible action"
    if name in _CONFIRM_FIRST:
        return CONFIRM, "external write needs Alexandria's confirmation"

    for pat in _REFUSE_PATTERNS:
        if pat in name:
            return REFUSE, (
                f"'{tool_name}' looks destructive or out of scope ({detail or 'no detail given'}). "
                "I won't do that on my own, ma'am — let's have a human handle it."
            )

    # Safe default: unknown actions need a yes, never a silent go.
    return CONFIRM, f"'{tool_name}' is not on the allow-list, so it needs confirmation"


def request_confirmation(
    db: sqlite3.Connection, op: str, params: dict, detail: str
) -> int:
    """Record a pending confirm-first action. Returns the confirmation id."""
    now = datetime.now(timezone.utc).isoformat()
    cur = db.execute(
        "INSERT INTO pending_confirmations (op, params_json, detail, created_at) "
        "VALUES (?, ?, ?, ?)",
        (op, json.dumps(params), detail, now),
    )
    db.commit()
    return int(cur.lastrowid)


def get_pending(db: sqlite3.Connection, confirmation_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM pending_confirmations WHERE id = ?", (confirmation_id,)
    ).fetchone()


def resolve_confirmation(db: sqlite3.Connection, confirmation_id: int, status: str) -> None:
    db.execute(
        "UPDATE pending_confirmations SET status = ? WHERE id = ?",
        (status, confirmation_id),
    )
    db.commit()
