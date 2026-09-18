"""Agent configuration.

Explicit Python-level orchestration instead of the SDK's Agent-tool
delegation: each role below (intake, the three research specialists,
synthesis) is a plain ClaudeAgentOptions builder. orchestrator.py drives
them directly with asyncio.gather + query(), so fan-out/timing/parallelism
is controlled in code, not left to the model to decide via prompt.
"""

from claude_agent_sdk import ClaudeAgentOptions

from .prompts import (
    ATTRACTIONS_AGENT_PROMPT,
    FLIGHT_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    INTAKE_PROMPT,
    SYNTHESIS_PROMPT,
)

DEFAULT_MODEL = "sonnet"


def intake_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    """Conversational requirement-gathering only — no tools."""
    return ClaudeAgentOptions(
        system_prompt=INTAKE_PROMPT,
        model=model,
        allowed_tools=[],
        permission_mode="acceptEdits",
        setting_sources=[],
    )


def flight_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=FLIGHT_AGENT_PROMPT,
        model=model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
    )


def hotel_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=HOTEL_AGENT_PROMPT,
        model=model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
    )


def attractions_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=ATTRACTIONS_AGENT_PROMPT,
        model=model,
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
        setting_sources=[],
    )


def synthesis_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYNTHESIS_PROMPT,
        model=model,
        allowed_tools=["Write"],
        permission_mode="acceptEdits",
        setting_sources=[],
    )
