# Trip Planner Agents

[![CI](https://github.com/manmohanreddy/trip-planner-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/manmohanreddy/trip-planner-agents/actions/workflows/ci.yml)

Trip planning agent built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python).

**v4 (this)**: production-hardened — typed config, resilient orchestration
(retries/timeouts/budget caps, partial-failure handling), structured intake
validation, tests, Docker, CI. The pipeline shape is unchanged from v3:
explicit Python-level orchestration, four independent `query()` calls,
fanned out and sequenced by our own code (`orchestrator.py`), not by an LLM
deciding when to delegate:

```
                    You
                     │
            Intake (chat, no tools —
          gathers requirements, emits
          a "READY:" trip brief as JSON,
           validated against TripBrief)
                     │
                     │  orchestrator.py: asyncio.gather(...)
        ┌────────────┼────────────┐
        ▼             ▼            ▼
  flight-search  hotel-search  attractions-search
  (WebSearch/     (WebSearch/    (WebSearch/
   WebFetch,       WebFetch,      WebFetch,
   retry+timeout)  retry+timeout) retry+timeout)
        │             │            │
        └─────────────┼────────────┘
                       ▼
                  Synthesis
           (combines findings — including
          "[X unavailable]" notes for any
            failed leg — writes itinerary)
```

Each stage is a plain `ClaudeAgentOptions` builder in `agent.py` and a
`query()` call in `orchestrator.py`/`cli.py` — there's no `Agent` tool, no
`ClaudeAgentOptions.agents`, no model-driven delegation. Parallelism between
the three research specialists is `asyncio.gather`, guaranteed by code.

If one research specialist fails (rate limit, timeout, credit exhaustion),
`_run_specialist()` retries transient failures with backoff, then — if still
failing — returns a `"[X unavailable]"` sentinel instead of raising. The
other two specialists still complete, and synthesis proceeds with an
explicit note about the gap instead of the whole run crashing.

**Earlier iterations** (single agent doing everything directly, then an
orchestrator delegating via the SDK's `Agent` tool) are in git history.

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
own login session instead (not available inside Docker — see below).

## Run

```bash
python -m trip_planner.cli
```

Chat with it: give origin, destination, dates, travelers, budget, interests.
It will ask for anything missing, research live, and save the itinerary to
`output/<destination>-itinerary.md`.

## Configuration

All settings are read from the environment / `.env` (`trip_planner/config.py`).
`ANTHROPIC_API_KEY` keeps its own bare name (the SDK/CLI's convention); every
other setting is prefixed `TRIP_PLANNER_`.

| Env var | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | API key. If unset, falls back to `claude` CLI login (local runs only). |
| `TRIP_PLANNER_MODEL` | `sonnet` | Model alias used for every stage. |
| `TRIP_PLANNER_REQUEST_TIMEOUT_SECONDS` | `90.0` | Per-stage timeout before it's treated as failed. |
| `TRIP_PLANNER_RETRY_ATTEMPTS` | `3` | Retry attempts for transient failures per stage. |
| `TRIP_PLANNER_RETRY_BACKOFF_BASE_SECONDS` | `2.0` | Exponential backoff base between retries. |
| `TRIP_PLANNER_STAGE_BUDGET_USD` | unset | Per-stage cost cap (`ClaudeAgentOptions.max_budget_usd`). |
| `TRIP_PLANNER_RUN_BUDGET_USD` | unset | Whole-run cost cap — skips synthesis if research alone exceeds it. |
| `TRIP_PLANNER_LOG_LEVEL` | `INFO` | Diagnostic log level (retries, timeouts, failures — not the chat UI). |
| `TRIP_PLANNER_OUTPUT_DIR` | `output` | Where itineraries and `metrics.jsonl` are written. |
| `TRIP_PLANNER_INTAKE_MAX_REPAIR_ATTEMPTS` | `2` | Retries for the model to fix a malformed intake JSON line. |

## Development

```bash
pip install -e ".[dev]"
pytest -v
ruff check .
ruff format --check .
mypy trip_planner
```

## Docker

```bash
docker build -t trip-planner-agents .
docker run -it --rm \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v "$(pwd)/output:/app/output" \
  trip-planner-agents
```

`-it` is required — this is an interactive chat CLI, not a server.
`ANTHROPIC_API_KEY` is effectively required in Docker: there's no persisted
`claude` CLI login session inside an ephemeral container.

## Layout

```
trip_planner/
  config.py           # Settings (env-driven, typed, secret-redacted)
  models.py            # TripBrief — validated intake contract
  logging_config.py     # diagnostic logging setup
  agent.py               # ClaudeAgentOptions builders, one per stage/role
  prompts.py               # each stage's system prompt
  orchestrator.py            # fan-out + retry/timeout/budget + synthesis
  cli.py                      # interactive intake chat, then runs the pipeline
  metrics.py                   # per-stage timing/cost, output/metrics.jsonl
tests/                          # pytest, mocks trip_planner.orchestrator.query
output/                          # generated itineraries + metrics (gitignored)
Dockerfile, .dockerignore
.github/workflows/ci.yml          # lint + type-check + test + docker build
```
