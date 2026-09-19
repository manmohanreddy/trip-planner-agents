"""Orchestrator tests. Mock point: trip_planner.orchestrator.query -- that's
the name the module actually calls, patching claude_agent_sdk.query directly
would miss it since orchestrator imported its own reference at module load.

Fakes are keyed by each stage's system_prompt (a distinct constant per
role), since research() sends the *same* trip_brief text to all three
specialists -- only `options.system_prompt` tells them apart.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    ToolUseBlock,
)

from trip_planner import orchestrator
from trip_planner.agent import synthesis_options
from trip_planner.config import Settings
from trip_planner.orchestrator import Findings, plan_trip, research, synthesize
from trip_planner.prompts import (
    ATTRACTIONS_AGENT_PROMPT,
    FLIGHT_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    SYNTHESIS_PROMPT,
)


def _fast_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "retry_attempts": 2,
        "retry_backoff_base_seconds": 0.01,
        "request_timeout_seconds": 5.0,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[call-arg,arg-type]


def _result_message(text: str, cost: float = 0.01) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=10,
        is_error=False,
        num_turns=1,
        session_id="sess",
        total_cost_usd=cost,
        usage={"input_tokens": 1, "output_tokens": 1},
        result=text,
    )


def _label_for(options: ClaudeAgentOptions) -> str:
    system_prompt = options.system_prompt
    assert isinstance(system_prompt, str)
    return {
        FLIGHT_AGENT_PROMPT: "flights",
        HOTEL_AGENT_PROMPT: "hotels",
        ATTRACTIONS_AGENT_PROMPT: "attractions",
        SYNTHESIS_PROMPT: "synthesis",
    }[system_prompt]


def _install_fake_query(
    monkeypatch: pytest.MonkeyPatch,
    behaviors: dict[str, Callable[[], AsyncIterator[object]]],
    call_counts: dict[str, int] | None = None,
) -> None:
    async def fake_query(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[object]:
        label = _label_for(options)
        if call_counts is not None:
            call_counts[label] = call_counts.get(label, 0) + 1
        async for message in behaviors[label]():
            yield message

    monkeypatch.setattr(orchestrator, "query", fake_query)


def _success_stream(text: str) -> Callable[[], AsyncIterator[object]]:
    async def gen() -> AsyncIterator[object]:
        yield AssistantMessage(
            content=[ToolUseBlock(id="t1", name="WebSearch", input={"query": "x"})],
            model="sonnet",
        )
        yield _result_message(text)

    return gen


@pytest.mark.asyncio
async def test_research_fanout_runs_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_seconds = 0.2

    async def slow_success(label: str) -> AsyncIterator[object]:
        await asyncio.sleep(sleep_seconds)
        yield _result_message(f"{label} findings")

    _install_fake_query(
        monkeypatch,
        {
            "flights": lambda: slow_success("flights"),
            "hotels": lambda: slow_success("hotels"),
            "attractions": lambda: slow_success("attractions"),
        },
    )

    start = time.monotonic()
    findings, stages = await research("a trip brief", _fast_settings())
    elapsed = time.monotonic() - start

    assert findings == Findings(
        flights="flights findings", hotels="hotels findings", attractions="attractions findings"
    )
    assert all(not s.is_error for s in stages)
    # If these ran sequentially this would take ~3x sleep_seconds.
    assert elapsed < sleep_seconds * 2


@pytest.mark.asyncio
async def test_partial_failure_research_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    async def always_fails() -> AsyncIterator[object]:
        raise ResultError("boom", data={"subtype": "error_max_turns"})
        yield  # pragma: no cover -- makes this an async generator

    _install_fake_query(
        monkeypatch,
        {
            "flights": _success_stream("flights ok"),
            "hotels": always_fails,
            "attractions": _success_stream("attractions ok"),
        },
    )

    findings, stages = await research("brief", _fast_settings())

    by_label = {s.label: s for s in stages}
    assert not by_label["flights"].is_error
    assert not by_label["attractions"].is_error
    assert by_label["hotels"].is_error
    assert "unavailable" in findings.hotels
    assert findings.flights == "flights ok"


@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"flights": 0}

    async def flaky() -> AsyncIterator[object]:
        attempts["flights"] += 1
        if attempts["flights"] == 1:
            raise ResultError("overloaded", data={"api_error_status": 529})
            yield  # pragma: no cover
        yield _result_message("ok after retry")

    _install_fake_query(
        monkeypatch,
        {
            "flights": flaky,
            "hotels": _success_stream("hotels ok"),
            "attractions": _success_stream("attractions ok"),
        },
    )

    findings, stages = await research("brief", _fast_settings())

    flights_stage = next(s for s in stages if s.label == "flights")
    assert not flights_stage.is_error
    assert findings.flights == "ok after retry"
    assert attempts["flights"] == 2


@pytest.mark.asyncio
async def test_non_transient_failure_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    call_counts: dict[str, int] = {}

    async def budget_exceeded() -> AsyncIterator[object]:
        raise ResultError("over budget", data={"subtype": "error_max_budget_usd"})
        yield  # pragma: no cover

    _install_fake_query(
        monkeypatch,
        {
            "flights": budget_exceeded,
            "hotels": _success_stream("hotels ok"),
            "attractions": _success_stream("attractions ok"),
        },
        call_counts,
    )

    await research("brief", _fast_settings())

    assert call_counts["flights"] == 1  # no retry spent on a non-transient failure


@pytest.mark.asyncio
async def test_stage_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def hangs() -> AsyncIterator[object]:
        await asyncio.sleep(10)
        yield _result_message("too late")  # pragma: no cover

    _install_fake_query(
        monkeypatch,
        {
            "flights": hangs,
            "hotels": _success_stream("hotels ok"),
            "attractions": _success_stream("attractions ok"),
        },
    )

    settings = _fast_settings(retry_attempts=1, request_timeout_seconds=0.05)
    start = time.monotonic()
    findings, stages = await research("brief", settings)
    elapsed = time.monotonic() - start

    flights_stage = next(s for s in stages if s.label == "flights")
    assert flights_stage.is_error
    assert "unavailable" in findings.flights
    assert elapsed < 5  # bounds proof that wait_for actually fired, not the 10s sleep


@pytest.mark.asyncio
async def test_synthesize_prompt_includes_unavailable_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_query(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[object]:
        captured["prompt"] = prompt
        yield _result_message("final itinerary")

    monkeypatch.setattr(orchestrator, "query", fake_query)

    findings = Findings(
        flights="[flights research unavailable after 2 attempt(s): ResultError]",
        hotels="hotels ok",
        attractions="attractions ok",
    )

    await synthesize("brief", findings, _fast_settings())

    assert "unavailable" in captured["prompt"]


@pytest.mark.asyncio
async def test_plan_trip_skips_synthesis_over_run_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    call_counts: dict[str, int] = {}

    _install_fake_query(
        monkeypatch,
        {
            "flights": _success_stream_with_cost("flights ok", 0.5),
            "hotels": _success_stream_with_cost("hotels ok", 0.5),
            "attractions": _success_stream_with_cost("attractions ok", 0.5),
            "synthesis": _success_stream("should not run"),
        },
        call_counts,
    )

    settings = _fast_settings(run_budget_usd=1.0)  # research alone spends 1.5
    itinerary, metrics = await plan_trip("brief", settings)

    assert "synthesis" not in call_counts
    assert "budget cap" in itinerary.lower()
    synthesis_stage = next(s for s in metrics.stages if s.label == "synthesis")
    assert synthesis_stage.is_error


def _success_stream_with_cost(text: str, cost: float) -> Callable[[], AsyncIterator[object]]:
    async def gen() -> AsyncIterator[object]:
        yield _result_message(text, cost=cost)

    return gen


def test_synthesis_options_uses_write_tool_only() -> None:
    options = synthesis_options(_fast_settings())
    assert options.allowed_tools == ["Write"]
