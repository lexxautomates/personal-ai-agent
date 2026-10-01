# Personal AI Agent — Jarvis-Inspired Everyday Assistant

## Purpose

A voice-first personal assistant that handles the everyday errands of a solo
entrepreneur and a regular person: scheduling, email, web lookups, reminders,
contacts, notes, messaging, calendar, lightweight home/device actions, and glue
across the tools one person actually uses. Voice interface modeled on Jarvis; the
"does everything" part is the tool layer, not the voice layer.

## Non-goal

Not a sentient agent, not a research assistant, not a coding agent. It is a
personal operator that acts on the user's behalf through real tools, with a
permission layer so it can be useful without being dangerous.

## Substrate

- LiveKit server for the always-on media/signal layer.
- LiveKit agents SDK for the Python voice/realtime runtime.
- LiveKit Flutter starter for the companion mobile/desktop client the user talks
  to when not on a phone call.
- Zapier MCP for the long tail of integrations.
- friday_jarvis as the minimal reference shape for the voice agent.
- drive-thru / frontdesk / healthcare / hotel_receptionist examples from the
  LiveKit agents repo for mature tool patterns.

## Where Flutter fits

Flutter is the client the person actually uses when they are not on a phone call:
a small app that dials into the same LiveKit agent, shows a voice UI, and can
also be a text channel for the same assistant. The lexxautomates/livekit_flutter_starter
fork is the starting point for that client. The assistant backend is the same
Python agent either way; Flutter is one interaction surface among others, not a
separate assistant.

The Flutter client is adapted from livekit_flutter_starter: same architecture —
`VoiceAssistantApp` → `AppCtrl` (session + room + token sourcing) → `WelcomeScreen`
(start call) → `AgentScreen` (voice + transcription chat, camera toggle, agent
track view, audio visualizer). The only change for our personal agent is re-pointing
the token source from the LiveKit Cloud homepage endpoint to our own LiveKit server.

## Where Flask fits

Flask is the web layer around the assistant: a small HTTP surface for things the
voice channel is not good for — dashboards, manual trigger endpoints, health
checks, status, config, the permission/policy UI, and integration hooks that
Zapier or other services hit. It is not the agent runtime; the agent runtime is
the LiveKit agents SDK Python process. Flask is the companion web API and admin
surface.

## Pi

Not part of the assistant runtime. Only relevant as the coding assistant used to
build and iterate on the agent code, the Flask layer, and the Flutter client.

## Architecture (target)

- LiveKit server as the always-on media/signal layer, self-hosted on the iMac if
  it can be reached, otherwise LiveKit Cloud to start.
- Python agent app on the LiveKit agents SDK as the runtime (`agent/`).
- Flask web layer (`web/`) alongside the agent for HTTP endpoints, admin, status,
  health, and integration hooks.
- Flutter client (`client/`) adapted from livekit_flutter_starter, pointed at the
  same LiveKit server and agent.
- Tool layer:
  - small set of custom tools for things Zapier cannot reach (local notes/files,
    memory, permission gate, follow-up scheduler, voice-specific actions),
  - Zapier MCP connector for the long tail: calendar, email, sheets, CRM, forms,
    messaging glue, notifications,
  - a few high-frequency native tools where tighter control, latency, or offline
    fallback matters.
- Cross-session memory: lightweight profile + episodic log + follow-up list,
  read on connect, written back on disconnect.
- Permission/policy layer: read broadly, write/execute under policy; confirm for
  expensive or public-facing actions; hand off to the human when out of scope.
- Background scheduler for reminders and follow-ups, separate from the voice
  session.
- Eval layer: a few scenario-driven regression tests for the behaviors that
  matter.

## Build order

1. Stand up a minimal voice agent on the LiveKit agents SDK using the
   friday_jarvis shape: Agent, AgentSession, entrypoint, a couple of toy tools,
   persona instructions. Prove the voice loop works end to end.
2. Add the Flask web layer with a health endpoint, status endpoint, and config
   surface. This gives the assistant an HTTP face before any dashboard.
3. Add the Flutter client from the livekit_flutter_starter shape so the same
   agent is reachable from a phone/laptop app, not only from a call. Repoint the
   token source from the LiveKit Cloud homepage endpoint to our own server.
4. Pick the first real tool surface for one persona's actual errands, not
   "everything." Example: calendar + email + reminders + notes for one user.
5. Add a Zapier MCP connector early so a big chunk of integrations is reachable
   without writing each one by hand.
6. Add cross-session memory: profile + episodic log + follow-up list.
7. Add the permission/policy layer: what can fire autonomously, what must confirm,
   what is off-limits unattended.
8. Add background scheduling for reminders and follow-ups.
9. Polish voice instructions and persona.
10. Add a few regression scenarios and keep them green as tools change.

## Repos in play

- lexxautomates/livekit — the server substrate. Fresh fork of livekit/livekit,
  zero local commits. Use upstream or this fork; today they are the same.
- lexxautomates/agents — the Python SDK substrate. Fresh fork of livekit/agents,
  zero local commits. Use upstream or this fork; today they are the same.
- lexxautomates/livekit_flutter_starter — the Flutter client substrate. Fresh
  fork of livekit/livekit-flutter-starter, zero local commits. Same note as the
  others: today it is upstream.
- lexxautomates/pi — not part of the assistant runtime. TypeScript CLI coding
  agent. Only relevant as the coding assistant that helps build the agent code.
- ruxakK/friday_jarvis — minimal reference implementation of exactly this shape.

## Hermes state

The Hermes working state that belongs to this project should live in its own repo,
separate from the agent code, so the agent repo stays clean and the Hermes state
can be snapshotted and shipped to the iMac without dragging the agent source along.
That repo is lexxautomates/hermes-state. It is private and currently empty; this
project's Hermes state goes there.

## Blockers

- iMac SSH is not reachable from this machine. Tailscale shows alexandrias-imac-1
  as active on macOS, but SSH to the tailnet address is blocked with "Permission
  denied" even with the known hermes_mac_ed25519 key. Until that is fixed, the
  iMac cannot be the always-on LiveKit host, and Hermes state cannot be pushed to
  it directly. Two options: fix iMac SSH access from here, or push Hermes state to
  the private hermes-state repo and pull it down on the iMac from there.
- The first pass will likely start on LiveKit Cloud for the server until the iMac
  path is proven.

## Open questions

- Which backends does this specific user actually want the assistant to touch day
  to day? That determines the real tool list.
- How much autonomy is wanted vs confirm-first? That determines the policy layer.
- Which LLM/realtime model and STT/TTS providers for the first pass?
- Self-hosted LiveKit server on the iMac, or LiveKit Cloud to start?

## Status

Agent runtime is REAL (built 2026-10-01, working tree — not yet committed):

- `agent/agent.py` — PersonalAgent with the Jarvis persona (dry British-butler
  wit, voice-first, addresses Alexandria as "ma'am"), entrypoint with
  AgentSession(vad, stt, llm, tts), AgentServer + `@server.rtc_session()`.
  Session start reads memory brief + announces due reminders; session end
  appends an episodic log entry.
- `agent/voice.py` — free self-hosted stack: WhisperSTT (faster-whisper
  base.en, CPU int8) on the livekit STT interface, PiperTTS
  (en_US-lessac-medium, downloaded on first run) on the livekit TTS
  interface, Silero VAD, Ollama LLM (qwen2.5:7b-instruct, OLLAMA_URL).
- `agent/tool_impls.py` + `agent/tools.py` — 17 real @function_tool tools:
  notes jot/list/search, reminders add/list/cancel + due-reminder check,
  gmail_search/read/draft, gmail_send (confirm-first), calendar_list,
  calendar_create (confirm-first), confirm_action, web_search (DuckDuckGo),
  weather (Open-Meteo), get_status. Gmail/Calendar go through the Nat (n8n)
  bridge: POST http://localhost:5678/webhook/jarvis-tools
  {"op","params"} + X-Jarvis-Secret; bridge failures are plain-English
  voice sentences, never tracebacks.
- `agent/policy.py` — permission layer: reads + local writes auto-allow,
  gmail_send/calendar_create confirm-first (recorded in
  pending_confirmations, executed via confirm_action), destructive/out-of-scope
  refused with plain-English handoff. Every external write calls
  policy.check() first.
- `agent/memory.py` — cross-session sqlite memory: profile, episodic log,
  follow_ups; brief injected at session start.
- `agent/scheduler.py` — daemon thread every 60s moves due reminders into
  due_outbox (announced at next session start; push delivery wiring later).
- `agent/schema.sql` — extended: due_outbox, pending_confirmations, profile,
  episodic, follow_ups (original notes/reminders tables untouched).
- `agent/requirements.txt` — pinned, pip dry-run resolves on Python 3.12.
- `agent/.env.example` — all config via env, no secrets in code.
- `tests/` — 22 pytest tests green: policy allow/confirm/refuse,
  notes/reminders sqlite round-trip, Nat bridge with fake HTTP server
  (op/params/secret header, graceful failures), web/weather parsers on
  fixture JSON.

Not yet: live server run, Flutter client repointing, Zapier MCP, push
delivery of due reminders, session-summary capture for the episodic log.

Earlier status (kept for history): plan + first code scaffolding. Minimal
voice agent scaffolding in agent/, Flask web layer scaffolding in web/,
Flutter client adapted from livekit_flutter_starter in client/. No live
server, no tools beyond stubs, no Zapier MCP yet.
