# Jarvis — Alexandria's personal AI butler.
#
# Shape: friday_jarvis minimal reference.
#   Agent + AgentSession + entrypoint + @function_tool tools + persona instructions.
# Runtime: LiveKit agents SDK voice process. Flask (web/) is the companion
# HTTP layer; this file is the voice runtime.

import logging
from datetime import datetime, timezone

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)

from . import db as dbmod
from . import memory
from . import scheduler
from . import tool_impls
from . import tools
from .voice import create_voice_stack

logger = logging.getLogger("jarvis")

INSTRUCTIONS = """
You are Jarvis, Alexandria's personal AI butler. Voice-first: keep replies short
and spoken, no markdown, no lists, no emojis. Personality: dry British-butler
wit, lightly sarcastic, always helpful. Address Alexandria as "ma'am". Never
invent tool results. If a tool fails, say so plainly and offer an alternative.
When you take an action, say what you did in one short sentence.

Tool rules you must follow:
- Reading (email search, calendar, notes, web, weather) is always fine.
- Sending email and creating calendar events are CONFIRM-FIRST: the tool will
  hand you a confirmation number and an ask-aloud sentence. Ask Alexandria
  aloud, and only call confirm_action with the confirmation number if she
  says yes.
- If a tool refuses or is unavailable, say so plainly in your own words and
  offer the next best thing. Never pretend you did something you didn't.
- CallCovered is Alexandria's white-labeled GoHighLevel SaaS for South Florida
  roofers. Never say "GoHighLevel" to a customer. Use kb_search for tiers,
  pricing, ROI, objections, A2P and compliance answers — quote the handbook,
  never improvise product facts. Use client_add / client_stage / client_list /
  client_get / client_note to run the onboarding pipeline: intake, a2p,
  subaccount, snapshot, forwarding, voice_config, test_call, live. A2P
  registration is a hard gate before any texting. When a client goes live,
  set day-1, day-3 and day-7 check-in reminders.
"""


class PersonalAgent(Agent):
    def __init__(self, startup_brief: str = "") -> None:
        instructions = INSTRUCTIONS
        if startup_brief.strip():
            instructions += "\nSession brief:\n" + startup_brief.strip()
        super().__init__(instructions=instructions, tools=tools.ALL_TOOLS)

    async def on_enter(self) -> None:
        due = tool_impls.check_due_reminders(dbmod.connect())
        if due:
            await self.session.generate_reply(instructions=(
                "Greet Alexandria briefly as her butler, then read her these "
                f"due reminders: {due}"
            ))
        else:
            await self.session.generate_reply(instructions=(
                "Greet Alexandria briefly as her butler — one short sentence — "
                "and ask how you may be of service."
            ))


async def entrypoint(ctx: JobContext) -> None:
    dbmod.init_db()
    scheduler.start_reminder_watcher()

    conn = dbmod.connect()
    brief = memory.startup_context(conn)
    conn.close()

    started_at = datetime.now(timezone.utc).isoformat()
    vad, stt, llm, tts = create_voice_stack()
    session = AgentSession(vad=vad, stt=stt, llm=llm, tts=tts)

    try:
        await session.start(agent=PersonalAgent(startup_brief=brief), room=ctx.room)
    finally:
        # Session over: append a short episodic entry for next time.
        try:
            conn = dbmod.connect()
            memory.log_episode(
                conn,
                "Voice session with Alexandria (summary not captured in this build).",
                started_at,
            )
            conn.close()
        except Exception:
            logger.exception("failed to log episodic entry")


if __name__ == "__main__":
    # Classic worker shape: connects to LiveKit over LIVEKIT_URL itself and
    # takes dispatched jobs. No agent_dispatch block needed in livekit.yaml.
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="jarvis"))
