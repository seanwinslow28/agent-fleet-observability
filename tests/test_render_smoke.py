"""Smoke tests for lib/render.py — public + private render passes.

Tests confirm:
- Both passes produce index.html, kanban.html, data.json
- Public pass strips job-feed vault paths, target_companies, warm_intros names
- Private pass retains Strategic funnel, warm-intro names, Anthropic tier-1 row
"""
import json
from datetime import date

from lib import aggregations, kanban, readers, render

from .conftest import FIXTURES


def _data():
    return {
        "agent_runs": readers.read_run_history(FIXTURES / "sample-run-history.csv"),
        "synth_manifests": readers.read_synth_manifests(FIXTURES),
        "gemini_spend": readers.read_gemini_spend(FIXTURES / "sample-gemini-spend.json"),
        "council_spend": {"month_total_usd": 0.41, "day_count": 1, "days": []},
        "lint_reports": readers.read_lint_reports(FIXTURES),
        "eval_last_run": readers.read_eval_last_run(FIXTURES / "sample-eval-last-run.md"),
        "job_feed_db": {
            "total_postings": 4, "by_status": {"new": 1}, "top_fit": [], "active_count": 3
        },
        "job_feed_manifests": {"latest": None, "last_7": []},
        "research_queue": readers.read_research_queue(FIXTURES / "sample-research-queue.md"),
        "manual_tickets": readers.read_manual_tickets(FIXTURES / "sample-tickets.md"),
        "target_companies": readers.read_target_companies(FIXTURES / "sample-target-companies.md"),
        "warm_intros": readers.read_warm_intros(FIXTURES / "sample-warm-intros.md"),
        "agent_names": [
            "vault_indexer", "vault_synthesizer", "deep_researcher", "meta_agent",
            "daily_driver", "knowledge_lint", "flush", "job_feed",
        ],
    }


def test_render_public_emits_html_and_data_json(tmp_path):
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(
        {**data, "lint_reports": {**data["lint_reports"], "raw_body": ""},
         "eval_last_run": data["eval_last_run"]},
        include_job_feed=False,
    )
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_public(agg, tickets, tmp_path)
    fleet = (tmp_path / "index.html").read_text()
    kb = (tmp_path / "kanban.html").read_text()
    sidecar = json.loads((tmp_path / "data.json").read_text())
    assert "Agent Fleet Observability" in fleet
    assert "Job Feed" not in kb  # public kanban has 4 chips, not 5
    assert sidecar["tickets"]
    # privacy boundary smoke check
    assert "vault/.job-feed" not in fleet
    assert "vault/20_projects" not in fleet
    # §4d live-wire: target_companies + warm_intros names must not leak to public
    assert "Anthropic" not in fleet or fleet.count("Anthropic") == 0  # only in target_companies
    assert "Larry" not in fleet
    assert "Messari" not in fleet


def test_render_private_includes_job_feed_lane(tmp_path):
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(
        {**data, "lint_reports": {**data["lint_reports"], "raw_body": ""}},
        include_job_feed=True,
    )
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_private(agg, tickets, tmp_path)
    kb = (tmp_path / "kanban.html").read_text()
    fleet = (tmp_path / "index.html").read_text()
    assert "Job Feed" in kb
    assert (tmp_path / "data.json").exists()
    # §4d live-wire: target_companies + warm_intros render on PRIVATE
    assert "Strategic" in fleet  # "Strategic 6" in target funnel header
    assert "Larry" in fleet  # warm-intro active row
    assert "Anthropic" in fleet  # tier-1 row
