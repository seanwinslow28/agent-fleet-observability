from datetime import UTC, date, datetime, timedelta

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


def _run(agent, status, minutes_ago, notes=""):
    return {
        "agent": agent, "status": status,
        "ts": datetime.now(UTC) - timedelta(minutes=minutes_ago),
        "cost_usd": 0.0, "duration_ms": None, "turns": None,
        "mode": None, "notes": notes,
    }


def test_compose_tickets_includes_all_sources_private():
    d = _data()
    d["agent_runs"] = [_run("vault_indexer", "failed", 60)]
    tickets = kanban.compose_tickets(d, include_job_feed=True)
    sources = {t["source"] for t in tickets}
    assert sources == {"research", "lint", "eval", "manual", "feed"}


def test_compose_tickets_excludes_job_feed_when_public():
    d = _data()
    d["agent_runs"] = [_run("vault_indexer", "failed", 60)]
    tickets = kanban.compose_tickets(d, include_job_feed=False)
    sources = {t["source"] for t in tickets}
    assert "feed" not in sources
    assert sources == {"research", "lint", "eval", "manual"}


def test_compose_tickets_ids_are_stable():
    t1 = kanban.compose_tickets(_data(), include_job_feed=True)
    t2 = kanban.compose_tickets(_data(), include_job_feed=True)
    ids1 = sorted(t["id"] for t in t1)
    ids2 = sorted(t["id"] for t in t2)
    assert ids1 == ids2


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
    assert out["headline"] == expected_title
    assert "Cover: (1) auth header pattern" in out["details"]


def test_parse_research_title_keeps_periods_inside_abbreviations():
    raw = (
        "Topic 13 — Pi (pi.dev) platform overview in 2026. "
        "What the developer platform at https://pi.dev is."
    )
    out = kanban._parse_research_title(raw)
    assert out["headline"] == "Topic 13 — Pi (pi.dev) platform overview in 2026"


def test_parse_research_title_short_question_passes_through():
    raw = "What are the practical differences between MLX and GGUF for 14B models?"
    out = kanban._parse_research_title(raw)
    assert out["headline"] == raw
    assert out["details"] == raw


def test_parse_research_title_long_falls_back_to_truncation():
    raw = (
        "A very long single-sentence research question that runs past eighty characters "
        "and therefore has no Topic prefix and no internal sentence break for the parser to use"
    )
    out = kanban._parse_research_title(raw)
    assert len(out["headline"]) <= 81  # 80 + "…"
    assert out["headline"].endswith("…")
    assert out["details"] == raw


def test_parse_research_title_strips_done_link_tail():
    raw = "Quick topic. — done 2026-05-01 02:00 → [[20_projects/research/old-topic]]"
    out = kanban._parse_research_title(raw)
    assert "[[" not in out["headline"]
    assert "done 2026-05" not in out["headline"]


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
    # basename only in the displayed title — no path separators
    assert "/" not in lint["title"]
    # Raw extension stripped from the headline (humanized) but full path
    # preserved in details.
    assert ".md" not in lint["headline"]
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


def test_failures_to_tickets_one_per_unresolved_failure():
    runs = [
        _run("vault_indexer", "ok", 60 * 24),         # yesterday: ok
        _run("vault_indexer", "failed", 60 * 5),      # 5h ago: failed
        _run("vault_synthesizer", "failed", 60 * 3),  # 3h ago: failed
    ]
    out = kanban._failures_to_tickets(runs)
    agents = sorted(t["assigned_agent"] for t in out)
    assert agents == ["vault_indexer", "vault_synthesizer"]
    assert all(t["source"] == "eval" for t in out)


def test_failures_to_tickets_resolved_by_subsequent_success():
    runs = [
        _run("vault_indexer", "failed", 60 * 5),  # 5h ago: failed
        _run("vault_indexer", "ok", 60 * 2),      # 2h ago: recovered
    ]
    out = kanban._failures_to_tickets(runs)
    assert out == []


def test_failures_to_tickets_ages_off_after_7_days():
    runs = [
        _run("vault_indexer", "failed", 60 * 24 * 8),  # 8 days ago
    ]
    out = kanban._failures_to_tickets(runs)
    assert out == []


def test_failures_to_tickets_title_uses_notes_then_status():
    # New schema: title/headline = "{agent} failed: {status_word}"; notes go to details.
    runs = [
        _run("agent_a", "failed", 30, notes="ConnectTimeout to backend"),
        _run("agent_b", "failed", 60),  # no notes
    ]
    out = sorted(kanban._failures_to_tickets(runs), key=lambda t: t["assigned_agent"])
    assert out[0]["title"] == "agent_a failed: failed"
    assert out[0]["title"].startswith("agent_a failed:")
    assert "ConnectTimeout" in (out[0]["details"] or "")  # notes preserved in details
    assert "failed" in out[1]["title"]


def test_failures_to_tickets_title_is_status_word_notes_in_details():
    # New schema: title is always "{agent} failed: {status_word}" — no truncation needed.
    # Full notes are preserved verbatim in details instead.
    long_notes = "x" * 200
    runs = [_run("agent_a", "failed", 30, notes=long_notes)]
    out = kanban._failures_to_tickets(runs)
    assert out[0]["title"] == "agent_a failed: failed"
    assert out[0]["details"] == long_notes


def test_failures_to_tickets_section_hint_is_todo():
    runs = [_run("agent_a", "failed", 30)]
    out = kanban._failures_to_tickets(runs)
    assert out[0]["_section_hint"] == "todo"


def test_failures_to_tickets_empty_runs_returns_empty():
    """Followups: explicit contract — empty input → empty output."""
    assert kanban._failures_to_tickets([]) == []


def test_failures_to_tickets_status_case_normalized():
    """Followups: status comparison must be .lower()-aware."""
    runs = [
        {"agent": "x", "status": "FAILED", "ts": datetime.now(UTC),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "shouty"},
    ]
    out = kanban._failures_to_tickets(runs)
    assert len(out) == 1
    assert out[0]["source"] == "eval"


def test_failures_to_tickets_multiple_failures_same_agent_picks_latest():
    """Followups: with no intervening success, the newest failure wins."""
    base = datetime.now(UTC)
    runs = [
        {"agent": "x", "status": "failed", "ts": base - timedelta(hours=6),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "old"},
        {"agent": "x", "status": "failed", "ts": base - timedelta(hours=1),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "new"},
    ]
    out = kanban._failures_to_tickets(runs)
    assert len(out) == 1
    # Newest failure survives — its notes show up in details
    assert out[0]["details"] == "new"


def test_compose_tickets_all_empty_inputs_returns_empty_list():
    """Followups: cheap safety net for the all-empty-inputs path."""
    assert kanban.compose_tickets({}, include_job_feed=False) == []


def test_parse_research_title_returns_headline_and_details():
    out = kanban._parse_research_title(
        "Topic 5 — OpenRouter routing config. Some long prose continues here."
    )
    assert out["headline"] == "Topic 5 — OpenRouter routing config"
    assert out["details"].startswith("Topic 5")
    assert "Some long prose" in out["details"]
    # No more `title` or `subheadline` keys from this function
    assert "subheadline" not in out


def test_parse_research_title_short_input_no_truncation():
    out = kanban._parse_research_title("Short question that fits?")
    assert out["headline"] == "Short question that fits?"
    assert "…" not in out["headline"]


def test_parse_research_title_strips_done_tail():
    out = kanban._parse_research_title(
        "Topic 12 — Foo bar. Details. — done 2026-05-16 02:46 → [[wikilink]]"
    )
    assert out["headline"] == "Topic 12 — Foo bar"
    # Done-tail stripped from details too
    assert "done 2026-05-16" not in out["details"]
    assert "wikilink" not in out["details"]


def test_parse_research_title_empty_input_guard():
    """Followups: previously returned headline="" for empty/whitespace input."""
    result = kanban._parse_research_title("   ")
    assert result["headline"] == "(no title)"
    assert result["details"] == "   "  # raw preserved


def test_parse_research_title_done_tail_only_input():
    """Input that becomes empty AFTER the done-tail strip hits the second guard."""
    result = kanban._parse_research_title("— done 2026-05-01")
    assert result["headline"] == "(no title)"
    # The second guard preserves raw (not raw-or-empty), since raw is non-empty
    assert result["details"] == "— done 2026-05-01"


def test_research_ticket_uses_headline_and_empty_subheadline():
    """Pending research items have no per-item date → empty subheadline."""
    data = _data()
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    topic5 = next(t for t in tickets if t["source"] == "research"
                  and t["headline"].startswith("Topic 5"))
    assert topic5["headline"] == "Topic 5 — OpenRouter routing config"
    assert topic5["subheadline"] == ""
    assert topic5["title"] == topic5["headline"]  # back-compat
    # Full prose retained for the click-to-modal payload
    assert "Some long prose" in topic5["details"]


def test_lint_ticket_headline_strips_tier_subheadline_has_report_date():
    data = _data()
    # _data() sets lint_reports["latest_date"] = "2026-05-12"
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    # foo.md → "Foo" after humanizing; the raw filename moves to details.
    crit = next(t for t in tickets if t["source"] == "lint"
                and "foo.md" in (t["details"] or ""))
    assert crit["headline"] == "contradiction · Foo"
    assert "(T2)" not in crit["headline"]
    assert crit["subheadline"] == "2026-05-12"
    assert crit["_tier"] == "T2"  # still on the dict for meta line / future use
    assert "contradicts bar" in crit["details"]
    assert "foo.md" in crit["details"]


def test_eval_failure_ticket_subheadline_is_failure_date():
    runs = [_run("vault_synthesizer", "failed", minutes_ago=30, notes="cap-hit")]
    data = {**_data(), "agent_runs": runs}
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    fail = next(t for t in tickets if t["source"] == "eval")
    assert fail["headline"].startswith("vault_synthesizer failed")
    # Subheadline is the failure timestamp date (YYYY-MM-DD)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    assert fail["subheadline"] == today
    # Full notes preserved in details for the modal
    assert "cap-hit" in (fail["details"] or "")


def test_manual_ticket_has_empty_subheadline():
    data = _data()
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    manual = next(t for t in tickets if t["source"] == "manual")
    assert manual["headline"] == manual["title"]
    assert manual["subheadline"] == ""  # tickets.md has no per-item date


def test_feed_ticket_subheadline_is_first_seen_date_or_empty():
    """Feed subheadline = first_seen_at date when present, else empty."""
    data = _data()
    # Augment one feed row with first_seen_at
    data["job_feed"]["top_fit"][0]["first_seen_at"] = "2026-05-15T08:30:00Z"
    tickets = kanban.compose_tickets(data, include_job_feed=True)
    sierra = next(t for t in tickets if t["source"] == "feed"
                  and t["headline"].startswith("Sierra"))
    assert sierra["headline"] == "Sierra · Agent PM"
    assert sierra["subheadline"] == "2026-05-15"
    # The second feed row had no first_seen_at → empty subheadline
    anthropic = next(t for t in tickets if t["source"] == "feed"
                     and t["headline"].startswith("Anthropic"))
    assert anthropic["subheadline"] == ""


def test_eval_cases_become_tickets():
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 7, "failed": 2, "skipped": 1, "total_cases": 10,
            "cases": [
                {"id": "case-1-broken-wikilink", "category": "lint", "status": "passed"},
                {"id": "case-7-cycle-detect",    "category": "lint", "status": "failed"},
                {"id": "case-9-concept-merge",   "category": "synth", "status": "failed"},
                {"id": "case-10-stale-frontmatter", "category": "lint", "status": "skipped"},
            ],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    eval_tix = [t for t in tickets if t["source"] == "eval"]
    headlines = {t["headline"] for t in eval_tix}
    assert "eval failed: case-7-cycle-detect" in headlines
    assert "eval failed: case-9-concept-merge" in headlines
    # Passed + skipped cases must NOT become tickets
    assert not any("case-1-broken" in h for h in headlines)
    assert not any("case-10-stale" in h for h in headlines)


def test_eval_case_subheadline_is_run_date_when_run_id_is_dated():
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 9, "failed": 1, "skipped": 0, "total_cases": 10,
            "cases": [{"id": "case-3", "category": "synth", "status": "failed"}],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    case_tix = [t for t in tickets if t["source"] == "eval"
                and t["_eval_case_id"] == "case-3"]
    assert len(case_tix) == 1
    # Subheadline = first 10 chars of run_id when it parses as a date
    assert case_tix[0]["subheadline"] == "2026-05-18"


def test_eval_case_subheadline_empty_when_run_id_not_date_shaped():
    """If run_id doesn't start with YYYY-MM-DD, subheadline falls back to empty."""
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 0, "failed": 1, "skipped": 0, "total_cases": 1,
            "cases": [{"id": "case-3", "category": "synth", "status": "failed"}],
            "run_id": "local-run-42",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    case = next(t for t in tickets if t.get("_eval_case_id") == "case-3")
    assert case["subheadline"] == ""


def test_eval_case_status_uppercase_is_normalized():
    """`.lower()` on case status — `FAILED` still becomes a ticket."""
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 0, "failed": 1, "skipped": 0, "total_cases": 1,
            "cases": [{"id": "case-shouty", "category": "lint", "status": "FAILED"}],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    headlines = {t["headline"] for t in tickets if t["source"] == "eval"}
    assert "eval failed: case-shouty" in headlines


def test_eval_cases_and_agent_run_failures_coexist():
    runs = [_run("deep_researcher", "failed", minutes_ago=10, notes="timeout 900s")]
    data = {
        **_data(),
        "agent_runs": runs,
        "eval_last_run": {
            "passed": 9, "failed": 1, "skipped": 0, "total_cases": 10,
            "cases": [{"id": "case-3", "category": "synth", "status": "failed"}],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    headlines = {t["headline"] for t in tickets if t["source"] == "eval"}
    assert any("deep_researcher failed" in h for h in headlines)
    assert any("case-3" in h for h in headlines)


# ---------------------------------------------------------------------------
# Task 1: credibility-cluster fixes
# ---------------------------------------------------------------------------


def test_lint_duplicate_ids_collapse_to_one_ticket_with_edge_count():
    """8 broken-wikilink edges in one source file → one ticket with count=8.

    Reproduces the 2026-05-21 critique: the lint composer was emitting one
    ticket per broken-wikilink edge even when many edges shared the same
    source file (and therefore the same _stable_id), producing 8 visually
    identical rows. They must collapse.
    """
    same_path = "knowledge/connections/mcp-server-and-knowledge-graph-synergy.md"
    edges = [
        {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
         "path": same_path, "context": f"edge_target_{i}"}
        for i in range(8)
    ]
    data = {
        "lint_reports": {
            "latest_date": "2026-05-17",
            "issues_total": 8,
            "issues_by_severity": {"HIGH": 8},
            "issues": edges,
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"]
    assert len(lint) == 1
    ticket = lint[0]
    assert ticket["count"] == 8
    assert ticket["headline"].endswith("· 8 edges")
    # Each edge target preserved in details (deduplicated, newline-separated).
    for i in range(8):
        assert f"edge_target_{i}" in ticket["details"]


def test_lint_single_edge_has_no_count_suffix_and_count_field_is_one():
    """Edge case: a single-occurrence lint ticket must NOT show "· 1 edges"."""
    data = {
        "lint_reports": {
            "latest_date": "2026-05-17",
            "issues_total": 1,
            "issues_by_severity": {"HIGH": 1},
            "issues": [
                {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                 "path": "knowledge/lone.md", "context": "lonely_target"},
            ],
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"]
    assert len(lint) == 1
    assert lint[0]["count"] == 1
    assert "edges" not in lint[0]["headline"]


def test_humanize_slug_basic_and_acronyms():
    """File-slug humanization rules."""
    assert kanban._humanize_slug(
        "mcp-server-and-knowledge-graph-synergy.md"
    ) == "MCP server and knowledge graph synergy"
    # Title-case only the first word.
    assert kanban._humanize_slug("hello-world.md") == "Hello world"
    # Underscores also become spaces.
    assert kanban._humanize_slug("foo_bar_baz.md") == "Foo bar baz"
    # No extension is fine.
    assert kanban._humanize_slug("plain-name") == "Plain name"
    # No hyphens, no extension → single word title-cased.
    assert kanban._humanize_slug("foo") == "Foo"
    # Multiple acronyms.
    assert kanban._humanize_slug("api-cli-ui-tour.md") == "API CLI UI tour"
    # Acronym at the front stays uppercase, not Title-cased.
    assert kanban._humanize_slug("llm.md") == "LLM"
    # Empty input → returned verbatim (defensive).
    assert kanban._humanize_slug("") == ""


def test_lint_headline_humanizes_slug_and_keeps_filename_in_details():
    """Lint headlines no longer show raw file slugs; raw name moves to details."""
    data = {
        "lint_reports": {
            "latest_date": "2026-05-17",
            "issues_total": 1,
            "issues_by_severity": {"HIGH": 1},
            "issues": [
                {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                 "path": "knowledge/connections/mcp-server-and-knowledge-graph-synergy.md",
                 "context": "concept_edges"},
            ],
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"][0]
    assert (
        lint["headline"]
        == "broken-wikilink · MCP server and knowledge graph synergy"
    )
    # Raw filename moves to data-details so the modal still shows it.
    assert "mcp-server-and-knowledge-graph-synergy.md" in lint["details"]


def test_eval_meta_error_failures_are_filtered():
    """Agent-run failures whose notes are eval-runner placeholders are dropped."""
    runs = [
        _run("daily-driver", "failed", minutes_ago=10,
             notes="Check stderr output for details"),
        _run("vault_synthesizer", "failed", minutes_ago=20,
             notes="Command failed with exit code 1"),
        _run("flush", "failed", minutes_ago=30,
             notes="ConnectTimeout to backend"),  # real failure — keep
    ]
    out = kanban._failures_to_tickets(runs)
    agents = {t["assigned_agent"] for t in out}
    assert agents == {"flush"}


def test_meta_error_pattern_match_is_case_insensitive():
    """Patterns must match regardless of input case."""
    runs = [
        _run("a", "failed", minutes_ago=10, notes="CHECK STDERR OUTPUT FOR DETAILS"),
        _run("b", "failed", minutes_ago=20, notes="command FAILED with EXIT code 1"),
    ]
    assert kanban._failures_to_tickets(runs) == []


def test_eval_meta_error_substantive_details_are_kept():
    """Substantive failure notes are not collateral damage of the filter."""
    runs = [
        _run("agent_x", "failed", minutes_ago=5, notes="ConnectTimeout in 12s"),
    ]
    out = kanban._failures_to_tickets(runs)
    assert len(out) == 1
    assert "ConnectTimeout" in out[0]["details"]


def test_eval_case_with_meta_error_details_is_filtered():
    """Eval-case branch also drops meta-error placeholders.

    Mirrors the agent-runs filter — readers may surface a structured
    `details` field on a failing case, and if that field is itself an
    eval-runner placeholder ("Check stderr output for details") we drop
    the ticket.
    """
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 0, "failed": 2, "skipped": 0, "total_cases": 2,
            "cases": [
                {"id": "case-stderr", "category": "lint", "status": "failed",
                 "details": "Check stderr output for details"},
                {"id": "case-real", "category": "synth", "status": "failed",
                 "details": "concept-edge cycle detected"},
            ],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    headlines = {t["headline"] for t in tickets if t["source"] == "eval"}
    assert "eval failed: case-real" in headlines
    assert not any("case-stderr" in h for h in headlines)


def test_lint_same_path_different_rule_does_not_collapse():
    """Collapse key pins severity|rule|path, not just path.

    Two distinct lint rules firing on the same source file are two distinct
    problems and must surface as two tickets. This test would fail loudly if
    someone simplifies the collapse key to path-only.
    """
    data = {
        "lint_reports": {
            "latest_date": "2026-05-17",
            "issues_total": 2,
            "issues_by_severity": {"HIGH": 1, "MEDIUM": 1},
            "issues": [
                {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                 "path": "notes/foo.md", "context": "missing_target"},
                {"severity": "MEDIUM", "rule": "tier-a-soul-conflict", "tier": "T2",
                 "path": "notes/foo.md", "context": "soul_check"},
            ],
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"]
    assert len(lint) == 2
    rules = {t["_rule"] for t in lint}
    assert rules == {"broken-wikilink", "tier-a-soul-conflict"}
    # Each ticket is a single-edge ticket — no "· N edges" suffix.
    assert all(t["count"] == 1 for t in lint)
    assert all("edges" not in t["headline"] for t in lint)


def test_compose_tickets_redacts_vault_paths_in_lint_details():
    """Public pass: lint ticket details must not contain raw vault paths or
    absolute home-prefixed paths. Both shapes (`vault/...` and the
    `/Users/.../vault/...` absolute form Sean's vault readers actually emit)
    must collapse to ``[redacted]`` before the dict ever materializes.
    """
    data = {
        "lint_reports": {
            "latest_date": "2026-05-17",
            "issues_total": 2,
            "issues_by_severity": {"HIGH": 2},
            "issues": [
                {
                    "severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                    "path": (
                        "/Users/seanwinslow/Code-Brain/code-brain/vault/"
                        "20_projects/prj-job-hunt-2026/README.md"
                    ),
                    "context": "job_feed",
                },
                {
                    "severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                    "path": "vault/20_projects/prj-job-hunt-2026/notes.md",
                    "context": "second_edge",
                },
            ],
        },
    }
    # Public pass — redact_paths=True.
    public = kanban.compose_tickets(data, include_job_feed=False, redact_paths=True)
    for ticket in (t for t in public if t["source"] == "lint"):
        assert "/Users/seanwinslow" not in (ticket["details"] or "")
        assert "prj-job-hunt-2026" not in (ticket["details"] or "")
        assert "vault/20_projects" not in (ticket["details"] or "")
        assert "[redacted]" in (ticket["details"] or "")

    # Private pass — redact_paths default False — paths preserved.
    private = kanban.compose_tickets(data, include_job_feed=True)
    private_lint = [t for t in private if t["source"] == "lint"]
    assert any(
        "prj-job-hunt-2026" in (t["details"] or "") for t in private_lint
    ), "private pass must preserve raw paths for Sean's own use"


def test_compose_tickets_redacts_research_and_manual_titles_when_public():
    """Public pass also redacts research and manual ticket titles/details so a
    `vault/...` substring in either source doesn't leak through."""
    data = {
        "research_queue": {
            "pending": [
                {
                    "title": (
                        "Topic 99 — vault/20_projects/prj-job-hunt-2026/intake.md "
                        "review. Something something."
                    ),
                    "assigned_agent": None,
                },
            ],
            "in_flight": [],
            "done": [],
        },
        "manual_tickets": {
            "todo": [
                {"title": "Audit /Users/seanwinslow/Code-Brain/code-brain/"
                          "vault/20_projects/prj-job-hunt-2026/target-companies.md",
                 "assigned_agent": "Sean"},
            ],
            "in_progress": [], "done": [],
        },
    }
    public = kanban.compose_tickets(data, include_job_feed=False, redact_paths=True)
    for ticket in public:
        for field in ("headline", "title", "details"):
            value = ticket.get(field) or ""
            assert "/Users/seanwinslow" not in value, (ticket, field)
            assert "prj-job-hunt-2026" not in value, (ticket, field)
            assert "vault/" not in value, (ticket, field)


# ---------------------------------------------------------------------------
# Task 2: /kanban hero-plate stats
# ---------------------------------------------------------------------------


def _ticket(source, created_offset_days, today):
    """Build a minimal ticket with created_at = today - offset_days."""
    ts = (today - timedelta(days=created_offset_days)).isoformat()
    return {
        "id": f"{source}-{created_offset_days}",
        "source": source,
        "created_at": ts,
    }


def test_compose_kanban_hero_stats_counts_last_7_days():
    today = datetime(2026, 5, 21, tzinfo=UTC)
    tickets = [
        _ticket("research", 0, today),    # today
        _ticket("research", 3, today),    # 3 days ago — in window
        _ticket("research", 6, today),    # 6 days ago — in window
        _ticket("lint",     7, today),    # 7 days ago — boundary, in window
        _ticket("lint",     8, today),    # 8 days ago — out of window
        _ticket("manual",  30, today),    # way out
    ]
    stats = kanban.compose_kanban_hero_stats(tickets, today=today)
    assert stats["total_7d"] == 4
    assert stats["is_quiet_week"] is False


def test_compose_kanban_hero_stats_buckets_by_source():
    today = datetime(2026, 5, 21, tzinfo=UTC)
    tickets = [
        _ticket("research", 1, today),
        _ticket("research", 2, today),
        _ticket("research", 3, today),
        _ticket("lint",     1, today),
        _ticket("lint",     2, today),
        _ticket("eval",     1, today),
        _ticket("manual",   4, today),
        _ticket("manual",   5, today),
    ]
    stats = kanban.compose_kanban_hero_stats(tickets, today=today)
    assert stats["by_source"] == {
        "research": 3,
        "lint": 2,
        "eval": 1,
        "manual": 2,
        "feed": 0,
    }


def test_compose_kanban_hero_stats_quiet_week_flag():
    today = datetime(2026, 5, 21, tzinfo=UTC)
    stats = kanban.compose_kanban_hero_stats([], today=today)
    assert stats["total_7d"] == 0
    assert stats["is_quiet_week"] is True
    assert stats["by_source"] == {
        "research": 0, "lint": 0, "eval": 0, "manual": 0, "feed": 0,
    }


def test_compose_kanban_hero_stats_uses_now_when_created_at_missing():
    """Tickets without created_at count as 'now' — they don't get dropped."""
    today = datetime(2026, 5, 21, tzinfo=UTC)
    tickets = [
        {"id": "r1", "source": "research"},  # no created_at
        {"id": "m1", "source": "manual", "created_at": None},  # explicit None
        _ticket("lint", 30, today),  # old, excluded
    ]
    stats = kanban.compose_kanban_hero_stats(tickets, today=today)
    assert stats["total_7d"] == 2
    assert stats["by_source"]["research"] == 1
    assert stats["by_source"]["manual"] == 1
    assert stats["by_source"]["lint"] == 0


def test_compose_kanban_hero_stats_feed_tickets_counted_in_private_pass():
    """When a private caller passes feed tickets, they bucket into by_source.feed."""
    today = datetime(2026, 5, 21, tzinfo=UTC)
    tickets = [
        _ticket("feed", 0, today),
        _ticket("feed", 2, today),
        _ticket("research", 1, today),
    ]
    stats = kanban.compose_kanban_hero_stats(tickets, today=today)
    assert stats["by_source"]["feed"] == 2
    assert stats["total_7d"] == 3


def test_compose_kanban_hero_stats_default_today_uses_wall_clock():
    """When today is omitted, the function uses the current UTC moment.

    Smoke check: a ticket created 'now' counts; one created 30d ago does not.
    """
    now = datetime.now(UTC)
    tickets = [
        {"id": "fresh", "source": "research", "created_at": now.isoformat()},
        {"id": "old",   "source": "lint",
         "created_at": (now - timedelta(days=30)).isoformat()},
    ]
    stats = kanban.compose_kanban_hero_stats(tickets)
    assert stats["total_7d"] == 1
    assert stats["by_source"]["research"] == 1
    assert stats["by_source"]["lint"] == 0


def test_compose_kanban_hero_stats_accepts_date_object_for_today():
    """`today` may be passed as a date as well as a datetime — same window."""
    today_d = date(2026, 5, 21)
    today_dt = datetime(2026, 5, 21, tzinfo=UTC)
    tickets = [_ticket("research", 1, today_dt), _ticket("lint", 8, today_dt)]
    stats = kanban.compose_kanban_hero_stats(tickets, today=today_d)
    assert stats["total_7d"] == 1
