# Trip Planner Agents

Trip planning agent built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python).

**v1 (this)**: a single agent with `WebSearch` / `WebFetch` / `Write` tools that
gathers trip requirements, researches flights/hotels/attractions, and writes a
full day-by-day itinerary to `output/`.

**Planned iteration**: split into an orchestrator + subagents (flight-search,
hotel-search, attractions, itinerary-writer) using `ClaudeAgentOptions.agents`,
so each concern can be tuned/tested independently. `agent.py` is kept separate
from `cli.py` for exactly this reason — the transport layer shouldn't need to
change when the agent topology does.

## Setup

```bash
cd trip-planner-agents
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy .env.example .env        # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
python -m trip_planner.cli
```

Chat with it: give origin, destination, dates, travelers, budget, interests.
It will ask for anything missing, research live, and save the itinerary to
`output/<destination>-itinerary.md`.

## Layout

```
trip_planner/
  agent.py    # ClaudeAgentOptions — model, tools, system prompt wiring
  prompts.py  # system prompt (the actual "trip planner" behavior spec)
  cli.py      # interactive terminal chat loop
output/       # generated itineraries land here (gitignored)
```
