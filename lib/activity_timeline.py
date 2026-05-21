"""24-Hour Activity Timeline composer.

Replaces the flat "Recent Runs" table position. Each agent gets one lane.
Each run becomes a dot on the lane at its firing time. Dot color encodes
status; dot title carries the human-readable hover detail.

This is architecturally honest: the system's agents are independent launchd
cron jobs, so this is a parallel-lanes-on-shared-time view, not a fake
nested-span waterfall (per docs/2026-05-15-agent-fleet-dashboard-design.md
§10 anti-patterns).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

_SUCCESS_STATUSES = {"success", "ok", "completed", "passed"}
_FAILURE_STATUSES = {"error", "failed", "capped", "timeout"}
_GUARDED_STATUSES = {"recursion-guard", "skipped"}

# Plain-English definitions for insider terms that surface on the public
# dashboard. Keys are matched exactly against event statuses, eval categories,
# and severity tiers; values are appended to native browser `title=` tooltips
# so a non-developer reader can decode the jargon without leaving the page.
# IMPORTANT: keep this list em-dash-free; the project copy guide bars `—` from
# rendered text and we grep for it on every build.
TERM_DEFINITIONS: dict[str, str] = {
    "recursion-guard": "Safety mechanism: stops an agent from triggering itself in a loop.",
    "schema-integrity": "Verification that data shape matches the declared schema.",
    "T1": "Tier 1: highest priority, direct customer or deadline work.",
    "T2": "Tier 2: in-flight projects, no immediate deadline.",
    "guarded": "Run hit a safety guard (cost cap, rate limit, recursion check).",
}


def term_definition(term: str | None) -> str | None:
    """Return the long-form definition for ``term`` or ``None`` when unknown.

    Callers that compose `title=` strings can append `" ({definition})"` when
    a definition is present. Returning ``None`` (not an empty string) makes
    "unknown term" trivially distinguishable from "known term with empty
    definition" in templates and tests.

    The function returns the raw definition string — callers are responsible
    for wrapping it into a `title=` attribute or any other presentation. The
    name reflects what it returns, not how a single caller happens to use it.
    """
    if not term:
        return None
    return TERM_DEFINITIONS.get(term)


def _classify(status: str) -> str:
    s = (status or "").lower()
    if s in _SUCCESS_STATUSES:
        return "success"
    if s in _FAILURE_STATUSES:
        return "error"
    if s in _GUARDED_STATUSES:
        return "guarded"
    return "other"


def _format_duration(duration_ms: int | None) -> str:
    if not duration_ms:
        return ""
    seconds = duration_ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes / 60.0:.1f}h"


def compose_timeline(
    runs: list[dict],
    agent_names: list[str],
    *,
    now: datetime | None = None,
    window_hours: int = 24,
) -> dict:
    """Build a per-agent lane of dots for the last `window_hours`.

    Returns:
        {
          "window_hours": 24,
          "axis_labels": ["00:00", "06:00", "12:00", "18:00", "24:00"],
          "lanes": [
            {
              "agent": "vault_indexer",
              "display_name": "vault_indexer",
              "run_count": 4,    # raw event cardinality (collapses contribute >1)
              "dots": [
                {"left_pct": 12.5, "status_class": "success",
                 "title": "vault_indexer · 03:00 · success · 11.4s"},
                ...
              ],
            },
            ...
          ],
        }

    If a lane has zero runs in the window, it still renders (proves the agent
    exists in the fleet but was silent — honest empty state).
    """
    now = now or datetime.now(UTC)
    window_start = now - timedelta(hours=window_hours)
    window_seconds = window_hours * 3600.0

    # Bucket runs by agent name (normalize dashes/underscores so vault-indexer == vault_indexer)
    def _norm(name: str) -> str:
        return (name or "").lower().replace("-", "_").strip()

    by_agent: dict[str, list[dict]] = {_norm(a): [] for a in agent_names}
    for run in runs:
        ts = run.get("ts")
        if ts is None:
            continue
        # Tolerate naive timestamps by assuming UTC
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < window_start or ts > now:
            continue
        key = _norm(run.get("agent", ""))
        if key in by_agent:
            by_agent[key].append({**run, "ts": ts})

    # 5 axis labels evenly spaced across the window
    axis_labels = []
    for i in range(5):
        t = window_start + timedelta(hours=window_hours * i / 4)
        axis_labels.append(t.strftime("%H:%M"))

    lanes: list[dict] = []
    for agent in agent_names:
        key = _norm(agent)
        agent_runs = by_agent.get(key, [])
        # Collapse co-located events for the same agent that share the
        # minute-resolution timestamp AND status: six recursion-guards in the
        # same minute should render as a single dot whose title ends "×6"
        # instead of overplotting six identical dots at the same left%.
        grouped: dict[tuple[str, str], dict] = {}
        order: list[tuple[str, str]] = []
        for run in agent_runs:
            ts_minute = run["ts"].strftime("%H:%M")
            status = run["status"]
            group_key = (ts_minute, status)
            entry = grouped.get(group_key)
            if entry is None:
                entry = {"runs": [run], "ts_minute": ts_minute}
                grouped[group_key] = entry
                order.append(group_key)
            else:
                entry["runs"].append(run)
        dots: list[dict] = []
        for group_key in order:
            entry = grouped[group_key]
            # Use the earliest timestamp in the group for left_pct positioning.
            group_runs = sorted(entry["runs"], key=lambda r: r["ts"])
            first = group_runs[0]
            count = len(group_runs)
            elapsed_s = (first["ts"] - window_start).total_seconds()
            left_pct = max(0.0, min(100.0, 100.0 * elapsed_s / window_seconds))
            status_class = _classify(first["status"])
            dur = _format_duration(first.get("duration_ms"))
            title_bits = [agent, entry["ts_minute"], first["status"]]
            if dur:
                title_bits.append(dur)
            if first.get("cost_usd") and first["cost_usd"] > 0:
                title_bits.append(f"${first['cost_usd']:.4f}")
            title = " · ".join(title_bits)
            if count > 1:
                title = f"{title} ×{count}"
            # Append plain-English definition when the run's status (e.g.
            # `recursion-guard`) or status class (e.g. `guarded`) is a known
            # insider term. Status takes precedence so the more-specific term
            # surfaces when both match.
            definition = term_definition(first["status"]) or term_definition(status_class)
            if definition:
                title = f"{title} ({definition})"
            dots.append({
                "left_pct": round(left_pct, 2),
                "status_class": status_class,
                "title": title,
                "count": count,
            })
        lanes.append({
            "agent": key,
            "display_name": agent,
            # run_count is raw event cardinality across all collapses on this
            # lane — what the eyebrow and credibility surface need. The dot
            # list length is the visual count, which can be smaller.
            "run_count": sum(d["count"] for d in dots),
            "dots": dots,
        })

    return {
        "window_hours": window_hours,
        "axis_labels": axis_labels,
        "lanes": lanes,
        # Total runs is the raw event count — must sum lane run_count, not
        # dot count, otherwise collapses under-report the fleet's noise.
        "total_runs": sum(lane["run_count"] for lane in lanes),
    }
