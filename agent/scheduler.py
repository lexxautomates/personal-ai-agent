"""Background reminder watcher.

A daemon thread in the agent process checks every 60s for reminders whose
time has come and moves them into the due_outbox table. Delivery (speaking
them aloud, pushing them) reads from due_outbox and is wired separately.
"""

import logging
import threading
import time
from datetime import datetime, timezone

from . import db as dbmod

logger = logging.getLogger("jarvis.scheduler")

_started: dict[str, threading.Thread] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fire_due(conn_or_path=None) -> int:
    """Move due reminders into due_outbox. Returns the count moved."""
    if isinstance(conn_or_path, str) or conn_or_path is None:
        conn = dbmod.connect(conn_or_path)
        close = True
    else:
        conn = conn_or_path
        close = False
    try:
        now = _utcnow_iso()
        due = conn.execute(
            "SELECT id, note, scheduled_at FROM reminders "
            "WHERE fired = 0 AND scheduled_at <= ?",
            (now,),
        ).fetchall()
        for row in due:
            conn.execute(
                "INSERT INTO due_outbox (reminder_id, note, due_at, enqueued_at) "
                "VALUES (?, ?, ?, ?)",
                (row["id"], row["note"], row["scheduled_at"], now),
            )
            conn.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return len(due)
    finally:
        if close:
            conn.close()


def start_reminder_watcher(db_path: str | None = None, interval: int = 60) -> threading.Thread:
    """Start (once per process) the daemon thread that fires due reminders."""
    key = db_path or dbmod.db_path()
    if key in _started and _started[key].is_alive():
        return _started[key]

    def loop() -> None:
        while True:
            try:
                moved = fire_due(key)
                if moved:
                    logger.info("fired %d due reminder(s) into outbox", moved)
            except Exception:
                logger.exception("reminder watcher tick failed")
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True, name="jarvis-reminder-watcher")
    t.start()
    _started[key] = t
    logger.info("reminder watcher started (interval=%ss)", interval)
    return t
