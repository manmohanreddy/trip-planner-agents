"""Agent configuration.

Orchestrator + specialist research subagents (flight-search, hotel-search,
attractions-search). The orchestrator gathers trip requirements, delegates
research to the subagents in parallel via the SDK's Agent tool, then
synthesizes the results into a day-by-day itinerary and writes it to disk.

Kept separate from cli.py so the transport layer (interactive chat today,
maybe an API/web frontend later) doesn't need to change when the agent
topology does.
"""

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

from .prompts import (
    ATTRACTIONS_AGENT_PROMPT,
    FLIGHT_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    ORCHESTRATOR_PROMPT,
)

DEFAULT_MODEL = "sonnet"

RESEARCH_AGENTS = {
    "flight-search": AgentDefinition(
        description=(
            "Searches for flight options between two airports on given "
            "dates and budget. Use for any flight/airfare research."
        ),
        prompt=FLIGHT_AGENT_PROMPT,
        tools=["WebSearch", "WebFetch"],
        model="sonnet",
        # Orchestrator needs results before it can synthesize the
        # itinerary, so these must run synchronously, not as background
        # tasks (the SDK default when a caller doesn't say otherwise).
        background=False,
    ),
    "hotel-search": AgentDefinition(
        description=(
            "Searches for lodging options in a destination matched to "
            "budget and area. Use for any hotel/hostel research."
        ),
        prompt=HOTEL_AGENT_PROMPT,
        tools=["WebSearch", "WebFetch"],
        model="sonnet",
        background=False,
    ),
    "attractions-search": AgentDefinition(
        description=(
            "Researches attractions, activities, and points of interest "
            "at a destination matched to traveler interests and budget."
        ),
        prompt=ATTRACTIONS_AGENT_PROMPT,
        tools=["WebSearch", "WebFetch"],
        model="sonnet",
        background=False,
    ),
}


def build_options(model: str = DEFAULT_MODEL) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=ORCHESTRATOR_PROMPT,
        model=model,
        # NOTE: ClaudeAgentOptions.tools scopes the whole session (including
        # subagents), not just the orchestrator, so it's deliberately left
        # unset here — restricting it choked off the subagents' WebSearch/
        # WebFetch access too. Tool restriction happens per-agent instead,
        # via each AgentDefinition.tools above. allowed_tools just
        # pre-approves these so nothing hits an interactive permission
        # prompt that a non-interactive session can't answer.
        allowed_tools=["Agent", "Write", "WebSearch", "WebFetch"],
        agents=RESEARCH_AGENTS,
        permission_mode="acceptEdits",
        setting_sources=[],
    )
