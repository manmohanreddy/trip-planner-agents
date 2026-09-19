"""Explicit orchestration of the three research specialists.

This is the piece that replaces SDK-level Agent-tool delegation: instead of
handing an orchestrator agent an `Agent` tool and trusting its prompt to fan
out and wait correctly, this module runs three independent `query()` calls
concurrently via asyncio.gather, collects their results itself, then runs a
fourth query() to synthesize the final itinerary. Parallelism and ordering
are guaranteed by the code here, not by model behavior.

Resilience: _run_specialist() wraps each query() call with a timeout and
retries transient failures (rate limits, transient API errors) via tenacity.
It never raises past its own boundary -- an exhausted-retry or non-transient
failure is captured as a StageMetrics(is_error=True) plus a sentinel string
in place of the specialist's findings, so research()'s plain asyncio.gather
gives correct partial-failure behavior for free: if one specialist fails,
the other two still complete and synthesis proceeds with an explicit
"data unavailable" note instead of the whole run crashing.

Each stage's timing/cost is captured as StageMetrics (see metrics.py) and
rolled up into a RunMetrics for the whole pipeline.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import NamedTuple

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLINotFoundError,
    ProcessError,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from .agent import attractions_options, flight_options, hotel_options, synthesis_options
from .config import Settings
from .metrics import RunMetrics, StageMetrics

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, str], None]

_TRANSIENT_API_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}
_NON_TRANSIENT_SUBTYPES = {"error_max_turns", "error_max_budget_usd"}


class Findings(NamedTuple):
    flights: str
    hotels: str
    attractions: str


def _is_transient(exc: BaseException) -> bool:
    """Whether exc is worth retrying, based on the SDK's own error taxonomy."""
    if isinstance(exc, CLINotFoundError):
        return False  # environment problem, retrying won't fix it
    if isinstance(exc, ResultError):
        if exc.subtype in _NON_TRANSIENT_SUBTYPES:
            return False
        if exc.api_error_status in _TRANSIENT_API_STATUSES:
            return True
        return exc.terminal_reason == "api_error"
    if isinstance(exc, ProcessError):
        return True  # bare CLI crash / non-zero exit, plausibly transient
    return isinstance(exc, TimeoutError)


async def _run_specialist_once(
    label: str,
    prompt: str,
    options: ClaudeAgentOptions,
    on_progress: ProgressFn | None,
) -> tuple[str, StageMetrics]:
    """One attempt: run query() to completion, return its text + metrics."""
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
    return result_text, stage


async def _run_specialist(
    label: str,
    prompt: str,
    options: ClaudeAgentOptions,
    settings: Settings,
    on_progress: ProgressFn | None = None,
) -> tuple[str, StageMetrics]:
    """Resilient wrapper: retries transient failures, times out, never raises."""
    attempt_num = 0
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.retry_attempts),
            wait=wait_exponential(multiplier=settings.retry_backoff_base_seconds, min=1, max=30),
            retry=retry_if_exception(_is_transient),
            reraise=True,
        ):
            with attempt:
                attempt_num += 1
                if attempt_num > 1:
                    logger.warning(
                        "retrying %s (attempt %d/%d)", label, attempt_num, settings.retry_attempts
                    )
                    if on_progress:
                        on_progress(
                            label, f"retrying (attempt {attempt_num}/{settings.retry_attempts})..."
                        )
                result_text, stage = await asyncio.wait_for(
                    _run_specialist_once(label, prompt, options, on_progress),
                    timeout=settings.request_timeout_seconds,
                )
        if on_progress:
            on_progress(label, f"finished in {stage.wall_seconds:.1f}s")
        return result_text, stage
    except Exception as exc:
        logger.error("%s failed after %d attempt(s): %s", label, attempt_num, exc, exc_info=True)
        if on_progress:
            on_progress(label, f"failed: {type(exc).__name__}")
        failed_stage = StageMetrics(label=label, wall_seconds=0.0, is_error=True)
        sentinel = (
            f"[{label} research unavailable after {attempt_num} attempt(s): {type(exc).__name__}]"
        )
        return sentinel, failed_stage


async def research(
    trip_brief: str,
    settings: Settings,
    on_progress: ProgressFn | None = None,
) -> tuple[Findings, list[StageMetrics]]:
    """Fan out to flight/hotel/attractions specialists in parallel."""
    (flights, flights_m), (hotels, hotels_m), (attractions, attractions_m) = await asyncio.gather(
        _run_specialist("flights", trip_brief, flight_options(settings), settings, on_progress),
        _run_specialist("hotels", trip_brief, hotel_options(settings), settings, on_progress),
        _run_specialist(
            "attractions", trip_brief, attractions_options(settings), settings, on_progress
        ),
    )
    findings = Findings(flights=flights, hotels=hotels, attractions=attractions)
    return findings, [flights_m, hotels_m, attractions_m]


async def synthesize(
    trip_brief: str,
    findings: Findings,
    settings: Settings,
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
    return await _run_specialist(
        "synthesis", prompt, synthesis_options(settings), settings, on_progress
    )


async def plan_trip(
    trip_brief: str,
    settings: Settings,
    on_progress: ProgressFn | None = None,
) -> tuple[str, RunMetrics]:
    """Full pipeline: parallel research, then synthesis. Returns itinerary + metrics."""
    run_start = time.monotonic()
    metrics = RunMetrics(trip_brief=trip_brief)

    findings, research_stages = await research(trip_brief, settings, on_progress)
    for stage in research_stages:
        metrics.add(stage)

    if settings.run_budget_usd is not None and metrics.total_cost_usd >= settings.run_budget_usd:
        logger.warning(
            "run budget cap ($%.2f) reached after research (spent $%.4f) — skipping synthesis",
            settings.run_budget_usd,
            metrics.total_cost_usd,
        )
        itinerary = (
            f"Budget cap (${settings.run_budget_usd:.2f}) was reached during research "
            f"(spent ${metrics.total_cost_usd:.4f}) — synthesis was skipped.\n\n"
            f"Flight findings:\n{findings.flights}\n\n"
            f"Hotel findings:\n{findings.hotels}\n\n"
            f"Attractions findings:\n{findings.attractions}\n"
        )
        metrics.add(StageMetrics(label="synthesis", wall_seconds=0.0, is_error=True))
    else:
        itinerary, synthesis_stage = await synthesize(trip_brief, findings, settings, on_progress)
        metrics.add(synthesis_stage)

    metrics.total_wall_seconds = time.monotonic() - run_start
    metrics.write_log(settings.output_dir)

    return itinerary, metrics
