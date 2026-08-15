"""Aria — Omni Hotels & Resorts virtual guest services voice agent.

LiveKit Agents 1.x (Python) entrypoint. Single-agent architecture:
- STT: Deepgram nova-3
- LLM: OpenAI-compatible endpoint (default: GLM 4.5/5.2 Fast via Baseten)
- TTS: ElevenLabs
- VAD: Silero
- Tools: get_weather, get_local_events (Ticketmaster + Open-Meteo)

Local dev (hot-reload):
    lk cloud auth
    lk agent dev

Deploy:
    lk agent create --secrets-file .env.local
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    cli,
    metrics,
)
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import deepgram, elevenlabs, openai, silero

from prompt import ARIA_INSTRUCTIONS, FIRST_MESSAGE, load_kb
from tools import (
    get_local_events,
    get_weather,
    log_booking_capture,
    log_caller_intent,
    log_cancellation_capture,
    log_escalation_capture,
    log_reschedule_capture,
    verify_date,
)


def _build_calendar_reference(now: datetime, days_ahead: int = 90) -> str:
    """Pre-compute day-of-week for the next N days so the LLM doesn't have
    to do calendar arithmetic (which it does unreliably).
    """
    lines = [
        "# CALENDAR REFERENCE (authoritative — use this to verify any date)",
        f"Today is {now.strftime('%A, %B %-d, %Y')}.",
        "",
        "Upcoming dates (day of week is what actually falls on that date):",
    ]
    for i in range(days_ahead + 1):
        d = now + timedelta(days=i)
        lines.append(f"- {d.strftime('%Y-%m-%d')} = {d.strftime('%A, %B %-d')}")
    lines.append("")
    lines.append(
        "When the caller mentions a date with a day-of-week ('Sunday August 24'), "
        "look it up in this table. If they got the day-of-week wrong, silently "
        "note the correct one and ask them which they meant. If it matches, "
        "proceed silently — do NOT announce 'let me verify' or 'the date checks out'. "
        "Only speak up if there's a mismatch."
    )
    return "\n".join(lines)

# Load env from .env.local (dev) then .env (fallback). Deployed agents get
# secrets injected from LiveKit Cloud's encrypted store instead.
load_dotenv(".env.local")
load_dotenv(".env")

logger = logging.getLogger("omni-aria")
logging.basicConfig(level=logging.INFO)


class AriaAgent(Agent):
    """Aria — Omni's virtual guest services assistant."""

    def __init__(self) -> None:
        # Inline the KB, stamp the current date/time, and pre-compute a
        # 90-day calendar so date validation is reliable (LLMs don't do
        # calendar arithmetic well).
        kb = load_kb()
        now = datetime.now(timezone.utc).astimezone()
        current_time_str = now.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
        calendar_ref = _build_calendar_reference(now, days_ahead=90)

        instructions = ARIA_INSTRUCTIONS.replace("{{KNOWLEDGE_BASE}}", kb)
        instructions = (
            f"# CURRENT DATE AND TIME\n"
            f"The current date and time is **{current_time_str}**.\n\n"
            f"{calendar_ref}\n\n" + instructions
        )

        super().__init__(
            instructions=instructions,
            tools=[
                # Official LiveKit end_call — waits for the farewell speech
                # to finish, deletes the room (disconnecting all participants),
                # then shuts the job process down cleanly.
                # `ignore_on_enter=True` prevents end_call firing during the greeting.
                # `end_instructions=None` prevents the LLM from adding an extra
                # "Goodbye!" turn AFTER we already spoke the farewell.
                EndCallTool(
                    delete_room=True,
                    ignore_on_enter=True,
                    end_instructions=None,
                ),
                log_caller_intent,
                log_booking_capture,
                log_cancellation_capture,
                log_reschedule_capture,
                log_escalation_capture,
                verify_date,
                get_weather,
                get_local_events,
            ],
        )


# LiveKit CLI (`lk agent dev` / `lk agent create`) auto-discovers this
# module-level `server` object.
server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Called for every caller session."""
    logger.info("Aria session starting — room=%s", ctx.room.name)

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-3",
            language="en",
            api_key=os.environ.get("DEEPGRAM_API_KEY"),
        ),
        llm=openai.LLM(
            model=os.environ.get("LLM_MODEL", "zai-org/GLM-5.2-Fast"),
            base_url=os.environ.get("LLM_BASE_URL", "https://inference.baseten.co/v1"),
            api_key=os.environ.get("LLM_API_KEY"),
            temperature=0.4,
        ),
        tts=elevenlabs.TTS(
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
            model="eleven_turbo_v2_5",
            api_key=os.environ.get("ELEVENLABS_API_KEY"),
        ),
    )

    # Log per-turn metrics for slide 3 evidence collection.
    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage.collect(ev.metrics)

    async def _log_usage_on_shutdown() -> None:
        logger.info("Session summary: %s", usage.get_summary())

    ctx.add_shutdown_callback(_log_usage_on_shutdown)

    await session.start(agent=AriaAgent(), room=ctx.room)

    # Fixed greeting so we always disclose AI up front.
    await session.say(FIRST_MESSAGE, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(server)
