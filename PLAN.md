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

## Reference points

- livekit server + livekit agents SDK for the voice/realtime substrate.
- friday_jarvis as the minimal reference shape: Agent + AgentSession + a few
  @function_tool tools + persona instructions.
- drive-thru, frontdesk, healthcare, hotel_receptionist examples from livekit
  agents for mature tool patterns: dynamic tools, sub-tasks, auth gating,
  modality-aware instructions, evals.
- Zapier MCP as the shortcut for the long tail of integrations.

## Architecture (target)

- livekit server as the always-on media/signal layer (self-hosted or cloud).
- Python agent app on the livekit agents SDK as the runtime.
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

1. Stand up a minimal voice agent on the livekit agents SDK using the
   friday_jarvis shape: Agent, AgentSession, entrypoint, a couple of toy tools,
   persona instructions. Prove the voice loop works end to end.
2. Pick the first real tool surface for one persona's actual errands, not
   "everything." Example: calendar + email + reminders + notes for one user.
3. Add a Zapier MCP connector early so a big chunk of integrations is reachable
   without writing each one by hand.
4. Add cross-session memory: profile + episodic log + follow-up list.
5. Add the permission/policy layer: what can fire autonomously, what must confirm,
   what is off-limits unattended.
6. Add background scheduling for reminders and follow-ups.
7. Polish voice instructions and persona.
8. Add a few regression scenarios and keep them green as tools change.

## Repos in play

- lexxautomates/livekit — the server substrate. Fresh fork of livekit/livekit,
  zero local commits. Use upstream or this fork; today they are the same.
- lexxautomates/agents — the Python SDK substrate. Fresh fork of livekit/agents,
  zero local commits. Use upstream or this fork; today they are the same.
- lexxautomates/pi — not part of the assistant runtime. TypeScript CLI coding
  agent. Only relevant as the coding assistant that helps build the agent code.
- ruxakK/friday_jarvis — minimal reference implementation of exactly this shape.

## Open questions

- Which backends does this specific user actually want the assistant to touch day
  to day? That determines the real tool list.
- How much autonomy is wanted vs confirm-first? That determines the policy layer.
- Self-hosted livekit server on the iMac, or LiveKit Cloud to start?
- Which LLM/realtime model and STT/TTS providers for the first pass?

## Status

Plan. No code started yet.
