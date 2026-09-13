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

Plan + first code scaffolding. No live server, no real tools yet.
