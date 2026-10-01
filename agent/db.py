"""SQLite plumbing for the Jarvis agent. One file, stdlib only."""

import os
import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


def db_path() -> str:
    return os.environ.get("JARVIS_DB", str(Path.home() / ".jarvis" / "jarvis.db"))


def connect(path: str | None = None) -> sqlite3.Connection:
    p = path or db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | None = None) -> str:
    """Create all tables (idempotent). Returns the db path."""
    p = path or db_path()
    conn = connect(p)
    try:
        conn.executescript(_SCHEMA.read_text())
        conn.commit()
    finally:
        conn.close()
    return p
