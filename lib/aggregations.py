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

from collections import Counter
from datetime import UTC, datetime, timedelta
from datetime import date as _date


def _is_local(model: str | None) -> bool:
    """Return True when the run used a local (zero-cost) model."""
    if not model:
        return True  # no model field = local task (rsync, sqlite, etc.)
    return any(tok in model.lower() for tok in ("qwen", "nomic", "gemma", "kokoro", "ollama"))


def _norm_agent(name: str) -> str:
    return (name or "").lower().replace("-", "_").strip()


def compute_fleet_status(runs: list[dict], agent_names: list[str]) -> list[dict]:
    """One tile per agent. Health derived from the last 7 days of runs.

    Health values:
        "healthy"  — all runs ok (or skipped only)
        "degraded" — mix of ok and error/failed/capped
        "down"     — only errors in window, no ok
        "unknown"  — no runs in window

    Agent names normalized dash↔underscore so the CSV's `vault-indexer` matches
    the canonical `vault_indexer` in AGENT_NAMES.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=7)
    by_agent: dict[str, list[dict]] = {_norm_agent(n): [] for n in agent_names}
    for r in runs:
        key = _norm_agent(r["agent"])
        if key in by_agent and r["ts"] >= cutoff:
            by_agent[key].append(r)

    _ok_statuses = {"ok", "success", "completed", "passed"}
    _err_statuses = {"error", "failed", "capped", "timeout"}

    tiles: list[dict] = []
    for name in agent_names:
        key = _norm_agent(name)
        agent_runs = sorted(by_agent[key], key=lambda r: r["ts"], reverse=True)

        # 7-day sparkline — run count per day, oldest → newest (left-to-right matchstick)
        spark: list[dict] = []
        for d in range(7):
            day_start = (now - timedelta(days=6 - d)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_runs = [r for r in agent_runs if day_start <= r["ts"] < day_end]
            day_statuses = [r["status"].lower() for r in day_runs]
            if not day_runs:
                cls = "idle"
            elif any(s in _err_statuses for s in day_statuses):
                cls = "down" if not any(s in _ok_statuses for s in day_statuses) else "degraded"
            else:
                cls = "healthy"
            spark.append({"count": len(day_runs), "cls": cls})

        if not agent_runs:
            tiles.append({
                "agent": name,
                "health": "unknown",
                "last_run": None,
                "last_cost": 0.0,
                "last_status": None,
                "last_notes": "",
                "run_count_7d": 0,
                "sparkline_7d": spark,
            })
            continue
        statuses = [r["status"].lower() for r in agent_runs]
        has_error = any(s in _err_statuses for s in statuses)
        has_ok = any(s in _ok_statuses for s in statuses)
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
            "sparkline_7d": spark,
        })
    return tiles


def compute_agent_state(fleet_status: list[dict]) -> dict[str, str]:
    """Adapt fleet_status (list of per-agent tiles) into a dict keyed by
    normalized agent name. Used by the kanban template to render the
    agent-state dot on cards with the same source of truth as /fleet.
    """
    return {_norm_agent(t["agent"]): t["health"] for t in fleet_status}


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


def compute_synth_series(manifests: list[dict], days: int, end: _date) -> list[dict]:
    """Build a `days`-long series ending on `end`. Missing dates → concepts=None."""
    by_date = {m["date"]: m for m in manifests}
    out: list[dict] = []
    for i in range(days - 1, -1, -1):
        d = end - timedelta(days=i)
        m = by_date.get(d)
        out.append({
            "date": d,
            "concepts": m["concepts_written"] if m else None,
            "connections": m.get("connections_written") if m else None,
        })
    return out


def compute_regression_window(manifests: list[dict]) -> dict:
    """Find the longest run of consecutive zero-concept nights."""
    if not manifests:
        return {"start": None, "end": None, "nights": 0}
    sorted_m = sorted(manifests, key=lambda m: m["date"])
    best = {"start": None, "end": None, "nights": 0}
    run_start = None
    run_len = 0
    for m in sorted_m:
        if m.get("concepts_written", 0) == 0:
            run_start = run_start or m["date"]
            run_len += 1
            if run_len > best["nights"]:
                best = {"start": run_start, "end": m["date"], "nights": run_len}
        else:
            run_start = None
            run_len = 0
    return best


def compute_eval_sparkline(eval_run: dict, days: int = 14) -> list[int]:
    """v1: no historical eval store, so emit a flat-tail sparkline ending at today.

    Day 2 Task 11 follow-up: when we wire an evals/vault-synthesizer/history.jsonl,
    swap this to read real history.
    """
    today_pass = eval_run.get("passed", 0)
    return [today_pass] * days


def compute_cost_trend(runs: list[dict], days: int, end: _date) -> dict:
    """Per-day per-agent cost totals for stacked area rendering."""
    by_date_agent: dict[tuple[_date, str], float] = {}
    agents: set[str] = set()
    for r in runs:
        d = r["ts"].date()
        if d > end or d < end - timedelta(days=days - 1):
            continue
        a = r["agent"]
        agents.add(a)
        key = (d, a)
        by_date_agent[key] = by_date_agent.get(key, 0.0) + r["cost_usd"]
    ordered_agents = sorted(agents)
    day_axis = [end - timedelta(days=i) for i in range(days - 1, -1, -1)]
    series: dict[str, list[float]] = {a: [0.0] * days for a in ordered_agents}
    for (d, a), v in by_date_agent.items():
        idx = day_axis.index(d)
        series[a][idx] = round(v, 4)
    return {"days": [d.isoformat() for d in day_axis], "agents": ordered_agents, "series": series}


def compute_model_mix(runs: list[dict]) -> dict[str, dict]:
    """Bucket runs by local-vs-cloud + family. Returns {label: {count, pct}}."""
    buckets: Counter = Counter()
    for r in runs:
        model = (r.get("model") or "").lower()
        if "qwen" in model or "ollama" in model:
            label = "local-qwen"
        elif "nomic" in model:
            label = "local-nomic"
        elif "gemma" in model or "kokoro" in model:
            label = "local-other"
        elif "sonnet" in model or "opus" in model or "haiku" in model:
            label = "cloud-anthropic"
        elif "gemini" in model:
            label = "cloud-gemini"
        elif r["cost_usd"] == 0.0:
            label = "local"
        else:
            label = "cloud"
        buckets[label] += 1
    total = sum(buckets.values()) or 1
    return {label: {"count": n, "pct": round(n / total * 100, 1)} for label, n in buckets.items()}


def compute_recent_runs(runs: list[dict], n: int = 50) -> list[dict]:
    return sorted(runs, key=lambda r: r["ts"], reverse=True)[:n]


def compute_all(data: dict, *, end: _date | None = None) -> dict:
    """Single entry point: build every aggregate the renderers need."""
    # Local import — keeps aggregations importable standalone in tests
    from lib import activity_timeline

    end = end or datetime.now(UTC).date()
    runs = data["agent_runs"]
    eval_run = data["eval_last_run"]
    gemini = data["gemini_spend"]
    council = data["council_spend"]
    manifests = data["synth_manifests"]
    agent_names = data["agent_names"]
    fleet_status = compute_fleet_status(runs, agent_names)
    return {
        "fleet_status": fleet_status,
        "agent_state": compute_agent_state(fleet_status),
        "activity_timeline": activity_timeline.compose_timeline(runs, agent_names),
        "kpis": compute_kpis(runs, eval_run, gemini["total_usd"], council["month_total_usd"]),
        "synth_series_60d": compute_synth_series(manifests, days=60, end=end),
        "synth_series_14d": compute_synth_series(manifests, days=14, end=end),
        "regression_window": compute_regression_window(manifests),
        "eval_sparkline": compute_eval_sparkline(eval_run, days=14),
        "cost_trend_30d": compute_cost_trend(runs, days=30, end=end),
        "model_mix": compute_model_mix(
            [r for r in runs if r["ts"].date() >= end - timedelta(days=30)]
        ),
        "recent_runs": compute_recent_runs(runs, n=50),
        "gemini": gemini,
        "council": council,
        "eval": eval_run,
        "lint": data.get("lint_reports", {}),
        "job_feed": data.get("job_feed_db", {}),
        "job_feed_manifests": data.get("job_feed_manifests", {}),
        "research_queue": data.get("research_queue", {}),
        "manual_tickets": data.get("manual_tickets", {}),
        # §4d live-wire additions per Sean's 2026-05-16 decision:
        "target_companies": data.get(
            "target_companies",
            {"tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0},
        ),
        "warm_intros": data.get(
            "warm_intros",
            {"active": [], "prospecting": [], "second_degree": [], "total": 0},
        ),
        "end_date": end,
    }
