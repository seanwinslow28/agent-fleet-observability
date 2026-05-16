"""Tests for lib/aggregations.py — compute_fleet_status and compute_kpis.

Date-window note: fixtures use 2026-05-12 and 2026-05-13 dates.
compute_fleet_status uses a 7-day window; compute_kpis uses a 30-day window.
Both functions call datetime.now(UTC) internally. These tests are correct as
long as they run within 7 days of 2026-05-16 (fleet status) and within 30 days
(kpis). Task 10 will establish the end-parameter pattern for proper date injection.
"""
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
