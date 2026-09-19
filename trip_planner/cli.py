"""Interactive CLI: chat-based intake, then explicit Python-orchestrated
research + synthesis (see orchestrator.py) — no SDK Agent-tool delegation.
"""

import asyncio
import logging
import os
import sys

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock
from dotenv import load_dotenv
from pydantic import ValidationError

from .agent import intake_options
from .config import Settings
from .logging_config import configure_logging
from .models import TripBrief
from .orchestrator import plan_trip

logger = logging.getLogger(__name__)

READY_PREFIX = "READY:"


async def _send_and_receive(client: ClaudeSDKClient, text: str) -> str:
    await client.query(text)
    full_text = ""
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    full_text += block.text
    return full_text


def _extract_trip_brief(full_text: str) -> TripBrief | None:
    """None if this turn wasn't a READY: line. Raises pydantic.ValidationError
    if it was but the JSON payload doesn't parse/validate."""
    stripped = full_text.strip()
    if not stripped.startswith(READY_PREFIX):
        return None
    payload = stripped[len(READY_PREFIX) :].strip()
    return TripBrief.model_validate_json(payload)


async def gather_requirements(settings: Settings) -> TripBrief | None:
    """Chat with the user until intake emits a valid READY: brief. None = user quit."""
    async with ClaudeSDKClient(options=intake_options(settings)) as client:
        repair_attempts = 0
        pending_correction: str | None = None

        while True:
            if pending_correction is not None:
                full_text = await _send_and_receive(client, pending_correction)
                pending_correction = None
            else:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return None

                if not user_input:
                    continue
                if user_input.lower() in {"exit", "quit"}:
                    return None

                full_text = await _send_and_receive(client, user_input)

            try:
                brief = _extract_trip_brief(full_text)
            except ValidationError as exc:
                repair_attempts += 1
                logger.warning(
                    "intake emitted invalid READY: JSON (attempt %d/%d): %s",
                    repair_attempts,
                    settings.intake_max_repair_attempts,
                    exc,
                )
                if repair_attempts > settings.intake_max_repair_attempts:
                    print(
                        "\nHad trouble understanding your trip details as structured "
                        "data. Let's start over.\n"
                    )
                    return None
                pending_correction = (
                    f"Your last READY: line did not parse: {exc}. Re-emit a corrected "
                    "one-line READY: JSON now, nothing else."
                )
                continue

            if brief is not None:
                return brief

            print(f"\nAgent: {full_text}\n")

    # Unreachable: the while True loop above only exits via return. This is
    # here because ClaudeSDKClient.__aexit__ returns bool (can suppress an
    # exception), so mypy can't otherwise prove this point is never reached.
    raise AssertionError("unreachable")


def _print_progress(label: str, detail: str) -> None:
    print(f"  [{label}] {detail}", flush=True)


async def run() -> None:
    # Windows console defaults to a legacy codepage (cp1252) that can't
    # encode characters like → or emoji the agent may emit. Force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    load_dotenv()
    settings = Settings()
    configure_logging(settings.log_level)

    if settings.anthropic_api_key is None:
        logger.warning(
            "ANTHROPIC_API_KEY not set — relying on `claude` CLI's own login "
            "session. If that's not set up, copy .env.example to .env and "
            "fill in a key."
        )

    os.makedirs(settings.output_dir, exist_ok=True)

    print("Trip Planner Agent. Describe the trip you want. Type 'exit' to quit.\n")

    while True:
        brief = await gather_requirements(settings)
        if brief is None:
            break

        print("\nAll set. Researching flights, hotels, and attractions in parallel...\n")
        itinerary, metrics = await plan_trip(
            brief.to_prompt_text(), settings, on_progress=_print_progress
        )
        print(f"\n{itinerary}\n")
        print("\n".join(metrics.summary_lines()))
        print(f"\n(Full metrics appended to {settings.output_dir}/metrics.jsonl)")
        print("\nAsk about another trip, or type 'exit' to quit.\n")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
