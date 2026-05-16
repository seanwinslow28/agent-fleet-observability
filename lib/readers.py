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
_BULLET_RE = re.compile(r"^- \[[ x]\]\s*(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
_PLAIN_BULLET_RE = re.compile(r"^-\s+(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")


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


def _parse_section_items(lines: list[str], regex: re.Pattern) -> list[dict]:
    items: list[dict] = []
    for line in lines:
        m = regex.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip().strip("*_~")
        title = re.sub(r"\*\*(.+?)\*\*", r"\1", title)
        agent = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        items.append({"title": title, "assigned_agent": agent})
    return items


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "_pre"
    sections[current] = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower().replace(" ", "_")
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def read_research_queue(path: Path) -> dict:
    """Parse research-queue.md into pending / in_flight / done item lists."""
    if not path.exists():
        return {"pending": [], "in_flight": [], "done": []}
    sections = _split_sections(path.read_text())
    return {
        "pending": _parse_section_items(sections.get("pending", []), _BULLET_RE),
        "in_flight": _parse_section_items(sections.get("in_flight", []), _BULLET_RE),
        "done": _parse_section_items(sections.get("done", []), _BULLET_RE),
    }


def read_manual_tickets(path: Path) -> dict:
    """Parse manual-tickets.md into todo / in_progress / done item lists."""
    if not path.exists():
        return {"todo": [], "in_progress": [], "done": []}
    sections = _split_sections(path.read_text())
    return {
        "todo": _parse_section_items(sections.get("todo", []), _PLAIN_BULLET_RE),
        "in_progress": _parse_section_items(sections.get("in_progress", []), _PLAIN_BULLET_RE),
        "done": _parse_section_items(sections.get("done", []), _PLAIN_BULLET_RE),
    }


def read_job_feed_manifests(dir_path: Path) -> dict:
    """Return the latest job-feed-manifest-*.json plus a 7-day rollup."""
    if not dir_path.exists():
        return {"latest": None, "last_7": []}
    paths = sorted(dir_path.glob("job-feed-manifest-*.json"))
    if not paths:
        return {"latest": None, "last_7": []}
    last_7 = [json.loads(p.read_text()) for p in paths[-7:]]
    return {"latest": last_7[-1], "last_7": last_7}


_PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEP_CELL_RE = re.compile(r"^:?-+:?$")
_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*$")
_PLACEHOLDER_RE = re.compile(r"_\(to fill", re.IGNORECASE)


def _normalize_col_key(header: str) -> str:
    """Normalize a pipe-table header cell to a Python-safe dict key.

    Examples:
        "#" → "id"
        "Loc / Policy" → "loc_policy"
        "Date Applied" → "date_applied"
        "Role / Company" → "role_company"
        "2nd-Degree Intros" → "2nd_degree_intros"
    """
    h = header.strip()
    if h == "#":
        return "id"
    # Lowercase, replace runs of non-alphanumeric chars with underscore
    h = h.lower()
    h = re.sub(r"[^a-z0-9]+", "_", h)
    h = h.strip("_")
    return h


def _parse_pipe_table(lines: list[str]) -> list[dict]:
    """Find the FIRST pipe table in `lines` and parse it into a list of dicts.

    - Header row → column keys via _normalize_col_key
    - Separator row (cells all match ^:?-+:?$) → skipped
    - Bold stripped from each cell: **Foo** → Foo
    - Rows where ALL cells are empty → dropped
    - Rows where first non-empty cell matches the placeholder pattern → dropped
    - Returns [] if no table is found
    """
    # Find table start: first line matching pipe-row pattern
    start = None
    for i, line in enumerate(lines):
        if _PIPE_ROW_RE.match(line):
            start = i
            break
    if start is None:
        return []

    # Collect contiguous pipe rows
    table_lines: list[str] = []
    for line in lines[start:]:
        if _PIPE_ROW_RE.match(line):
            table_lines.append(line)
        else:
            # blank line or non-pipe line ends the table
            if not line.strip():
                break
            # A non-pipe, non-blank line also ends the table
            break

    if not table_lines:
        return []

    # Parse header (first row)
    def split_row(line: str) -> list[str]:
        # strip outer pipes then split
        inner = line.strip()
        if inner.startswith("|"):
            inner = inner[1:]
        if inner.endswith("|"):
            inner = inner[:-1]
        return [cell.strip() for cell in inner.split("|")]

    headers = [_normalize_col_key(h) for h in split_row(table_lines[0])]

    rows: list[dict] = []
    for line in table_lines[1:]:
        cells = split_row(line)
        # Pad or trim to match header count
        cells = (cells + [""] * len(headers))[: len(headers)]

        # Detect separator row: all non-empty cells match ---
        non_empty_cells = [c for c in cells if c]
        if non_empty_cells and all(_SEP_CELL_RE.match(c) for c in non_empty_cells):
            continue

        # Strip bold from each cell
        stripped = [_BOLD_RE.sub(r"\1", c) for c in cells]

        # All-empty check
        if all(c == "" for c in stripped):
            continue

        # Placeholder check: first non-empty cell contains "_(to fill"
        first_non_empty = next((c for c in stripped if c), "")
        if _PLACEHOLDER_RE.search(first_non_empty):
            continue

        row = dict(zip(headers, stripped, strict=False))
        rows.append(row)

    return rows


def read_target_companies(path: Path) -> dict:
    """Parse a target-companies.md tracker into tier lists + by_status aggregate.

    Returns:
        {
            "tier_1": [row, ...],
            "tier_2": [row, ...],
            "tier_3": [row, ...],
            "by_status": {"not-applied": N, ...},
            "total": N,
        }

    PRIVATE-ONLY: callers must zero this out on public render pass.
    """
    empty: dict = {"tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0}
    if not path.exists():
        return empty

    sections = _split_sections(path.read_text())

    tier_1: list[dict] = []
    tier_2: list[dict] = []
    tier_3: list[dict] = []

    for key, lines in sections.items():
        rows = _parse_pipe_table(lines)
        # Coerce "id" column to int when present
        for row in rows:
            if "id" in row and row["id"].lstrip("-").isdigit():
                row["id"] = int(row["id"])
        if key.startswith("tier_1"):
            tier_1.extend(rows)
        elif key.startswith("tier_2"):
            tier_2.extend(rows)
        elif key.startswith("tier_3"):
            tier_3.extend(rows)

    by_status: dict[str, int] = {}
    for row in tier_1 + tier_2 + tier_3:
        status = row.get("status", "")
        if status:
            by_status[status] = by_status.get(status, 0) + 1

    total = len(tier_1) + len(tier_2) + len(tier_3)

    return {
        "tier_1": tier_1,
        "tier_2": tier_2,
        "tier_3": tier_3,
        "by_status": by_status,
        "total": total,
    }


def read_warm_intros(path: Path) -> dict:
    """Parse a warm-intros.md tracker into active / prospecting / second_degree lists.

    "total" counts active rows only — those are the warm intros that matter.

    PRIVATE-ONLY: callers must zero this out on public render pass.
    """
    empty: dict = {"active": [], "prospecting": [], "second_degree": [], "total": 0}
    if not path.exists():
        return empty

    sections = _split_sections(path.read_text())

    active: list[dict] = []
    prospecting: list[dict] = []
    second_degree: list[dict] = []

    for key, lines in sections.items():
        rows = _parse_pipe_table(lines)
        if key.startswith("active"):
            active.extend(rows)
        elif key.startswith("prospecting"):
            prospecting.extend(rows)
        elif key.startswith(("2nd-degree", "2nd_degree", "second_degree")):
            second_degree.extend(rows)

    return {
        "active": active,
        "prospecting": prospecting,
        "second_degree": second_degree,
        "total": len(active),
    }
