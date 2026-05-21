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


def test_render_kanban_includes_agent_dot_and_column_spark(tmp_path):
    """Smoke: rendered kanban.html contains the new chrome markers (Task 8
    wires the Python side; Task 9 lands the template that emits the markers)."""
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_public(agg, tickets, tmp_path)
    html = (tmp_path / "kanban.html").read_text()
    assert "agent-dot" in html
    assert "column-spark" in html


def test_kanban_template_renders_hero_plate(tmp_path):
    """The /kanban hero-plate lands above the filter chips on both passes."""
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_public(agg, tickets, tmp_path)
    html = (tmp_path / "kanban.html").read_text()
    assert 'class="kanban-hero"' in html
    assert "TICKET FLOW · LAST 7 DAYS" in html
    # Hero-plate appears before the filter-chip row in source order.
    assert html.index("kanban-hero") < html.index("kanban-filters")
    # No em dashes in our new prose strings (project copy guide).
    hero_block = html[html.index("kanban-hero"):html.index("kanban-filters")]
    assert "—" not in hero_block


def test_fleet_ribbon_renders_glossary_and_legend(tmp_path):
    """Task 4.1 + 4.2: the public /fleet ribbon panel ships an 8-entry agent
    glossary and a 3-item color legend so a non-developer reader can decode
    the matchstick row without prior context."""
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_public(agg, tickets, tmp_path)
    fleet = (tmp_path / "index.html").read_text()
    # Glossary block + every one of the 8 agent names + the legend
    assert 'class="fleet-glossary"' in fleet
    for agent in (
        "vault_synthesizer", "vault_indexer", "deep_researcher", "meta_agent",
        "daily_driver", "knowledge_lint", "flush", "job_feed",
    ):
        assert f"<dt>{agent}</dt>" in fleet, f"glossary missing {agent}"
    assert "(private surface only)" in fleet  # job_feed glossary tag
    assert 'class="ribbon-legend"' in fleet
    assert "healthy run" in fleet and "failed run" in fleet and "quiet day" in fleet
    # Legend appears before the matchstick row (eyebrow → legend → ribbon)
    assert fleet.index("ribbon-legend") < fleet.index("fleet-ribbon")
    # No em dashes introduced by the new blocks
    ribbon_close = fleet.index("</section>", fleet.index("fleet-ribbon"))
    glossary_block = fleet[fleet.index("ribbon-legend"):ribbon_close]
    assert "—" not in glossary_block


def test_timeline_titles_include_term_definitions(tmp_path):
    """Task 4.3: 24h timeline dots whose status is a known insider term carry
    a plain-English definition appended to the native browser tooltip."""
    data = _data()
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    tickets = kanban.compute_columns(tickets, data["agent_runs"])
    render.render_public(agg, tickets, tmp_path)
    fleet = (tmp_path / "index.html").read_text()
    # Every recursion-guard event title gets the long-form definition appended.
    if "recursion-guard" in fleet:
        assert "Safety mechanism: stops an agent from triggering itself in a loop." in fleet
    # No em dashes leaked into the rendered page from our new strings.
    assert "—" not in fleet


def test_kanban_quiet_week_prose_is_inflow_scoped(tmp_path):
    """Task 4.4: when the 7-day inflow is zero, the hero prose talks about
    inflow only — not backlog state, which compose_kanban_hero_stats does
    not observe.
    """
    # Drive the renderer with zero tickets so the quiet-week branch fires.
    data = {
        "research_queue": {"pending": [], "in_flight": [], "done": []},
        "lint_reports": {"latest_date": "2026-05-19", "issues_total": 0,
                         "issues_by_severity": {}, "issues": []},
        "manual_tickets": {"todo": [], "in_progress": [], "done": []},
        "agent_runs": [],
        "eval_last_run": {"passed": 0, "failed": 0, "skipped": 0,
                          "total_cases": 0, "cases": []},
        "job_feed": {"total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0},
        "synth_manifests": [],
        "gemini_spend": {"total_usd": 0, "run_count": 0, "tiers": {}},
        "council_spend": {"month_total_usd": 0, "day_count": 0, "days": []},
        "job_feed_manifests": {"latest": None, "last_7": []},
        "target_companies": {"tier_1": [], "tier_2": [], "tier_3": [],
                             "by_status": {}, "total": 0},
        "warm_intros": {"active": [], "prospecting": [], "second_degree": [], "total": 0},
        "agent_names": ["vault_synthesizer"],
    }
    agg = aggregations.compute_all(data, end=date(2026, 5, 14))
    tickets = kanban.compute_columns(
        kanban.compose_tickets(data, include_job_feed=False), data["agent_runs"]
    )
    render.render_public(agg, tickets, tmp_path)
    kb = (tmp_path / "kanban.html").read_text()
    assert "Quiet week." in kb
    assert "No new tickets surfaced this week." in kb
    # Old, misleading copy must be gone — it implied we know backlog state.
    assert "Backlog is caught up" not in kb
    # New prose is em-dash-free per project copy guide.
    hero = kb[kb.index("kanban-hero"):kb.index("kanban-filters")]
    assert "—" not in hero


def test_kanban_template_renders_headline_subheadline_and_modal_shell(tmp_path):
    """Kanban board uses .ticket-headline + .ticket-subheadline and emits a modal shell."""
    from lib import aggregations, kanban, render
    data = {
        "research_queue": {"pending": [
            {"title": "Topic 99 — Demo prompt. With prose body that should land in details.",
             "assigned_agent": None},
        ], "in_flight": [], "done": []},
        "lint_reports": {"latest_date": "2026-05-19", "issues_total": 0,
                         "issues_by_severity": {}, "issues": []},
        "manual_tickets": {"todo": [], "in_progress": [], "done": []},
        "agent_runs": [], "eval_last_run": {"passed": 0, "failed": 0, "skipped": 0,
                                             "total_cases": 0, "cases": []},
        "job_feed": {"total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0},
        "synth_manifests": [], "gemini_spend": {"total_usd": 0, "run_count": 0, "tiers": {}},
        "council_spend": {"month_total_usd": 0, "day_count": 0, "days": []},
        "job_feed_manifests": {"latest": None, "last_7": []},
        "target_companies": {"tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0},
        "warm_intros": {"active": [], "prospecting": [], "second_degree": [], "total": 0},
        "agent_names": ["vault_synthesizer"],
    }
    agg = aggregations.compute_all(data)
    tickets = kanban.compute_columns(
        kanban.compose_tickets(data, include_job_feed=False), data["agent_runs"]
    )
    out = tmp_path / "out"
    render.render_public(agg, tickets, out)
    html = (out / "kanban.html").read_text()
    assert 'class="ticket-headline"' in html
    # The Topic 99 ticket carries its full prose on data-details for the modal JS
    assert "data-details=" in html
    assert "With prose body" in html  # the details payload
    # Modal shell rendered once at the bottom of the partial
    assert html.count('id="ticket-modal"') == 1
    assert "Topic 99 — Demo prompt" in html
