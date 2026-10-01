"""Cross-session memory on sqlite: profile, episodic log, follow-ups."""

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- profile (key/value) -----------------------------------------------------

def profile_get(db: sqlite3.Connection, key: str, default: str = "") -> str:
    row = db.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def profile_set(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO profile (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def profile_all(db: sqlite3.Connection) -> dict:
    return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM profile")}


# -- episodic log ------------------------------------------------------------

def log_episode(db: sqlite3.Connection, summary: str, started_at: str) -> None:
    db.execute(
        "INSERT INTO episodic (summary, started_at, ended_at) VALUES (?, ?, ?)",
        (summary, started_at, _now()),
    )
    db.commit()


def recent_episodes(db: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM episodic ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# -- follow-ups --------------------------------------------------------------

def add_follow_up(db: sqlite3.Connection, text: str, due_at: str | None = None) -> int:
    cur = db.execute(
        "INSERT INTO follow_ups (text, due_at, created_at) VALUES (?, ?, ?)",
        (text, due_at, _now()),
    )
    db.commit()
    return int(cur.lastrowid)


def open_follow_ups(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM follow_ups WHERE done = 0 ORDER BY id"
    ).fetchall()


def complete_follow_up(db: sqlite3.Connection, follow_up_id: int) -> None:
    db.execute("UPDATE follow_ups SET done = 1 WHERE id = ?", (follow_up_id,))
    db.commit()


# -- startup context ---------------------------------------------------------

def startup_context(db: sqlite3.Connection) -> str:
    """Short brief injected into the agent instructions at session start."""
    lines: list[str] = []
    prof = profile_all(db)
    if prof:
        lines.append("What you know about Alexandria: " +
                     "; ".join(f"{k} = {v}" for k, v in prof.items()))
    fus = open_follow_ups(db)
    if fus:
        lines.append("Open follow-ups: " +
                     "; ".join(f"#{r['id']} {r['text']}" for r in fus))
    eps = recent_episodes(db, 3)
    if eps:
        lines.append("Recent sessions: " +
                     " | ".join(r["summary"] for r in eps))
    return "\n".join(lines)
