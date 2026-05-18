"""Tests for lib/aggregations.py — compute_fleet_status and compute_kpis.

Date-window note: fixtures use 2026-05-12 and 2026-05-13 dates.
compute_fleet_status uses a 7-day window; compute_kpis uses a 30-day window.
Both functions call datetime.now(UTC) internally. These tests are correct as
long as they run within 7 days of 2026-05-16 (fleet status) and within 30 days
(kpis). Task 10 will establish the end-parameter pattern for proper date injection.
"""
from datetime import date

import pytest

from lib import aggregations, readers

from .conftest import FIXTURES

AGENT_NAMES = [
    "vault_indexer", "vault_synthesizer", "deep_researcher", "meta_agent",
    "daily_driver", "knowledge_lint", "flush", "job_feed",
]


def _runs():
    return readers.read_run_history(FIXTURES / "sample-run-history.csv")


def test_compute_fleet_status_returns_eight_tiles():
    status = aggregations.compute_fleet_status(_runs(), AGENT_NAMES)
    assert len(status) == 8
    names = [s["agent"] for s in status]
    assert set(names) == set(AGENT_NAMES)


def test_compute_fleet_status_health_per_agent():
    status = aggregations.compute_fleet_status(_runs(), AGENT_NAMES)
    by_name = {s["agent"]: s for s in status}
    # synthesizer has one error + one ok + one skipped → degraded (amber)
    assert by_name["vault_synthesizer"]["health"] == "degraded"
    # job_feed has one ok → healthy
    assert by_name["job_feed"]["health"] == "healthy"


def test_compute_kpis_eval_pass_and_spend():
    runs = _runs()
    eval_run = readers.read_eval_last_run(FIXTURES / "sample-eval-last-run.md")
    kpis = aggregations.compute_kpis(runs, eval_run, gemini_total=8.40, council_total=0.41)
    assert kpis["eval_pass"] == "7 / 10"
    assert kpis["fleet_spend_30d_usd"] == pytest.approx(0.3812)
    assert 0 < kpis["local_only_share_pct"] <= 100
    assert kpis["spend_governors"] == "$50 / mo"


def test_compute_synth_series_60_days():
    manifests = [
        {"date": date(2026, 5, 1), "concepts_written": 0},
        {"date": date(2026, 5, 2), "concepts_written": 0},
        {"date": date(2026, 5, 10), "concepts_written": 0},
        {"date": date(2026, 5, 11), "concepts_written": 90},
        {"date": date(2026, 5, 13), "concepts_written": 114},
    ]
    series = aggregations.compute_synth_series(manifests, days=14, end=date(2026, 5, 14))
    assert len(series) == 14
    # day 2026-05-13 = index 12 in 14-day series ending 5/14
    assert series[12]["concepts"] == 114
    # missing dates fill with None (not 0 — we want a visible gap)
    assert series[7]["concepts"] is None  # 2026-05-07


def test_compute_regression_window_detects_silent_nights():
    manifests = [{"date": date(2026, 5, d), "concepts_written": 0} for d in range(1, 11)]
    manifests.append({"date": date(2026, 5, 11), "concepts_written": 90})
    window = aggregations.compute_regression_window(manifests)
    assert window["start"] == date(2026, 5, 1)
    assert window["end"] == date(2026, 5, 10)
    assert window["nights"] == 10


def test_compute_eval_sparkline_returns_14_values():
    # eval suite history isn't on disk yet — we synthesize from last_run only for v1
    eval_run = {"passed": 7, "total_cases": 10, "cases": []}
    spark = aggregations.compute_eval_sparkline(eval_run, days=14)
    assert len(spark) == 14
    assert all(0 <= v <= 10 for v in spark)
    assert spark[-1] == 7


def test_compute_cost_trend_30_day_stacked():
    runs = _runs()
    trend = aggregations.compute_cost_trend(runs, days=30, end=date(2026, 5, 14))
    assert len(trend["days"]) == 30
    assert set(trend["agents"]) <= set(AGENT_NAMES) | {"other"}
    # series[agent] is a list of `days` floats
    for _agent, series in trend["series"].items():
        assert len(series) == 30


def test_compute_model_mix_buckets():
    runs = _runs()
    mix = aggregations.compute_model_mix(runs)
    assert "local" in mix
    assert "cloud" in mix
    # fixture has one daily_driver run (cloud-ish) and several local
    total_pct = sum(v["pct"] for v in mix.values())
    assert 99.0 <= total_pct <= 101.0  # rounding slack


def test_compute_recent_runs_returns_last_50_desc():
    runs = _runs()
    recent = aggregations.compute_recent_runs(runs, n=5)
    assert len(recent) == 5
    timestamps = [r["ts"] for r in recent]
    assert timestamps == sorted(timestamps, reverse=True)


def test_compute_agent_state_maps_normalized_names_to_health():
    fleet_status = [
        {"agent": "vault_indexer", "health": "healthy"},
        {"agent": "vault-synthesizer", "health": "degraded"},  # CSV-style name
        {"agent": "deep_researcher", "health": "down"},
        {"agent": "flush", "health": "unknown"},
    ]
    out = aggregations.compute_agent_state(fleet_status)
    # Normalized: dash→underscore
    assert out["vault_indexer"] == "healthy"
    assert out["vault_synthesizer"] == "degraded"
    assert out["deep_researcher"] == "down"
    # unknown is kept (caller decides whether to render a dot)
    assert out["flush"] == "unknown"
