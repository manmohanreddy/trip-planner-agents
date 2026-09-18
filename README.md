# Trip Planner Agents

Trip planning agent built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python).

**v3 (this)**: explicit Python-level orchestration — four independent
`query()` calls, fanned out and sequenced by our own code
(`orchestrator.py`), not by an LLM deciding when to delegate:

```
                    You
                     │
            Intake (chat, no tools —
          gathers requirements, emits
             a "READY:" trip brief)
                     │
                     │  orchestrator.py: asyncio.gather(...)
        ┌────────────┼────────────┐
        ▼             ▼            ▼
  flight-search  hotel-search  attractions-search
  (WebSearch/     (WebSearch/    (WebSearch/
   WebFetch)       WebFetch)      WebFetch)
        │             │            │
        └─────────────┼────────────┘
                       ▼
                  Synthesis
           (combines findings, writes
            output/<dest>-itinerary.md)
```

Each stage is a plain `ClaudeAgentOptions` builder in `agent.py` and a
`query()` call in `orchestrator.py`/`cli.py` — there's no `Agent` tool, no
`ClaudeAgentOptions.agents`, no model-driven delegation. Parallelism between
the three research specialists is `asyncio.gather`, guaranteed by code.

**Earlier iterations** (single agent doing everything directly, then an
orchestrator delegating via the SDK's `Agent` tool) are in git history. The
Agent-tool version worked, but delegation timing (parallel vs. sequential,
foreground vs. background) was steered by prompt instructions the model
could deviate from — this version makes those decisions in Python instead.

`agent.py` stays separate from `cli.py`/`orchestrator.py` so the transport
layer doesn't need to change when the agent topology does.

## Setup

```bash
cd trip-planner-agents
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy .env.example .env        # then fill in ANTHROPIC_API_KEY
```

If `ANTHROPIC_API_KEY` is left unset, it falls back to your `claude` CLI's
own login session instead.

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
  agent.py         # ClaudeAgentOptions builders, one per stage/role
  prompts.py        # each stage's system prompt
  orchestrator.py    # fan-out (asyncio.gather) + synthesis — the actual orchestration
  cli.py             # interactive intake chat, then runs the pipeline
output/              # generated itineraries land here (gitignored)
```
