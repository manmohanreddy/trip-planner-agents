"""Interactive CLI: chat-based intake, then explicit Python-orchestrated
research + synthesis (see orchestrator.py) — no SDK Agent-tool delegation.
"""

import asyncio
import os
import sys

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock
from dotenv import load_dotenv

from .agent import intake_options
from .orchestrator import plan_trip

READY_PREFIX = "READY:"


async def gather_requirements() -> str | None:
    """Chat with the user until intake emits a READY: brief. None = user quit."""
    async with ClaudeSDKClient(options=intake_options()) as client:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return None

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                return None

            await client.query(user_input)

            full_text = ""
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            full_text += block.text

            stripped = full_text.strip()
            if stripped.startswith(READY_PREFIX):
                return stripped[len(READY_PREFIX):].strip()

            print(f"\nAgent: {full_text}\n")


def _print_progress(label: str, detail: str) -> None:
    print(f"  [{label}] {detail}", flush=True)


async def run() -> None:
    # Windows console defaults to a legacy codepage (cp1252) that can't
    # encode characters like → or emoji the agent may emit. Force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Note: ANTHROPIC_API_KEY not set — relying on `claude` CLI's own "
            "login session. If that's not set up, copy .env.example to .env "
            "and fill in a key.\n",
            file=sys.stderr,
        )

    os.makedirs("output", exist_ok=True)

    print("Trip Planner Agent. Describe the trip you want. Type 'exit' to quit.\n")

    while True:
        brief = await gather_requirements()
        if brief is None:
            break

        print("\nAll set. Researching flights, hotels, and attractions in parallel...\n")
        itinerary = await plan_trip(brief, on_progress=_print_progress)
        print(f"\n{itinerary}\n")
        print("Ask about another trip, or type 'exit' to quit.\n")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
