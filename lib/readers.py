"""Data source loaders for the Agent Fleet Observability Dashboard.

All readers return plain dicts / lists of dicts — no domain models. Aggregation
happens downstream in lib/aggregations.py. Empty inputs return empty containers,
not None, so callers can blindly iterate.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import yaml


def _parse_ts(date_str: str, time_str: str) -> datetime:
    iso = f"{date_str}T{time_str}"
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


def _to_float(val: str) -> float:
    return float(val) if val else 0.0


def _to_int_or_none(val: str) -> int | None:
    return int(val) if val else None


def read_run_history(path: Path) -> list[dict]:
    """Load agent-run-history.csv → list of normalized run dicts.

    Schema: date, time, agent, mode, status, cost_usd, duration_ms, turns, notes.
    """
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            rows.append({
                "ts": _parse_ts(raw["date"], raw["time"]),
                "agent": raw["agent"],
                "mode": raw["mode"] or None,
                "status": raw["status"],
                "cost_usd": _to_float(raw["cost_usd"]),
                "duration_ms": _to_int_or_none(raw["duration_ms"]),
                "turns": _to_int_or_none(raw["turns"]),
                "notes": raw["notes"] or "",
            })
    return rows


_SYNTH_NAME_RE = re.compile(r"(?:sample-)?synth-manifest-(\d{4})-(\d{2})-(\d{2})\.json$")


def read_synth_manifests(dir_path: Path) -> list[dict]:
    """Load all synth-manifest-YYYY-MM-DD.json files in `dir_path`.

    Returns list sorted ascending by date. Each record adds a parsed `date`
    field on top of the raw manifest JSON.
    """
    if not dir_path.exists():
        return []
    records: list[dict] = []
    for path in sorted(dir_path.glob("*synth-manifest-*.json")):
        m = _SYNTH_NAME_RE.search(path.name)
        if not m:
            continue
        yr, mo, dy = (int(g) for g in m.groups())
        raw = json.loads(path.read_text())
        raw["date"] = date(yr, mo, dy)
        records.append(raw)
    return sorted(records, key=lambda r: r["date"])


def read_gemini_spend(path: Path) -> dict:
    """Aggregate a single gemini-spend-YYYY-MM.json (array of interactions)."""
    if not path.exists():
        return {"total_usd": 0.0, "run_count": 0, "tiers": {}}
    items = json.loads(path.read_text())
    total = sum(it.get("cost_usd", 0.0) or 0.0 for it in items)
    tiers: dict[str, int] = {}
    for it in items:
        tier = it.get("tier", "unknown")
        tiers[tier] = tiers.get(tier, 0) + 1
    return {
        "total_usd": round(total, 2),
        "run_count": len(items),
        "tiers": tiers,
    }


def read_council_spend(dir_path: Path) -> dict:
    """Aggregate all council-spend-YYYY-MM-DD.json files in dir_path for the month."""
    if not dir_path.exists():
        return {"month_total_usd": 0.0, "day_count": 0, "days": []}
    days: list[dict] = []
    total = 0.0
    for path in sorted(dir_path.glob("council-spend-*.json")):
        raw = json.loads(path.read_text())
        day_total = raw.get("day_total_usd", 0.0) or 0.0
        days.append({"date": raw.get("date"), "total_usd": day_total})
        total += day_total
    return {
        "month_total_usd": round(total, 2),
        "day_count": len(days),
        "days": days,
    }


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def read_eval_last_run(path: Path) -> dict:
    """Parse evals/vault-synthesizer/last-run.md frontmatter."""
    empty = {"passed": 0, "failed": 0, "skipped": 0, "total_cases": 0, "cases": []}
    if not path.exists():
        return empty
    fm = _parse_frontmatter(path.read_text())
    return {
        "passed": int(fm.get("passed", 0)),
        "failed": int(fm.get("failed", 0)),
        "skipped": int(fm.get("skipped", 0)),
        "total_cases": int(fm.get("total_cases", 0)),
        "cases": list(fm.get("cases", []) or []),
        "run_id": fm.get("run_id"),
    }


def read_job_feed_db(path: Path) -> dict:
    """Read aggregate stats from vault/.job-feed.db.

    Returns funnel by status, top-N fit-score rows, and timestamps.
    PRIVATE-ONLY: callers must skip this on public render pass.
    """
    empty = {"total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0}
    if not path.exists():
        return empty
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM job_postings")
        total = cur.fetchone()[0]
        cur = conn.execute("SELECT status, COUNT(*) FROM job_postings GROUP BY status")
        by_status = {row[0] or "new": row[1] for row in cur.fetchall()}
        cur = conn.execute(
            """SELECT company, title, fit_score, status, first_seen_at
               FROM job_postings
               WHERE rules_passed = 1 AND fit_score IS NOT NULL
                 AND status NOT IN ('rejected', 'archived')
               ORDER BY fit_score DESC
               LIMIT 10"""
        )
        top_fit = [
            {
                "company": r[0],
                "title": r[1],
                "fit_score": r[2],
                "status": r[3],
                "first_seen_at": r[4],
            }
            for r in cur.fetchall()
        ]
        cur = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE status NOT IN ('rejected', 'archived')"
        )
        active = cur.fetchone()[0]
    finally:
        conn.close()
    return {
        "total_postings": total,
        "by_status": by_status,
        "top_fit": top_fit,
        "active_count": active,
    }


_LINT_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-lint-report\.md$")


def read_lint_reports(dir_path: Path) -> dict:
    """Find the most recent lint report; return its summary."""
    if not dir_path.exists():
        return {"latest_date": None, "issues_total": 0, "issues_by_severity": {}}
    dated: list[tuple[str, Path]] = []
    for p in dir_path.glob("*-lint-report.md"):
        m = _LINT_NAME_RE.search(p.name)
        if m:
            dated.append((m.group(1), p))
    if not dated:
        return {"latest_date": None, "issues_total": 0, "issues_by_severity": {}}
    dated.sort(reverse=True)
    latest_date, latest_path = dated[0]
    fm = _parse_frontmatter(latest_path.read_text())
    return {
        "latest_date": latest_date,
        "issues_total": int(fm.get("issues_total", 0)),
        "issues_by_severity": dict(fm.get("issues_by_severity", {}) or {}),
        "raw_body": latest_path.read_text(),
    }
