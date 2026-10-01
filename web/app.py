# Flask companion web layer for Jarvis, Alexandria's personal AI butler.
#
# HTTP face of the assistant:
#   GET  /health   - liveness: web process, sqlite, agent HTTP, LiveKit TCP
#   GET  /status   - session counters + agent/web state
#   POST /status/session - agent runtime reports session start/end
#   GET  /config   - public config surface (no secrets)
#   GET  /token    - mint a LiveKit access token for the client (secret-gated)
#   GET  /pending  - list pending confirm-first actions (secret-gated)
#   POST /pending/<id>/resolve - approve/reject a pending action (secret-gated)
#
# This is NOT the agent runtime; the runtime is the LiveKit agents SDK
# process in agent/ (AgentServer on :8081).

import os
import sys
import json
import socket
import asyncio
import logging
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, request

# Import the agent package (db/policy) from the repo root regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db as dbmod      # noqa: E402
from agent import policy as policymod  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis-web")

app = Flask(__name__)

_status = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "sessions_today": 0,
    "agent_running": False,
    "web_running": True,
}


def _admin_ok() -> bool:
    """Admin endpoints require the shared secret (client sends it too)."""
    expected = os.environ.get("JARVIS_WEBHOOK_SECRET", "")
    if not expected:
        return False
    got = request.headers.get("X-Jarvis-Secret", "")
    return bool(got) and got == expected


def _check_agent() -> dict:
    """Is the AgentServer HTTP process answering?"""
    try:
        req = urllib.request.Request("http://127.0.0.1:8081/", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health detail only
        return {"ok": False, "error": str(exc)[:120]}


def _check_livekit() -> dict:
    """Is the LiveKit server TCP port open?"""
    try:
        with socket.create_connection(("127.0.0.1", 7880), timeout=3):
            return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health detail only
        return {"ok": False, "error": str(exc)[:120]}


def _check_db() -> dict:
    try:
        dbmod.init_db()
        conn = dbmod.connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health detail only
        return {"ok": False, "error": str(exc)[:120]}


@app.get("/health")
def health():
    db = _check_db()
    agent = _check_agent()
    livekit = _check_livekit()
    overall = "ok" if (db["ok"] and agent["ok"] and livekit["ok"]) else "degraded"
    return jsonify({
        "status": overall,
        "utc": datetime.now(timezone.utc).isoformat(),
        "checks": {"db": db, "agent": agent, "livekit": livekit},
    }), 200 if overall == "ok" else 503


@app.get("/status")
def status():
    return jsonify(_status)


@app.post("/status/session")
def record_session():
    """Called by the agent runtime when a session starts/ends."""
    body = request.get_json(silent=True) or {}
    action = body.get("action")
    if action == "start":
        _status["sessions_today"] = _status.get("sessions_today", 0) + 1
        _status["agent_running"] = True
    elif action == "end":
        _status["agent_running"] = False
    else:
        return jsonify({"error": "unknown action"}), 400
    return jsonify(_status)


@app.get("/config")
def config():
    """Public config surface. Secrets never exposed here."""
    return jsonify({
        "agent": {"name": "jarvis"},
        "livekit_public_url": os.environ.get("LIVEKIT_PUBLIC_URL", ""),
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "token": "/token",
            "pending": "/pending",
        },
    })


@app.get("/token")
def token():
    """Mint a LiveKit access token for Alexandria's client.

    Secret-gated: the client sends X-Jarvis-Secret. Query params:
    identity (default 'alexandria'), room (default 'jarvis').
    """
    if not _admin_ok():
        return jsonify({"error": "forbidden"}), 403
    api_key = os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "")
    if not api_key or not api_secret:
        return jsonify({"error": "livekit not configured"}), 503
    from livekit import api as lk_api
    from datetime import timedelta

    identity = request.args.get("identity", "alexandria")
    room = request.args.get("room", "jarvis")
    grant = lk_api.VideoGrants(room_join=True, room=room)
    at = (
        lk_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_grants(grant)
        .with_ttl(timedelta(hours=1))
    )
    token_str = at.to_jwt()

    # Summon the worker into the room (idempotent: skip if already dispatched).
    dispatch_status = asyncio.run(_ensure_agent_dispatch(room))

    return jsonify({
        "token": token_str,
        "url": os.environ.get("LIVEKIT_PUBLIC_URL", ""),
        "room": room,
        "identity": identity,
        "agent_dispatch": dispatch_status,
    })


async def _ensure_agent_dispatch(room: str) -> str:
    """Summon the worker into `room`.

    Uses room creation with an agent dispatch attached (CreateRoomRequest
    agents=[...]): the LiveKit server then assigns our registered "jarvis"
    worker a job for the room. The standalone AgentDispatchService API is
    broken in livekit-server v1.13.7 (psrpc "no response from servers"), so
    we go through the room service instead.

    The room is deleted first when it already exists so every token mints a
    fresh session with the agent attached (single-user butler: no concurrent
    calls to preserve).
    """
    try:
        import aiohttp
        from livekit.api import room_service as rs
        from livekit.api import (
            CreateRoomRequest,
            DeleteRoomRequest,
            ListRoomsRequest,
            RoomAgentDispatch,
        )

        ws_url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
        api_url = ws_url.replace("ws://", "http://").replace("wss://", "https://")
        async with aiohttp.ClientSession() as session:
            svc = rs.RoomService(
                session,
                api_url,
                os.environ.get("LIVEKIT_API_KEY", ""),
                os.environ.get("LIVEKIT_API_SECRET", ""),
            )
            rooms = await svc.list_rooms(ListRoomsRequest(names=[room]))
            if any(r.name == room for r in rooms.rooms):
                await svc.delete_room(DeleteRoomRequest(room=room))
                await asyncio.sleep(1)
            await svc.create_room(
                CreateRoomRequest(
                    name=room,
                    agents=[RoomAgentDispatch(agent_name="jarvis")],
                )
            )
            return "dispatched"
    except Exception as exc:  # noqa: BLE001 - token stays valid regardless
        logger.warning("agent dispatch failed for room %s: %s", room, exc)
        return f"dispatch_failed: {str(exc)[:100]}"


@app.get("/pending")
def pending_list():
    """Pending confirm-first actions awaiting Alexandria's yes/no."""
    if not _admin_ok():
        return jsonify({"error": "forbidden"}), 403
    dbmod.init_db()
    conn = dbmod.connect()
    rows = conn.execute(
        "SELECT id, op, params_json, detail, created_at, status "
        "FROM pending_confirmations ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify({"pending": [dict(r) for r in rows]})


@app.post("/pending/<int:confirmation_id>/resolve")
def pending_resolve(confirmation_id: int):
    """Approve or reject a pending action. Body: {"decision": "approve"|"reject"}.

    Approval here only marks intent; the voice runtime executes approved
    actions via its confirm_action tool on the next turn.
    """
    if not _admin_ok():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        return jsonify({"error": "decision must be approve or reject"}), 400
    dbmod.init_db()
    conn = dbmod.connect()
    row = policymod.get_pending(conn, confirmation_id)
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404
    policymod.resolve_confirmation(conn, confirmation_id, decision + "d")
    conn.close()
    return jsonify({"id": confirmation_id, "status": decision + "d"})


@app.get("/voice")
def voice_client():
    """Browser voice client for Alexandria.

    Secret-gated via ?key= query param (browsers can't set headers on page load).
    Mints a fresh LiveKit token server-side and embeds it in the page.
    The token is a one-time JWT for a fresh room — the secret never leaves the server.
    """
    expected = os.environ.get("JARVIS_WEBHOOK_SECRET", "")
    got = request.args.get("key", "")
    if not expected or not got or got != expected:
        return "Forbidden", 403

    import asyncio
    from livekit import api as lk_api
    from datetime import timedelta

    api_key = os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "")
    if not api_key or not api_secret:
        return "LiveKit not configured", 503

    room = "jarvis"
    grant = lk_api.VideoGrants(room_join=True, room=room)
    at = (
        lk_api.AccessToken(api_key, api_secret)
        .with_identity("alexandria")
        .with_grants(grant)
        .with_ttl(timedelta(hours=1))
    )
    token_str = at.to_jwt()
    dispatch_status = asyncio.run(_ensure_agent_dispatch(room))
    livekit_url = os.environ.get("LIVEKIT_PUBLIC_URL", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jarvis Voice</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 20px; text-align: center; background: #0f1419; color: #e8e8e8; }}
  h1 {{ font-size: 28px; margin-bottom: 8px; }}
  p {{ color: #8899a6; line-height: 1.5; }}
  #status {{ margin: 20px 0; padding: 12px; border-radius: 8px; background: #1a222b; min-height: 20px; }}
  button {{ font-size: 20px; padding: 16px 48px; border: none; border-radius: 50px; background: #1d9bf0; color: white; cursor: pointer; margin: 10px; }}
  button:disabled {{ background: #333; cursor: default; }}
  button.stop {{ background: #f4212e; }}
  .hint {{ font-size: 13px; color: #666; margin-top: 20px; }}
</style>
</head>
<body>
<h1>🎩 Jarvis</h1>
<p>Tap Start, allow the microphone, and speak.</p>
<div id="status">Ready.</div>
<button id="startBtn" onclick="start()">Start Talking</button>
<button id="stopBtn" class="stop" onclick="stop()" disabled>Stop</button>
<div class="hint">Keep this tab open while you talk. Jarvis replies out loud.</div>
<script src="https://cdn.jsdelivr.net/npm/livekit-client@2/dist/livekit-client.umd.min.js"></script>
<script>
const TOKEN = {token_str!r};
const URL = {livekit_url!r};
let room = null;
const status = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
function setStatus(t) {{ status.textContent = t; }}

async function start() {{
  startBtn.disabled = true;
  try {{
    setStatus('Connecting...');
    room = new LivekitClient.Room();
    room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, pub, participant) => {{
      if (track.kind === LivekitClient.Track.Kind.Audio) {{
        const el = track.attach();
        el.style.display = 'none';
        document.body.appendChild(el);
        setStatus('Jarvis is speaking...');
        track.on(LivekitClient.TrackEvent.Ended, () => setStatus('Listening...'));
      }}
    }});
    room.on(LivekitClient.RoomEvent.Disconnected, () => {{
      setStatus('Disconnected.');
      startBtn.disabled = false; stopBtn.disabled = true;
    }});
    await room.connect(URL, TOKEN);
    setStatus('Enabling microphone...');
    await room.localParticipant.setMicrophoneEnabled(true);
    setStatus('Listening... speak now.');
    stopBtn.disabled = false;
  }} catch (e) {{
    setStatus('Error: ' + e.message);
    startBtn.disabled = false;
  }}
}}
async function stop() {{
  if (room) await room.disconnect();
  startBtn.disabled = false; stopBtn.disabled = true;
  setStatus('Stopped.');
}}
</script>
</body>
</html>"""
    return html


def main():
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info("Starting jarvis-web on port %s", port)
    app.run(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    main()
