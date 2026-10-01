"""CallCovered knowledge base: seed from agent/kb/*.md, search via FTS5.

Each markdown file is split on `## ` headings; every section becomes one
searchable article titled by its heading. stdlib only.
"""

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

KB_DIR = Path(__file__).with_name("kb")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_kb_file(path: Path) -> list[tuple[str, str]]:
    """Split a markdown file into (title, body) articles on ## headings."""
    text = path.read_text(encoding="utf-8")
    articles: list[tuple[str, str]] = []
    title: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            if title is not None:
                articles.append((title, "\n".join(buf).strip()))
            title = m.group(1).strip()
            buf = []
        elif title is not None:
            buf.append(line)
    if title is not None:
        articles.append((title, "\n".join(buf).strip()))
    return [(t, b) for t, b in articles if b]


def seed_kb(db, force: bool = False) -> int:
    """Load agent/kb/*.md into kb_articles + kb_fts. Returns article count."""
    if not KB_DIR.is_dir():
        return 0
    count = 0
    for path in sorted(KB_DIR.glob("*.md")):
        for title, body in parse_kb_file(path):
            if force:
                db.execute("DELETE FROM kb_articles WHERE title = ?", (title,))
            db.execute(
                """INSERT OR IGNORE INTO kb_articles (title, body, source, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (title, body, path.name, _now()),
            )
            count += 1
    # Rebuild the FTS index from the articles table (external-content FTS5
    # tables are rebuilt with the special 'rebuild' command, not DELETE).
    db.execute("INSERT INTO kb_fts(kb_fts) VALUES('rebuild')")
    db.commit()
    return count


_STOPWORDS = frozenset(
    "how much is the a an what does do did it its in on of for to and or me "
    "tell about please can you your my we they them this that with from".split()
)


def _fts_query(query: str) -> str:
    """Turn a conversational query into an OR of meaningful FTS5 terms."""
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    terms = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    # Quote each term so FTS5 treats them literally.
    return " OR ".join(f'"{t}"' for t in terms)


def search_kb(db, query: str, limit: int = 3) -> list[dict]:
    """Full-text search; falls back to LIKE when FTS has no hits."""
    query = (query or "").strip()
    if not query:
        return []
    rows: list = []
    fts_q = _fts_query(query)
    if fts_q:
        try:
            rows = db.execute(
                """SELECT a.title, a.body
                   FROM kb_fts f JOIN kb_articles a ON a.id = f.rowid
                   WHERE kb_fts MATCH ? ORDER BY rank LIMIT ?""",
                (fts_q, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    if not rows:
        rows = db.execute(
            """SELECT title, body FROM kb_articles
               WHERE title LIKE ? OR body LIKE ? LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    return [{"title": r["title"], "body": r["body"]} for r in rows]
