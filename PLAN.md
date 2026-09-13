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
- drive-thru / frontdesk / healthcare / hotel_receptionist examples for mature
  tool patterns.

## Where Flutter fits

Flutter is the client the person actually uses when they are not on a phone call:
a small app that dials into the same LiveKit agent, shows a voice UI, and can
also be a text channel for the same assistant. The lexxautomates/livekit_flutter_starter
fork is the starting point for that client. The assistant backend is the same
Python agent either way; Flutter is one interaction surface among others, not a
separate assistant.

Pi is not part of the assistant runtime. It is only relevant as the coding
assistant used to build and iterate on the agent code and the Flutter client.

## Architecture (target)

- LiveKit server as the always-on media/signal layer, self-hosted on the iMac if
  it can be reached, otherwise LiveKit Cloud to start.
- Python agent app on the LiveKit agents SDK as the runtime.
- Flutter client from the livekit_flutter_starter shape that connects to the same
  agent for voice and text on the user's phone/laptop.
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
2. Add the Flutter client from the livekit_flutter_starter shape so the same
   agent is reachable from a phone/laptop app, not only from a call.
3. Pick the first real tool surface for one persona's actual errands, not
   "everything." Example: calendar + email + reminders + notes for one user.
4. Add a Zapier MCP connector early so a big chunk of integrations is reachable
   without writing each one by hand.
5. Add cross-session memory: profile + episodic log + follow-up list.
6. Add the permission/policy layer: what can fire autonomously, what must confirm,
   what is off-limits unattended.
7. Add background scheduling for reminders and follow-ups.
8. Polish voice instructions and persona.
9. Add a few regression scenarios and keep them green as tools change.

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

## Open questions

- Which backends does this specific user actually want the assistant to touch day
  to day? That determines the real tool list.
- How much autonomy is wanted vs confirm-first? That determines the policy layer.
- Self-hosted LiveKit server on the iMac, or LiveKit Cloud to start?
- iMac SSH is not reachable from this machine yet; Tailscale says the iMac is
  active but SSH is blocked or missing a usable key. That needs to be fixed before
  the iMac can be the always-on host or the Hermes-state destination.
- Which LLM/realtime model and STT/TTS providers for the first pass?

## Status

Plan. No code started.
