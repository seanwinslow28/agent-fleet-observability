"""Tests for the 24-hour activity timeline composer."""
from datetime import UTC, datetime, timedelta

from lib.activity_timeline import TERM_DEFINITIONS, compose_timeline, term_tooltip


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
    assert all(lane["run_count"] == 0 for lane in out["lanes"])
    assert len(out["axis_labels"]) == 5


def test_run_within_window_appears_as_dot():
    runs = [_run("vault_indexer", hours_ago=3)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    lane = out["lanes"][0]
    assert lane["run_count"] == 1
    dot = lane["dots"][0]
    # 3h ago in a 24h window starting at now-24h = position (24-3)/24 = 87.5%
    assert 86.0 <= dot["left_pct"] <= 89.0
    assert dot["status_class"] == "success"
    assert "vault_indexer" in dot["title"]


def test_run_outside_window_is_dropped():
    runs = [_run("vault_indexer", hours_ago=48)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    assert out["lanes"][0]["run_count"] == 0


def test_dash_underscore_normalization():
    """CSV has `vault-indexer`; agent_names has `vault_indexer`. They must match."""
    runs = [_run("vault-indexer", hours_ago=2)]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    assert out["lanes"][0]["run_count"] == 1


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
    assert out["lanes"][0]["run_count"] == 1


def test_colocated_events_collapse_to_one_dot_with_count():
    """Six recursion-guards in the same minute → one dot, title ends "×6"."""
    base = _NOW - timedelta(hours=6)  # ts_minute will be identical
    runs = [
        {
            "ts": base + timedelta(seconds=i),  # same minute, different seconds
            "agent": "flush",
            "status": "recursion-guard",
            "duration_ms": None,
            "cost_usd": 0.0,
            "notes": "",
        }
        for i in range(6)
    ]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    lane = out["lanes"][0]
    assert len(lane["dots"]) == 1
    dot = lane["dots"][0]
    assert dot["count"] == 6
    # Title carries the ×6 count; a trailing definition parenthetical may
    # follow (see term_tooltip), so assert presence, not the literal tail.
    assert "×6" in dot["title"]
    # The lane's reported run_count reflects raw event cardinality, not dots.
    assert lane["run_count"] == 6


def test_total_runs_counts_raw_events_not_collapsed_dots():
    """Regression: total_runs must sum raw events, not dot count. Otherwise
    the eyebrow at templates/partials/activity_timeline.html under-reports
    fleet activity after collapse — the exact "headline contradicts data"
    credibility bug Task 1 set out to fix.
    """
    base = _NOW - timedelta(hours=4)
    runs = [
        {"ts": base + timedelta(seconds=i), "agent": "flush",
         "status": "recursion-guard", "duration_ms": None,
         "cost_usd": 0.0, "notes": ""}
        for i in range(6)
    ]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    # One visual dot, but six runs in the lane and in the fleet total.
    assert len(out["lanes"][0]["dots"]) == 1
    assert out["lanes"][0]["run_count"] == 6
    assert out["total_runs"] == 6


def test_single_event_has_no_count_suffix():
    runs = [_run("flush", hours_ago=2, status="recursion-guard")]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    dot = out["lanes"][0]["dots"][0]
    assert dot["count"] == 1
    assert "×" not in dot["title"]


def test_term_tooltip_returns_definition_for_known_term():
    assert term_tooltip("recursion-guard") == TERM_DEFINITIONS["recursion-guard"]
    assert term_tooltip("schema-integrity") == TERM_DEFINITIONS["schema-integrity"]
    assert term_tooltip("T1") == TERM_DEFINITIONS["T1"]
    assert term_tooltip("T2") == TERM_DEFINITIONS["T2"]
    assert term_tooltip("guarded") == TERM_DEFINITIONS["guarded"]


def test_term_tooltip_returns_none_for_unknown_term():
    assert term_tooltip("success") is None
    assert term_tooltip(None) is None
    assert term_tooltip("") is None


def test_term_definitions_are_em_dash_free():
    """Project copy guide bars `—` from rendered text. The render pass leaks
    these strings into title= attributes, so they must stay clean too."""
    for term, definition in TERM_DEFINITIONS.items():
        assert "—" not in definition, f"{term} definition contains em-dash: {definition!r}"


def test_recursion_guard_event_title_includes_definition():
    """The 24h timeline composer must append the long-form definition to the
    dot's title when the event's status is a known insider term."""
    runs = [_run("flush", hours_ago=2, status="recursion-guard")]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    title = out["lanes"][0]["dots"][0]["title"]
    assert "recursion-guard" in title
    assert TERM_DEFINITIONS["recursion-guard"] in title


def test_collapsed_recursion_guard_dot_keeps_definition_after_count():
    """When multiple recursion-guards collapse into one dot (×N suffix), the
    definition still appears so the tooltip stays self-explanatory."""
    base = _NOW - timedelta(hours=5)
    runs = [
        {"ts": base + timedelta(seconds=i), "agent": "flush",
         "status": "recursion-guard", "duration_ms": None,
         "cost_usd": 0.0, "notes": ""}
        for i in range(3)
    ]
    out = compose_timeline(runs, ["flush"], now=_NOW)
    dot = out["lanes"][0]["dots"][0]
    assert "×3" in dot["title"]
    assert TERM_DEFINITIONS["recursion-guard"] in dot["title"]


def test_unknown_status_title_has_no_definition_suffix():
    """A plain `success` run carries no parenthetical definition tail."""
    runs = [_run("vault_indexer", hours_ago=2, status="success")]
    out = compose_timeline(runs, ["vault_indexer"], now=_NOW)
    title = out["lanes"][0]["dots"][0]["title"]
    # No trailing parenthetical from term_tooltip — the only `(`/`)` we'd see
    # would be from a definition append.
    assert "(" not in title
    assert ")" not in title


def test_different_statuses_at_same_minute_do_not_collapse():
    """Collapse keys on (minute, status); a success and an error in the same
    minute stay as two distinct dots."""
    base = _NOW - timedelta(hours=3)
    runs = [
        {"ts": base, "agent": "a", "status": "success",
         "duration_ms": 200, "cost_usd": 0.0, "notes": ""},
        {"ts": base + timedelta(seconds=10), "agent": "a", "status": "error",
         "duration_ms": 200, "cost_usd": 0.0, "notes": ""},
    ]
    out = compose_timeline(runs, ["a"], now=_NOW)
    assert len(out["lanes"][0]["dots"]) == 2
