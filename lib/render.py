"""Render orchestrators for public + private dashboard passes.

LOCKED DEVIATION from design doc §6a: single lib/render.py with render_public()
and render_private() functions, NOT separate lib/public_render.py + lib/private_render.py.
Sean approved 2026-05-15 — both passes share ~90% of logic, only difference is
one anonymize.public_pass() call before public render.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from lib import activity_timeline, anonymize, kanban, svg_charts

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"


_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# Donut/legend colors aligned with stacked_area bands (Spark palette only).
# Local family = amber (primary signal · local-first), Anthropic = purple, Gemini = alert.
_MODEL_MIX_COLORS = {
    "local-qwen":      svg_charts.AMBER,
    "local-nomic":     svg_charts.AMBER,
    "local-other":     svg_charts.AMBER,
    "local":           svg_charts.AMBER,
    "cloud-anthropic": svg_charts.PURPLE,
    "cloud-gemini":    svg_charts.ALERT,
    "cloud":           svg_charts.ALERT,
}


def _build_charts(agg: dict) -> dict:
    hero_series = [
        {"date": s["date"], "value": s["concepts"]}
        for s in agg["synth_series_60d"]
    ]
    rw = agg["regression_window"]
    annotation = None
    if rw["start"] and rw["nights"] >= 3:
        annotation = {
            "start_date": rw["start"], "end_date": rw["end"],
            "label": f"{rw['nights']}-DAY SILENT REGRESSION",
        }
    hero_svg = svg_charts.line_chart(hero_series, width=1100, height=240, annotation=annotation)

    eval_spark_svg = svg_charts.sparkline(agg["eval_sparkline"], width=80, height=18)

    cost = agg["cost_trend_30d"]
    cost_svg = svg_charts.stacked_area(cost["days"], cost["series"], width=1100, height=180)

    mix_segments = [
        {"label": label, "value": v["count"], "pct": v["pct"],
         "color": _MODEL_MIX_COLORS.get(label, svg_charts.AMBER)}
        for label, v in agg["model_mix"].items()
    ]
    # Center label = dominant share, sub = its label uppercased
    if mix_segments:
        dom = max(mix_segments, key=lambda s: s["value"])
        center_label = f"{dom['pct']}%"
        center_sub = dom["label"].upper()
    else:
        center_label = "—"
        center_sub = "NO RUNS"
    model_mix_svg = svg_charts.donut(
        mix_segments, size=160, stroke=18,
        center_label=center_label, center_sub=center_sub,
    )

    synth_series = [
        {"date": s["date"], "value": s["concepts"]} for s in agg["synth_series_60d"]
    ]
    synth_60d_svg = svg_charts.line_chart(synth_series, width=1100, height=180,
                                          color=svg_charts.AMBER)

    col_spark = agg.get("column_sparklines", {})
    column_sparkline_svgs = {
        "todo": svg_charts.sparkline(
            col_spark.get("todo", []), width=48, height=12, color=svg_charts.ALERT),
        "in_progress": svg_charts.sparkline(
            col_spark.get("in_progress", []), width=48, height=12, color=svg_charts.AMBER),
        "done": svg_charts.sparkline(
            col_spark.get("done", []), width=48, height=12, color=svg_charts.OK),
    }

    kpi_primitive_svgs = _build_kpi_primitives(agg)

    return {
        "hero_svg": hero_svg,
        "eval_sparkline_svg": eval_spark_svg,
        "cost_trend_svg": cost_svg,
        "model_mix_svg": model_mix_svg,
        "model_mix_segments": mix_segments,
        "synth_60d_svg": synth_60d_svg,
        "column_sparkline_svgs": column_sparkline_svgs,
        "kpi_primitive_svgs": kpi_primitive_svgs,
    }


def _build_kpi_primitives(agg: dict) -> dict:
    """Build the 4 inline-SVG primitives for the .kpi-row cards.

    Each card gets a visually distinct primitive matched to its data shape:
    - eval_dots  → 10 dots colored by passed/failed/skipped (eval-pass card)
    - spend_spark → 30-day spend sparkline (fleet-spend card)
    - share_donut → small donut, local share vs cloud (local-only-share card)
    - cap_bar    → fill bar, gemini spend vs $50 cap (governor card)

    All are aria-hidden — they're decorative. The kpi-label + kpi-value text
    remain the semantic content.
    """
    eval_run = agg["eval"]
    passed = int(eval_run.get("passed", 0) or 0)
    failed = int(eval_run.get("failed", 0) or 0)
    skipped = int(eval_run.get("skipped", 0) or 0)
    total = int(eval_run.get("total_cases", 0) or 0)
    eval_dots_svg = svg_charts.kpi_eval_dots(passed, failed, skipped, total)

    # 30-day daily spend series — sum cost_usd per day for the trailing 30d.
    end = agg.get("end_date") or datetime.now(UTC).date()
    daily_totals: list[float] = [0.0] * 30
    for r in agg.get("recent_runs", []):
        d = r["ts"].date() if hasattr(r["ts"], "date") else r["ts"]
        delta = (end - d).days
        if 0 <= delta < 30:
            idx = 29 - delta
            daily_totals[idx] += float(r.get("cost_usd", 0.0) or 0.0)
    # recent_runs is capped to 50 — fall back to scanning a wider window via
    # the cost_trend_30d aggregate if everything came back zero (handles the
    # case where the 50 most-recent runs are all zero-cost local runs).
    if all(v == 0 for v in daily_totals):
        cost = agg.get("cost_trend_30d", {})
        series = cost.get("series", {})
        if series:
            n_days = len(next(iter(series.values())))
            daily_totals = [
                sum(s[i] for s in series.values()) for i in range(n_days)
            ]
    spend_sparkline_svg = svg_charts.kpi_spend_sparkline(daily_totals)

    # Donut for local share (always rendered, but template only uses on the
    # public local-only-share card).
    local_pct = float(agg["kpis"].get("local_only_share_pct", 0) or 0)
    share_donut_svg = svg_charts.kpi_donut(local_pct, size=28, stroke=4)

    # Fill bar for governor card — gemini spend vs $50 monthly cap. The
    # private headroom card reuses this same SVG; the framing difference is
    # in the adjacent label/value text, not in the primitive.
    gemini_total = float(agg.get("gemini", {}).get("total_usd", 0.0) or 0.0)
    cap_bar_svg = svg_charts.kpi_fill_bar(gemini_total, 50.0, color=svg_charts.AMBER)

    return {
        "eval_dots": eval_dots_svg,
        "spend_sparkline": spend_sparkline_svg,
        "share_donut": share_donut_svg,
        "cap_bar": cap_bar_svg,
    }


def _build_alerts(agg: dict, is_private: bool) -> list[dict]:
    if not is_private:
        return []
    alerts: list[dict] = []
    if agg["gemini"]["total_usd"] > 35:
        msg = f"Gemini DR ${agg['gemini']['total_usd']:.2f} / $50 cap (>70% used)"
        alerts.append({"severity": "degraded", "message": msg, "ts": "now"})
    if agg["eval"].get("passed", 10) < 6:
        passed = agg["eval"]["passed"]
        total = agg["eval"]["total_cases"]
        msg = f"Eval pass dropped to {passed}/{total}"
        alerts.append({"severity": "down", "message": msg, "ts": "today"})
    return alerts


def _common_context(agg: dict, *, is_private: bool, snapshot_ts: str | None = None) -> dict:
    ts = snapshot_ts or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    healthy = sum(1 for t in agg["fleet_status"] if t["health"] == "healthy")
    down = sum(1 for t in agg["fleet_status"] if t["health"] == "down")
    degraded = sum(1 for t in agg["fleet_status"] if t["health"] == "degraded")
    total = len(agg["fleet_status"])
    fleet_health_label = f"{healthy}/{total} HEALTHY"
    # Mascot core pulse color tracks fleet state — glanceable status light
    if down:
        mascot_state = "down"
    elif degraded:
        mascot_state = "degraded"
    else:
        mascot_state = "healthy"
    extra_pills: list[str] = []
    if is_private:
        active = agg.get("job_feed", {}).get("active_count", 0)
        if active:
            extra_pills.append(f"HUNT · {active} ACTIVE")
    return {
        "snapshot_ts": ts,
        "is_private": is_private,
        "active_route": "fleet",
        "fleet_health_label": fleet_health_label,
        "mascot_state": mascot_state,
        "extra_pills": extra_pills,
        "kpis": agg["kpis"],
        "fleet_status": agg["fleet_status"],
        "agent_state": agg.get("agent_state", {}),
        "regression_window": agg["regression_window"],
        "clean_streak": agg.get("clean_streak", {
            "nights_clean": 60, "last_regression_end": None,
            "active_incident": False, "incident_nights": 0,
        }),
        "end_date": agg["end_date"],
        "recent_runs": agg["recent_runs"],
        "activity_timeline": agg.get(
            "activity_timeline",
            {"lanes": [], "axis_labels": [], "total_runs": 0, "window_hours": 24},
        ),
        "eval_cases": agg["eval"].get("cases", []),
        # Plain-English definitions for insider terms (T1, schema-integrity,
        # etc.) used to attach `title=` tooltips in templates. Centralized in
        # lib/activity_timeline.py — see Task 4.3.
        "term_definitions": activity_timeline.TERM_DEFINITIONS,
        "gemini": agg["gemini"],
        "council": agg["council"],
        "job_feed": agg["job_feed"],
        # §4d live-wire: pass target_companies + warm_intros through
        "target_companies": agg.get("target_companies", {}),
        "warm_intros": agg.get("warm_intros", {}),
        "alerts": _build_alerts(agg, is_private),
        **_build_charts(agg),
    }


def render_public(agg: dict, tickets: list[dict], out_dir: Path) -> None:
    """Render public-safe fleet + kanban HTML + data sidecar to out_dir.

    Calls anonymize.public_pass(agg) first — zeros job_feed, target_companies,
    warm_intros; redacts vault paths in notes + titles.
    """
    pub_agg = anonymize.public_pass(agg)
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = _common_context(pub_agg, is_private=False)

    fleet_html = _ENV.get_template("fleet.html").render(
        page_title="Agent Fleet Observability", **ctx)
    (out_dir / "index.html").write_text(fleet_html)

    ctx_k = {
        **ctx,
        "active_route": "kanban",
        "tickets": tickets,
        "kanban_hero": kanban.compose_kanban_hero_stats(tickets),
    }
    kb_html = _ENV.get_template("kanban.html").render(
        page_title="Agent Fleet · Kanban", **ctx_k)
    (out_dir / "kanban.html").write_text(kb_html)

    (out_dir / "data.json").write_text(json.dumps({
        "tickets": tickets,
        "snapshot_ts": ctx["snapshot_ts"],
    }, default=str, indent=2))


def render_private(agg: dict, tickets: list[dict], out_dir: Path) -> None:
    """Render full private fleet + kanban HTML + data sidecar to out_dir.

    No anonymization. Job-hunt + warm-intro + lint detail rendered as-is.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = _common_context(agg, is_private=True)

    fleet_html = _ENV.get_template("fleet.html").render(
        page_title="Agent Fleet Observability · Private", **ctx)
    (out_dir / "index.html").write_text(fleet_html)

    ctx_k = {
        **ctx,
        "active_route": "kanban",
        "tickets": tickets,
        "kanban_hero": kanban.compose_kanban_hero_stats(tickets),
    }
    kb_html = _ENV.get_template("kanban.html").render(
        page_title="Agent Fleet · Kanban · Private", **ctx_k)
    (out_dir / "kanban.html").write_text(kb_html)

    (out_dir / "data.json").write_text(json.dumps({
        "tickets": tickets,
        "snapshot_ts": ctx["snapshot_ts"],
    }, default=str, indent=2))
