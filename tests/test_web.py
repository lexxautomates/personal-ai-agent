"""Smoke tests for Flask web routes (no secret required paths)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.app import app


def test_health_ok():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "checks" in data


def test_voice_requires_key():
    client = app.test_client()
    resp = client.get("/voice")
    assert resp.status_code == 403
    resp = client.get("/voice?key=wrong")
    assert resp.status_code == 403


def test_token_requires_secret():
    client = app.test_client()
    resp = client.get("/token")
    assert resp.status_code == 403


def test_pending_requires_secret():
    client = app.test_client()
    resp = client.get("/pending")
    assert resp.status_code == 403
