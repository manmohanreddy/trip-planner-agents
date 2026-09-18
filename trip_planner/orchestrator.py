"""Explicit orchestration of the three research specialists.

This is the piece that replaces SDK-level Agent-tool delegation: instead of
handing an orchestrator agent an `Agent` tool and trusting its prompt to fan
out and wait correctly, this module runs three independent `query()` calls
concurrently via asyncio.gather, collects their results itself, then runs a
fourth query() to synthesize the final itinerary. Parallelism and ordering
are guaranteed by the code here, not by model behavior.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import NamedTuple

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from .agent import attractions_options, flight_options, hotel_options, synthesis_options

ProgressFn = Callable[[str, str], None]


class Findings(NamedTuple):
    flights: str
    hotels: str
    attractions: str


async def _run_specialist(
    label: str,
    prompt: str,
    options: ClaudeAgentOptions,
    on_progress: ProgressFn | None,
) -> str:
    """Run one specialist query() to completion, return its final text."""
    result_text = ""
    async for message in query(prompt=prompt, options=options):
        if on_progress and isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    payload = block.input or {}
                    detail = payload.get("query") or payload.get("url") or ""
                    on_progress(label, f"{block.name}: {detail}" if detail else block.name)
                elif isinstance(block, TextBlock) and block.text.strip():
                    on_progress(label, "done researching, writing up findings")
        if isinstance(message, ResultMessage):
            result_text = message.result or ""
    return result_text


async def research(trip_brief: str, on_progress: ProgressFn | None = None) -> Findings:
    """Fan out to flight/hotel/attractions specialists in parallel."""
    flights, hotels, attractions = await asyncio.gather(
        _run_specialist("flights", trip_brief, flight_options(), on_progress),
        _run_specialist("hotels", trip_brief, hotel_options(), on_progress),
        _run_specialist("attractions", trip_brief, attractions_options(), on_progress),
    )
    return Findings(flights=flights, hotels=hotels, attractions=attractions)


async def synthesize(
    trip_brief: str,
    findings: Findings,
    on_progress: ProgressFn | None = None,
) -> str:
    """Combine specialist findings into the final itinerary and write it."""
    prompt = (
        f"Trip brief:\n{trip_brief}\n\n"
        f"Flight research:\n{findings.flights}\n\n"
        f"Hotel research:\n{findings.hotels}\n\n"
        f"Attractions research:\n{findings.attractions}\n\n"
        "Combine these into the final itinerary now."
    )
    return await _run_specialist("synthesis", prompt, synthesis_options(), on_progress)


async def plan_trip(trip_brief: str, on_progress: ProgressFn | None = None) -> str:
    """Full pipeline: parallel research, then synthesis. Returns the itinerary."""
    findings = await research(trip_brief, on_progress)
    return await synthesize(trip_brief, findings, on_progress)
