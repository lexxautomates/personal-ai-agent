"""Thin client for the Nat (n8n) tool bridge.

Every Gmail/Calendar operation is a POST to the bridge webhook:
    {"op": "<op>", "params": {...}}
with header X-Jarvis-Secret from JARVIS_WEBHOOK_SECRET.

Bridge failures become plain-English sentences for the voice channel —
never tracebacks.
"""

import logging
import os

import requests

logger = logging.getLogger("jarvis.nat")


class BridgeError(Exception):
    """Raised when the Nat bridge can't be reached or misbehaves."""


def bridge_url() -> str:
    return os.environ.get(
        "JARVIS_NAT_WEBHOOK", "http://localhost:5678/webhook/jarvis-tools"
    )


def call(op: str, params: dict | None = None, timeout: int = 30) -> dict:
    """POST one op to the bridge. Returns the decoded JSON body."""
    secret = os.environ.get("JARVIS_WEBHOOK_SECRET", "")
    try:
        resp = requests.post(
            bridge_url(),
            json={"op": op, "params": params or {}},
            headers={"X-Jarvis-Secret": secret},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("bridge unreachable for op=%s: %s", op, exc)
        raise BridgeError("the mail room is unreachable at the moment, ma'am")

    if resp.status_code in (401, 403):
        raise BridgeError("the mail room refused my credentials, ma'am")
    if resp.status_code != 200:
        raise BridgeError(
            f"the mail room stumbled (status {resp.status_code}), ma'am"
        )
    try:
        return resp.json()
    except ValueError:
        raise BridgeError("the mail room sent back gibberish, ma'am")
