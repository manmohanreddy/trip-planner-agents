"""Interactive CLI for the trip planner agent."""

import asyncio
import os
import sys

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock, ToolUseBlock
from dotenv import load_dotenv

from .agent import build_options


def _tool_summary(block: ToolUseBlock) -> str:
    payload = block.input or {}
    return (
        payload.get("query")
        or payload.get("url")
        or payload.get("file_path")
        or payload.get("subagent_type")
        or ""
    )


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

    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break

            await client.query(user_input)
            print("\nAgent: ", end="", flush=True)

            subagent_names: dict[str, str] = {}

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    in_subagent = getattr(message, "parent_tool_use_id", None)
                    subagent = subagent_names.get(in_subagent, "subagent") if in_subagent else None

                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if subagent:
                                print(f"\n  [{subagent}] {block.text}", end="", flush=True)
                            else:
                                print(block.text, end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            if block.name in ("Agent", "Task"):
                                name = (block.input or {}).get("subagent_type", "subagent")
                                subagent_names[block.id] = name
                                print(f"\n  [delegating -> {name}]", flush=True)
                            elif subagent:
                                summary = _tool_summary(block)
                                suffix = f": {summary}" if summary else ""
                                print(f"\n    [{subagent}/{block.name}{suffix}]", flush=True)
                            else:
                                summary = _tool_summary(block)
                                suffix = f": {summary}" if summary else ""
                                print(f"\n  [{block.name}{suffix}]", flush=True)

            print("\n")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
