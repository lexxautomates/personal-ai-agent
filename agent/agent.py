# LiveKit agents SDK voice runtime for the personal AI assistant.
#
# Shape: friday_jarvis minimal reference.
#   Agent + AgentSession + entrypoint + @function_tool tools + persona instructions.
#
# Substrate: lexxautomates/agents (fork of livekit/agents)
# Reference: ruxakK/friday_jarvis
# Patterns: drive-thru, frontdesk, healthcare, hotel_receptionist examples

import logging
from dataclasses import dataclass

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool, inference
from livekit.agents.llm import ToolError

logger = logging.getLogger("personal-ai-agent")


# ---------------------------------------------------------------------------
# Tools - start as stubs; replace with real implementations as the tool layer
# grows. The first real tools are calendar + email + reminders + notes for one
# user; Zapier MCP covers the long tail later.
# ---------------------------------------------------------------------------

@function_tool()
async def get_status(context: RunContext) -> str:
    """Return the current status of the personal assistant: whether it is running,
    how many sessions it has seen today, and whether the web layer is reachable."""
    return "Personal AI Agent is running. Status endpoints: /health, /status."


@function_tool()
async def remind(context: RunContext, note: str, at_iso: str) -> str:
    """Schedule a reminder for the user. at_iso is an ISO datetime the reminder
    should fire at. This is a stub; the real implementation writes to the
    background scheduler."""
    return f"Reminder noted for {at_iso}: {note}. (Stub - scheduler not wired yet.)"


@function_tool()
async def note(context: RunContext, text: str) -> str:
    """Jot a note for the user. This is a stub; the real implementation persists
    to the user's notes store."""
    return f"Noted: {text}. (Stub - notes store not wired yet.)"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

INSTRUCTIONS = """
You are a personal assistant for a solo entrepreneur and everyday person.
You help with scheduling, email, web lookups, reminders, contacts, notes, and
similar everyday errands.

A few rules:
- Be concise and useful.
- When you take an action, tell the user what you did in one short sentence.
- When you cannot do something, say so plainly and suggest the next best thing.
- Do not make up tools or capabilities you do not have.
- If a request is out of scope or risky, ask before acting.
"""


class PersonalAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=INSTRUCTIONS,
            tools=[get_status, remind, note],
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Welcome the user briefly and ask how you can help. Keep it to one "
                "or two sentences. You are the personal AI assistant."
            ),
        )


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession(
        stt=inference.STT("google/gemini-2.5-flash"),
        llm=inference.LLM("google/gemini-2.5-flash"),
        tts=inference.TTS("google/cloud-tts"),  # placeholder provider; swap in a real voice
    )
    await session.start(agent=PersonalAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
