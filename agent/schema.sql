-- Jarvis personal agent storage. Created with IF NOT EXISTS so the
-- original tables (from the first scaffolding pass) are left untouched.

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    fired INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
-- fired: 0 = pending, 1 = fired into due_outbox, 2 = cancelled

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Reminders whose time has come. Delivery wiring (voice announce / push)
-- reads from here; the agent marks rows announced once spoken.
CREATE TABLE IF NOT EXISTS due_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id INTEGER NOT NULL,
    note TEXT NOT NULL,
    due_at TEXT NOT NULL,
    enqueued_at TEXT NOT NULL,
    announced INTEGER NOT NULL DEFAULT 0
);

-- Confirm-first actions waiting on Alexandria's spoken approval.
CREATE TABLE IF NOT EXISTS pending_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op TEXT NOT NULL,
    params_json TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
-- status: pending | approved | denied | executed

-- Cross-session memory.
CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    due_at TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
