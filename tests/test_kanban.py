from datetime import UTC, datetime, timedelta

from lib import kanban


def _data():
    return {
        "research_queue": {
            "pending": [{"title": "Substrate repricing", "assigned_agent": None}],
            "in_flight": [{"title": "FDE intake pattern", "assigned_agent": "deep_researcher"}],
            "done": [],
        },
        "lint_reports": {"latest_date": "2026-05-12", "issues_total": 2,
                         "issues_by_severity": {"HIGH": 1, "MEDIUM": 1},
                         "raw_body": "- [HIGH] broken-wikilink — `foo.md`\n- [MEDIUM] orphan — `bar.md`"},  # noqa: E501
        "eval_last_run": {"passed": 7, "total_cases": 10,
                          "cases": [
                              {"id": "case-03-cross-domain", "status": "failed"},
                              {"id": "case-05-duplicate-merge", "status": "failed"},
                              {"id": "case-01-empty-vault", "status": "passed"},
                          ]},
        "manual_tickets": {
            "todo": [{"title": "Bump synth eval suite to 12", "assigned_agent": None},
                     {"title": "Rotate ldr api token", "assigned_agent": "Sean"}],
            "in_progress": [{"title": "Substack post 2 draft", "assigned_agent": "Sean"}],
            "done": [],
        },
        "job_feed": {
            "total_postings": 4,
            "top_fit": [
                {"company": "Sierra", "title": "Agent PM", "fit_score": 91, "status": "new"},
                {"company": "Anthropic", "title": "FDE", "fit_score": 88, "status": "screen-scheduled"},  # noqa: E501
            ],
            "by_status": {"new": 1, "screen-scheduled": 1},
            "active_count": 3,
        },
    }


def test_compose_tickets_includes_all_sources_private():
    tickets = kanban.compose_tickets(_data(), include_job_feed=True)
    sources = {t["source"] for t in tickets}
    assert sources == {"research", "lint", "eval", "manual", "feed"}


def test_compose_tickets_excludes_job_feed_when_public():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    sources = {t["source"] for t in tickets}
    assert "feed" not in sources
    assert sources == {"research", "lint", "eval", "manual"}


def test_compose_tickets_ids_are_stable():
    t1 = kanban.compose_tickets(_data(), include_job_feed=True)
    t2 = kanban.compose_tickets(_data(), include_job_feed=True)
    ids1 = sorted(t["id"] for t in t1)
    ids2 = sorted(t["id"] for t in t2)
    assert ids1 == ids2


def test_compose_tickets_eval_failures_only():
    tickets = kanban.compose_tickets(_data(), include_job_feed=True)
    eval_tickets = [t for t in tickets if t["source"] == "eval"]
    assert len(eval_tickets) == 2
    titles = [t["title"] for t in eval_tickets]
    assert all("cross-domain" in t or "duplicate-merge" in t for t in titles)


def test_compute_columns_unassigned_research_goes_backlog():
    t = {"source": "research", "assigned_agent": None, "_section_hint": "pending",
         "title": "x", "id": "x"}
    out = kanban.compute_columns([t], runs=[])
    assert out[0]["column"] == "backlog"


def test_compute_columns_assigned_research_goes_todo():
    t = {"source": "research", "assigned_agent": "deep_researcher",
         "_section_hint": "in_flight", "title": "x", "id": "x"}
    out = kanban.compute_columns([t], runs=[])
    assert out[0]["column"] == "todo"


def test_compute_columns_eval_failure_in_todo():
    t = {"source": "eval", "assigned_agent": None, "_section_hint": "todo",
         "title": "Eval failing: case-03", "id": "x"}
    out = kanban.compute_columns([t], runs=[])
    assert out[0]["column"] == "todo"


def test_compute_columns_in_progress_when_started_recently():
    now = datetime.now(UTC)
    runs = [
        {"agent": "deep_researcher", "status": "started",
         "ts": now - timedelta(minutes=2), "cost_usd": 0.0,
         "duration_ms": None, "notes": "x", "mode": None, "turns": None},
    ]
    t = {"source": "research", "assigned_agent": "deep_researcher",
         "_section_hint": "in_flight", "title": "x", "id": "x"}
    out = kanban.compute_columns([t], runs=runs)
    assert out[0]["column"] == "in_progress"
    assert out[0]["is_running"] is True


def test_compute_columns_done_recent():
    t = {"source": "manual", "assigned_agent": None, "_section_hint": "done",
         "title": "x", "id": "x"}
    out = kanban.compute_columns([t], runs=[])
    assert out[0]["column"] == "done"
