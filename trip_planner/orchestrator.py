"""Explicit orchestration of the three research specialists.

This is the piece that replaces SDK-level Agent-tool delegation: instead of
handing an orchestrator agent an `Agent` tool and trusting its prompt to fan
out and wait correctly, this module runs three independent `query()` calls
concurrently via asyncio.gather, collects their results itself, then runs a
fourth query() to synthesize the final itinerary. Parallelism and ordering
are guaranteed by the code here, not by model behavior.

Each stage's timing/cost is captured as StageMetrics (see metrics.py) and
rolled up into a RunMetrics for the whole pipeline.
"""

import asyncio
import time
from collections.abc import Callable
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
from .metrics import RunMetrics, StageMetrics

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
) -> tuple[str, StageMetrics]:
    """Run one specialist query() to completion, return its text + metrics."""
    result_text = ""
    result_message: ResultMessage | None = None
    start = time.monotonic()

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
            result_message = message
            result_text = message.result or ""

    wall_seconds = time.monotonic() - start
    usage = (result_message.usage if result_message else None) or {}
    stage = StageMetrics(
        label=label,
        wall_seconds=wall_seconds,
        sdk_duration_ms=result_message.duration_ms if result_message else None,
        sdk_api_duration_ms=result_message.duration_api_ms if result_message else None,
        num_turns=result_message.num_turns if result_message else None,
        cost_usd=result_message.total_cost_usd if result_message else None,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        is_error=result_message.is_error if result_message else True,
    )

    if on_progress:
        on_progress(label, f"finished in {wall_seconds:.1f}s")

    return result_text, stage


async def research(
    trip_brief: str, on_progress: ProgressFn | None = None
) -> tuple[Findings, list[StageMetrics]]:
    """Fan out to flight/hotel/attractions specialists in parallel."""
    (flights, flights_m), (hotels, hotels_m), (attractions, attractions_m) = await asyncio.gather(
        _run_specialist("flights", trip_brief, flight_options(), on_progress),
        _run_specialist("hotels", trip_brief, hotel_options(), on_progress),
        _run_specialist("attractions", trip_brief, attractions_options(), on_progress),
    )
    findings = Findings(flights=flights, hotels=hotels, attractions=attractions)
    return findings, [flights_m, hotels_m, attractions_m]


async def synthesize(
    trip_brief: str,
    findings: Findings,
    on_progress: ProgressFn | None = None,
) -> tuple[str, StageMetrics]:
    """Combine specialist findings into the final itinerary and write it."""
    prompt = (
        f"Trip brief:\n{trip_brief}\n\n"
        f"Flight research:\n{findings.flights}\n\n"
        f"Hotel research:\n{findings.hotels}\n\n"
        f"Attractions research:\n{findings.attractions}\n\n"
        "Combine these into the final itinerary now."
    )
    return await _run_specialist("synthesis", prompt, synthesis_options(), on_progress)


async def plan_trip(
    trip_brief: str, on_progress: ProgressFn | None = None
) -> tuple[str, RunMetrics]:
    """Full pipeline: parallel research, then synthesis. Returns itinerary + metrics."""
    run_start = time.monotonic()
    metrics = RunMetrics(trip_brief=trip_brief)

    findings, research_stages = await research(trip_brief, on_progress)
    for stage in research_stages:
        metrics.add(stage)

    itinerary, synthesis_stage = await synthesize(trip_brief, findings, on_progress)
    metrics.add(synthesis_stage)

    metrics.total_wall_seconds = time.monotonic() - run_start
    metrics.write_log()

    return itinerary, metrics
