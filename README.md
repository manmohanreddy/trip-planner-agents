# Trip Planner Agents

Trip planning agent built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python).

**v2 (this)**: an orchestrator + three specialist subagents, wired via
`ClaudeAgentOptions.agents` and the SDK's built-in `Agent` tool:

```
                    You
                     │
              Orchestrator (gathers requirements,
              delegates, synthesizes, writes file)
                     │
        ┌────────────┼────────────┐
        ▼             ▼            ▼
  flight-search  hotel-search  attractions-search
  (WebSearch/     (WebSearch/    (WebSearch/
   WebFetch)       WebFetch)      WebFetch)
```

The orchestrator has no web tools of its own — it must delegate research to
the three subagents (run in parallel), then combines their findings into a
day-by-day itinerary and writes it to `output/`.

**v1** was a single agent doing everything directly — see git history. Each
subagent's behavior lives in its own prompt in `prompts.py` / `AgentDefinition`
in `agent.py`, so flight/hotel/attractions logic can be tuned independently
without touching the others. `agent.py` stays separate from `cli.py` so the
transport layer (interactive chat today, maybe an API later) doesn't need to
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
