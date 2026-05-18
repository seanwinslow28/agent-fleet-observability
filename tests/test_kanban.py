from datetime import UTC, datetime, timedelta

from lib import kanban


def _data():
    return {
        "research_queue": {
            "pending": [
                {"title": "Topic 5 — OpenRouter routing config. Some long prose.",
                 "assigned_agent": None},
                {"title": "Short question that fits in a card?",
                 "assigned_agent": None},
            ],
            "in_flight": [
                {"title": "Topic 7 — FDE intake pattern. Long prose continues.",
                 "assigned_agent": "deep_researcher"},
            ],
            "done": [],
        },
        "lint_reports": {
            "latest_date": "2026-05-12",
            "issues_total": 4,
            "issues_by_severity": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 1},
            "issues": [
                {"severity": "CRITICAL", "rule": "contradiction", "tier": "T2",
                 "path": "knowledge/concepts/foo.md", "context": "contradicts bar"},
                {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                 "path": "knowledge/connections/baz.md", "context": "concept_edges"},
                {"severity": "MEDIUM", "rule": "stale-frontmatter", "tier": "T2",
                 "path": "vault/qux.md", "context": "old format"},
                {"severity": "LOW", "rule": "duplicate-title", "tier": "T2",
                 "path": "concepts/dup.md", "context": "same as dup-2"},
            ],
        },
        "agent_runs": [],  # Task 5 will populate this for the eval tests
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
                {"company": "Anthropic", "title": "FDE", "fit_score": 88,
                 "status": "screen-scheduled"},
            ],
            "by_status": {"new": 1, "screen-scheduled": 1},
            "active_count": 3,
        },
    }


def test_compose_tickets_includes_all_sources_private():
    tickets = kanban.compose_tickets(_data(), include_job_feed=True)
    sources = {t["source"] for t in tickets}
    # eval re-enters via agent_runs in Task 5
    assert sources == {"research", "lint", "manual", "feed"}


def test_compose_tickets_excludes_job_feed_when_public():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    sources = {t["source"] for t in tickets}
    assert "feed" not in sources
    assert sources == {"research", "lint", "manual"}


def test_compose_tickets_ids_are_stable():
    t1 = kanban.compose_tickets(_data(), include_job_feed=True)
    t2 = kanban.compose_tickets(_data(), include_job_feed=True)
    ids1 = sorted(t["id"] for t in t1)
    ids2 = sorted(t["id"] for t in t2)
    assert ids1 == ids2


def test_compose_tickets_eval_source_pending_for_task_5():
    """Eval-source assertions live in test_compose_failures_to_tickets_*
    after Task 5 wires agent_runs into compose_tickets."""
    pass


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


def test_parse_research_title_topic_prefix():
    raw = (
        "Topic 8 — OpenRouter Python integration patterns for the agents-sdk fleet. "
        "Cover: (1) auth header pattern... — done 2026-05-12 02:54 → [[20_projects/research/foo]]"
    )
    out = kanban._parse_research_title(raw)
    expected_title = "Topic 8 — OpenRouter Python integration patterns for the agents-sdk fleet"
    assert out["title"] == expected_title
    assert "Cover: (1) auth header pattern" in out["details"]


def test_parse_research_title_short_question_passes_through():
    raw = "What are the practical differences between MLX and GGUF for 14B models?"
    out = kanban._parse_research_title(raw)
    assert out["title"] == raw
    assert out["details"] == raw


def test_parse_research_title_long_falls_back_to_truncation():
    raw = (
        "A very long single-sentence research question that runs past eighty characters "
        "and therefore has no Topic prefix and no internal sentence break for the parser to use"
    )
    out = kanban._parse_research_title(raw)
    assert len(out["title"]) <= 81  # 80 + "…"
    assert out["title"].endswith("…")
    assert out["details"] == raw


def test_parse_research_title_strips_done_link_tail():
    raw = "Quick topic. — done 2026-05-01 02:00 → [[20_projects/research/old-topic]]"
    out = kanban._parse_research_title(raw)
    assert "[[" not in out["title"]
    assert "done 2026-05" not in out["title"]


def test_compose_tickets_lint_drains_severity_in_order():
    data = _data()
    # Inflate fixture: 5 CRITICAL, 30 HIGH, 50 MEDIUM
    extra = []
    for i in range(4):  # already 1 CRITICAL in fixture
        extra.append({"severity": "CRITICAL", "rule": "contradiction", "tier": "T2",
                      "path": f"c{i}.md", "context": "x"})
    for i in range(29):  # already 1 HIGH in fixture
        extra.append({"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                      "path": f"h{i}.md", "context": "x"})
    for i in range(49):  # already 1 MEDIUM
        extra.append({"severity": "MEDIUM", "rule": "stale-frontmatter", "tier": "T2",
                      "path": f"m{i}.md", "context": "x"})
    data["lint_reports"]["issues"] = (
        data["lint_reports"]["issues"][:3] + extra  # keep original ordering
    )
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint_tickets = [t for t in tickets if t["source"] == "lint"]
    assert len(lint_tickets) == 20
    # First 5 must be CRITICAL, then HIGH fills the rest
    severities = [t["_severity"] for t in lint_tickets]
    assert severities[:5] == ["CRITICAL"] * 5
    assert all(s == "HIGH" for s in severities[5:])


def test_compose_tickets_lint_title_uses_basename():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"][0]
    # basename only in the displayed title
    assert "/" not in lint["title"]
    # full path preserved in details
    assert "knowledge/concepts/foo.md" in lint["details"]


def test_compose_tickets_research_title_parsed():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    research = [t for t in tickets if t["source"] == "research"]
    titles = [t["title"] for t in research]
    # Topic-N prefix items collapse to short title
    assert "Topic 5 — OpenRouter routing config" in titles
    # Short questions pass through verbatim
    assert "Short question that fits in a card?" in titles
    # Full prose preserved in details for one of the Topic-N items
    topic_5 = next(t for t in research if t["title"].startswith("Topic 5"))
    assert "Some long prose" in topic_5["details"]
