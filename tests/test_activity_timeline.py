"""Tests for the 24-hour activity timeline composer."""
from datetime import UTC, datetime, timedelta

from lib.activity_timeline import compose_timeline


def _run(agent: str, hours_ago: float, status: str = "success",
         duration_ms: int | None = 5000, cost: float = 0.0) -> dict:
    return {
        "ts": datetime(2026, 5, 18, 12, 0, tzinfo=UTC) - timedelta(hours=hours_ago),
        "agent": agent,
        "status": status,
        "duration_ms": duration_ms,
        "cost_usd": cost,
        "notes": "",
    }


_NOW = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)


def test_empty_runs_produces_lanes_for_each_agent():
    out = compose_timeline([], ["vault_indexer", "flush"], now=_NOW)
    assert len(out["lanes"]) == 2
    assert out["total_runs"] == 0
    assert all(lane["dot_count"] == 0 for lane in out["lanes"])
    assert len(out["axis_labels"]) == 5


def test_run_within_window_appears_as_dot():
    runs = [_run("vault_indexer", hours_ago=3)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    lane = out["lanes"][0]
    assert lane["dot_count"] == 1
    dot = lane["dots"][0]
    # 3h ago in a 24h window starting at now-24h = position (24-3)/24 = 87.5%
    assert 86.0 <= dot["left_pct"] <= 89.0
    assert dot["status_class"] == "success"
    assert "vault_indexer" in dot["title"]


def test_run_outside_window_is_dropped():
    runs = [_run("vault_indexer", hours_ago=48)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    assert out["lanes"][0]["dot_count"] == 0


def test_dash_underscore_normalization():
    """CSV has `vault-indexer`; agent_names has `vault_indexer`. They must match."""
    runs = [_run("vault-indexer", hours_ago=2)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    assert out["lanes"][0]["dot_count"] == 1


def test_status_classification():
    runs = [
        _run("a", hours_ago=1, status="success"),
        _run("a", hours_ago=2, status="error"),
        _run("a", hours_ago=3, status="recursion-guard"),
        _run("a", hours_ago=4, status="capped"),
    ]
    out = compose_timeline(runs, ["a"], now=_NOW)
    classes = sorted(d["status_class"] for d in out["lanes"][0]["dots"])
    assert classes == ["error", "error", "guarded", "success"]


def test_naive_timestamp_treated_as_utc():
    runs = [{
        "ts": (_NOW - timedelta(hours=2)).replace(tzinfo=None),
        "agent": "flush",
        "status": "success",
        "duration_ms": 500,
        "cost_usd": 0.0,
        "notes": "",
    }]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    assert out["lanes"][0]["dot_count"] == 1
