"""Agent configuration.

Explicit Python-level orchestration instead of the SDK's Agent-tool
delegation: each role below (intake, the three research specialists,
synthesis) is a plain ClaudeAgentOptions builder. orchestrator.py drives
them directly with asyncio.gather + query(), so fan-out/timing/parallelism
is controlled in code, not left to the model to decide via prompt.
"""

from claude_agent_sdk import ClaudeAgentOptions

from .config import Settings
from .prompts import (
    ATTRACTIONS_AGENT_PROMPT,
    FLIGHT_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    INTAKE_PROMPT,
    SYNTHESIS_PROMPT,
)


def intake_options(settings: Settings | None = None) -> ClaudeAgentOptions:
    """Conversational requirement-gathering only — no tools."""
    settings = settings or Settings()
    return ClaudeAgentOptions(
        system_prompt=INTAKE_PROMPT,
        model=settings.model,
        allowed_tools=[],
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=settings.stage_budget_usd,
    )


def flight_options(settings: Settings | None = None) -> ClaudeAgentOptions:
    settings = settings or Settings()
    return ClaudeAgentOptions(
        system_prompt=FLIGHT_AGENT_PROMPT,
        model=settings.model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=settings.stage_budget_usd,
    )


def hotel_options(settings: Settings | None = None) -> ClaudeAgentOptions:
    settings = settings or Settings()
    return ClaudeAgentOptions(
        system_prompt=HOTEL_AGENT_PROMPT,
        model=settings.model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=settings.stage_budget_usd,
    )


def attractions_options(settings: Settings | None = None) -> ClaudeAgentOptions:
    settings = settings or Settings()
    return ClaudeAgentOptions(
        system_prompt=ATTRACTIONS_AGENT_PROMPT,
        model=settings.model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=settings.stage_budget_usd,
    )


def synthesis_options(settings: Settings | None = None) -> ClaudeAgentOptions:
    settings = settings or Settings()
    return ClaudeAgentOptions(
        system_prompt=SYNTHESIS_PROMPT,
        model=settings.model,
        allowed_tools=["Write"],
        permission_mode="acceptEdits",
        setting_sources=[],
        max_budget_usd=settings.stage_budget_usd,
    )
