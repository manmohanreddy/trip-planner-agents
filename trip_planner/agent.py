"""Agent configuration.

Single agent for v1. Kept isolated from CLI/transport concerns so this can
later be swapped for an orchestrator that fans out to flight/hotel/attraction
subagents (see ClaudeAgentOptions.agents in the SDK) without touching cli.py.
"""

from claude_agent_sdk import ClaudeAgentOptions

from .prompts import SYSTEM_PROMPT

DEFAULT_MODEL = "sonnet"


def build_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=model,
        allowed_tools=["WebSearch", "WebFetch", "Write"],
        permission_mode="acceptEdits",
        setting_sources=[],
    )
