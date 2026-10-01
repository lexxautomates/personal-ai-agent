import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import db as dbmod  # noqa: E402


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "jarvis-test.db")


@pytest.fixture()
def conn(db_path):
    dbmod.init_db(db_path)
    c = dbmod.connect(db_path)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("JARVIS_DB", raising=False)
    monkeypatch.delenv("JARVIS_NAT_WEBHOOK", raising=False)
    monkeypatch.delenv("JARVIS_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
