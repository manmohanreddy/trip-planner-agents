import json

from trip_planner.metrics import RunMetrics, StageMetrics


def test_total_cost_usd_sums_and_treats_none_as_zero() -> None:
    metrics = RunMetrics(trip_brief="brief")
    metrics.add(StageMetrics(label="a", wall_seconds=1.0, cost_usd=0.1))
    metrics.add(StageMetrics(label="b", wall_seconds=1.0, cost_usd=None))
    metrics.add(StageMetrics(label="c", wall_seconds=1.0, cost_usd=0.2))

    assert metrics.total_cost_usd == 0.1 + 0.2


def test_summary_lines_flags_errors() -> None:
    metrics = RunMetrics(trip_brief="brief")
    metrics.add(StageMetrics(label="ok", wall_seconds=1.0, is_error=False))
    metrics.add(StageMetrics(label="bad", wall_seconds=1.0, is_error=True))

    lines = "\n".join(metrics.summary_lines())

    assert "ok" in lines
    assert "[ERROR]" in lines
    assert lines.count("[ERROR]") == 1  # only the failed stage is flagged


def test_write_log_appends_one_json_line_per_call(tmp_path) -> None:
    metrics = RunMetrics(trip_brief="a trip")
    metrics.add(StageMetrics(label="flights", wall_seconds=1.5, cost_usd=0.05))
    metrics.total_wall_seconds = 1.5

    metrics.write_log(tmp_path)
    metrics.write_log(tmp_path)

    log_path = tmp_path / "metrics.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    record = json.loads(lines[0])
    assert record["trip_brief"] == "a trip"
    assert record["total_wall_seconds"] == 1.5
    assert record["total_cost_usd"] == 0.05
    assert record["stages"][0]["label"] == "flights"
    assert {"ts", "trip_brief", "total_wall_seconds", "total_cost_usd", "stages"} <= record.keys()
