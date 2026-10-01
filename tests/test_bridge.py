"""Nat bridge client against a fake HTTP server.

Verifies: op/params JSON body, X-Jarvis-Secret header, and graceful
plain-English failures (no tracebacks) when the bridge is down or rude.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent import nat, tool_impls


class _Handler(BaseHTTPRequestHandler):
    seen = None  # class-level capture of the last request

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _Handler.seen = {
            "path": self.path,
            "secret": self.headers.get("X-Jarvis-Secret"),
            "body": body,
        }
        mode = getattr(self.server, "mode", "ok")
        if mode == "boom":
            self.send_response(500)
            self.end_headers()
            return
        payload = {"messages": [{"from": "boss@corp.com", "subject": "Q4 numbers",
                                 "date": "today", "id": "m1"}]}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def bridge(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.mode = "ok"
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    monkeypatch.setenv("JARVIS_NAT_WEBHOOK",
                       f"http://127.0.0.1:{server.server_port}/webhook/jarvis-tools")
    monkeypatch.setenv("JARVIS_WEBHOOK_SECRET", "s3cret")
    yield server
    server.shutdown()


def test_bridge_posts_op_params_and_secret(bridge):
    nat.call("gmail_search", {"query": "q4"})
    seen = _Handler.seen
    assert seen["path"] == "/webhook/jarvis-tools"
    assert seen["secret"] == "s3cret"
    assert seen["body"] == {"op": "gmail_search", "params": {"query": "q4"}}


def test_gmail_search_formats_results(bridge):
    out = tool_impls.gmail_search("q4")
    assert "boss@corp.com" in out and "Q4 numbers" in out


def test_bridge_500_gives_plain_english(bridge):
    bridge.mode = "boom"
    with pytest.raises(nat.BridgeError) as exc:
        nat.call("gmail_search", {})
    assert "Traceback" not in str(exc.value)
    assert "mail room" in str(exc.value)


def test_bridge_down_gives_plain_english(monkeypatch):
    monkeypatch.setenv("JARVIS_NAT_WEBHOOK", "http://127.0.0.1:9/webhook/x")
    out = tool_impls.gmail_search("anything")
    assert "mail room is unreachable" in out
    assert "Traceback" not in out


def test_gmail_send_asks_first_then_executes(conn, bridge):
    # First call: confirm-first, nothing sent.
    ask = tool_impls.gmail_send(conn, "a@b.c", "Hi", "body here")
    assert "just to confirm" in ask and "a@b.c" in ask
    cid = int(ask.rsplit("confirmation ", 1)[1].rstrip(")"))
    # Approve: now it actually POSTs.
    done = tool_impls.confirm_action(conn, cid)
    assert "Sent to a@b.c" in done
    assert _Handler.seen["body"]["op"] == "gmail_send"
    assert _Handler.seen["body"]["params"]["to"] == "a@b.c"


def test_confirm_unknown_id(conn, bridge):
    assert "nothing waiting" in tool_impls.confirm_action(conn, 424242)
