Personal AI Agent — everyday errands, voice-first

A Jarvis-inspired assistant that handles typical errands of a solo entrepreneur
and a regular person: scheduling, email, web lookups, reminders, contacts, notes,
messaging, calendar, lightweight home/device actions, and glue across the tools
one person actually uses.

## Substrate

- LiveKit server for the always-on media/signal layer.
- LiveKit agents SDK for the Python voice/realtime runtime.
- LiveKit Flutter starter for the companion mobile/desktop client.
- Flask web layer for HTTP admin, status, health, and integration hooks.
- Zapier MCP for the long tail of integrations.
- friday_jarvis as the minimal reference shape.
- drive-thru / frontdesk / healthcare / hotel_receptionist examples for mature
  tool patterns.

## Structure

- agent/ — the LiveKit agents SDK Python voice runtime.
- web/ — the Flask companion web API.
- client/ — the Flutter client, adapted from livekit_flutter_starter.

## Pi

Not part of the assistant runtime. Only relevant as the coding assistant used to
build and iterate on the agent code, the Flask layer, and the Flutter client.

## Status

Agent runtime is real. `agent/agent.py` runs PersonalAgent — "Jarvis,"
Alexandria's personal AI butler (dry British-butler wit, voice-first, calls
her "ma'am") — on a fully free self-hosted voice stack: faster-whisper STT,
Piper TTS, Silero VAD, Ollama LLM (see `agent/voice.py`).

Real tools (17): notes, reminders (with a background watcher that fires due
reminders into an outbox), Gmail search/read/draft/send and calendar
list/create via the Nat (n8n) webhook bridge, DuckDuckGo web search,
Open-Meteo weather. Sending mail and creating calendar events are
confirm-first — Jarvis asks aloud and only proceeds after Alexandria's spoken
yes (`confirm_action`). Reads and local writes run free; destructive or
out-of-scope actions are refused with a plain-English explanation
(`agent/policy.py`). Cross-session memory (profile, episodic log,
follow-ups) lives in sqlite (`agent/memory.py`).

Config is env-only — see `agent/.env.example`. Pinned deps in
`agent/requirements.txt` (Python 3.12). `tests/` holds 22 green pytest
tests. No live server run yet; push delivery of due reminders is still to
come.
