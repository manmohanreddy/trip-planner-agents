"""Timing/cost metrics for each pipeline stage.

Wraps the Claude Agent SDK's own ResultMessage fields (duration_ms,
total_cost_usd, usage tokens) plus a wall-clock timer around each stage.
Wall time and SDK duration_ms usually differ slightly: wall time includes
our own dispatch/await overhead, duration_ms is the SDK's own accounting of
time spent in the agent loop.

Every run appends one JSON line to output/metrics.jsonl, so performance
(and cost) can be tracked across runs over time, not just printed once and
lost.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

METRICS_LOG = Path("output/metrics.jsonl")


@dataclass
class StageMetrics:
    label: str
    wall_seconds: float
    sdk_duration_ms: int | None = None
    sdk_api_duration_ms: int | None = None
    num_turns: int | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    is_error: bool = False


@dataclass
class RunMetrics:
    trip_brief: str
    stages: list[StageMetrics] = field(default_factory=list)
    total_wall_seconds: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd or 0.0 for s in self.stages)

    def add(self, stage: StageMetrics) -> None:
        self.stages.append(stage)

    def summary_lines(self) -> list[str]:
        lines = ["Run metrics:"]
        for s in self.stages:
            cost = f"${s.cost_usd:.4f}" if s.cost_usd is not None else "n/a"
            flag = " [ERROR]" if s.is_error else ""
            lines.append(
                f"  {s.label:<12} {s.wall_seconds:6.2f}s wall  "
                f"{(s.sdk_duration_ms or 0) / 1000:6.2f}s sdk  "
                f"{s.num_turns or 0:2d} turns  {cost}{flag}"
            )
        lines.append(
            f"  {'TOTAL':<12} {self.total_wall_seconds:6.2f}s wall  "
            f"${self.total_cost_usd:.4f}"
        )
        return lines

    def write_log(self) -> None:
        METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.time(),
            "trip_brief": self.trip_brief,
            "total_wall_seconds": round(self.total_wall_seconds, 3),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "stages": [asdict(s) for s in self.stages],
        }
        with METRICS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
