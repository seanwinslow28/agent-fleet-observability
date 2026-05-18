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
              "dot_count": 4,
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
        dots: list[dict] = []
        for run in agent_runs:
            elapsed_s = (run["ts"] - window_start).total_seconds()
            left_pct = max(0.0, min(100.0, 100.0 * elapsed_s / window_seconds))
            status_class = _classify(run["status"])
            dur = _format_duration(run.get("duration_ms"))
            ts_label = run["ts"].strftime("%H:%M")
            title_bits = [agent, ts_label, run["status"]]
            if dur:
                title_bits.append(dur)
            if run.get("cost_usd") and run["cost_usd"] > 0:
                title_bits.append(f"${run['cost_usd']:.4f}")
            dots.append({
                "left_pct": round(left_pct, 2),
                "status_class": status_class,
                "title": " · ".join(title_bits),
            })
        lanes.append({
            "agent": key,
            "display_name": agent,
            "dot_count": len(dots),
            "dots": dots,
        })

    return {
        "window_hours": window_hours,
        "axis_labels": axis_labels,
        "lanes": lanes,
        "total_runs": sum(len(lane["dots"]) for lane in lanes),
    }
