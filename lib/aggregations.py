"""Telemetry aggregation for the Agent Fleet Observability Dashboard.

All public functions consume plain dicts from lib/readers and return plain dicts.
No domain models. Aggregation results feed Jinja2 templates via build.py.

Date-window assumption: compute_fleet_status uses a 7-day window from now()
and compute_kpis uses a 30-day window from now(). Fixtures have dates from
2026-05-12 and 2026-05-13; tests pass when run within 7 days of 2026-05-16.
Task 10 will introduce an `end` parameter for date injection in the time-series
functions, establishing the pattern. Task 11 will propagate it to compute_all.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _is_local(model: str | None) -> bool:
    """Return True when the run used a local (zero-cost) model."""
    if not model:
        return True  # no model field = local task (rsync, sqlite, etc.)
    return any(tok in model.lower() for tok in ("qwen", "nomic", "gemma", "kokoro", "ollama"))


def compute_fleet_status(runs: list[dict], agent_names: list[str]) -> list[dict]:
    """One tile per agent. Health derived from the last 7 days of runs.

    Health values:
        "healthy"  — all runs ok (or skipped only)
        "degraded" — mix of ok and error/failed/capped
        "down"     — only errors in window, no ok
        "unknown"  — no runs in window
    """
    cutoff = datetime.now(UTC) - timedelta(days=7)
    by_agent: dict[str, list[dict]] = {n: [] for n in agent_names}
    for r in runs:
        if r["agent"] in by_agent and r["ts"] >= cutoff:
            by_agent[r["agent"]].append(r)
    tiles: list[dict] = []
    for name in agent_names:
        agent_runs = sorted(by_agent[name], key=lambda r: r["ts"], reverse=True)
        if not agent_runs:
            tiles.append({"agent": name, "health": "unknown", "last_run": None, "last_cost": 0.0})
            continue
        statuses = [r["status"] for r in agent_runs]
        has_error = any(s in ("error", "failed", "capped") for s in statuses)
        has_ok = any(s == "ok" for s in statuses)
        if has_error and has_ok:
            health = "degraded"
        elif has_error:
            health = "down"
        else:
            health = "healthy"
        last = agent_runs[0]
        tiles.append({
            "agent": name,
            "health": health,
            "last_run": last["ts"],
            "last_cost": last["cost_usd"],
            "last_status": last["status"],
            "last_notes": last["notes"],
            "run_count_7d": len(agent_runs),
        })
    return tiles


def compute_kpis(
    runs: list[dict],
    eval_run: dict,
    gemini_total: float,
    council_total: float,
) -> dict:
    """Top-level KPI block for the dashboard header row.

    Args:
        runs:          full run history from read_run_history
        eval_run:      parsed eval result from read_eval_last_run
        gemini_total:  cumulative Gemini spend this month in USD
        council_total: cumulative LLM Council spend this month in USD

    Returns a flat dict with 10 keys consumed by the KPI row template.
    """
    cutoff = datetime.now(UTC) - timedelta(days=30)
    last_30 = [r for r in runs if r["ts"] >= cutoff]
    spend_30d = sum(r["cost_usd"] for r in last_30)
    local_runs = [r for r in last_30 if _is_local(r.get("model")) and r["cost_usd"] == 0.0]
    pct_local = (len(local_runs) / len(last_30) * 100) if last_30 else 100.0
    return {
        "eval_pass": f"{eval_run['passed']} / {eval_run['total_cases']}",
        "eval_pass_count": eval_run["passed"],
        "eval_total": eval_run["total_cases"],
        "fleet_spend_30d_usd": round(spend_30d, 4),
        "fleet_spend_30d_label": f"${spend_30d:.2f}",
        "run_count_30d": len(last_30),
        "local_only_share_pct": round(pct_local, 1),
        "spend_governors": "$50 / mo",
        "monthly_headroom_usd": round(50.0 - gemini_total, 2),
        "council_month_total": round(council_total, 2),
    }
