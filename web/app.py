# Flask companion web layer for the personal AI assistant.
#
# This is the HTTP face of the assistant: health, status, config, and later
# integration hooks that Zapier or other services call. It is NOT the agent
# runtime; the agent runtime is the LiveKit agents SDK process in agent/.
#
# Substrate: lexxautomates/agents + lexxautomates/livekit
# Reference: friday_jarvis shape for the agent

import os
import json
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal-ai-web")

app = Flask(__name__)

# Simple in-memory status for the first pass.
_status = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "sessions_today": 0,
    "agent_running": False,
    "web_running": True,
}


@app.get("/health")
def health():
    return jsonify({"status": "ok", "utc": datetime.now(timezone.utc).isoformat()})


@app.get("/status")
def status():
    return jsonify(_status)


@app.post("/status/session")
def record_session():
    """Called by the agent runtime when a session starts/ends. First-pass hook."""
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
        "agent": {"name": "personal-ai-agent"},
        "endpoints": {"health": "/health", "status": "/status"},
    })


def main():
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info("Starting personal-ai-web on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
