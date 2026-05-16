"""Kanban ticket composer + column membership rules.

Implements design doc Section 3e (sources) + 3e column rules. Tickets are
deterministic dicts; column assignment is computed after composition.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

_LINT_LINE_RE = re.compile(r"^- \[(HIGH|MEDIUM|LOW)\]\s+(.+?)(?:\s+—\s+`(.+?)`)?\s*$")


def _stable_id(source: str, title: str) -> str:
    h = hashlib.sha1(f"{source}|{title}".encode()).hexdigest()
    return f"{source}-{h[:8]}"


def compose_tickets(data: dict, *, include_job_feed: bool) -> list[dict]:
    """Build a single list of tickets across all sources.

    Each ticket has: id, title, source, assigned_agent, column (filled by
    compute_columns), is_running (default False), created_at, moved_at, details.
    """
    out: list[dict] = []
    now = datetime.now(UTC).isoformat()

    rq = data.get("research_queue", {})
    for item in rq.get("pending", []):
        out.append({
            "id": _stable_id("research", item["title"]),
            "title": item["title"], "source": "research",
            "assigned_agent": item.get("assigned_agent"),
            "_section_hint": "pending",
            "created_at": now, "moved_at": now, "details": None,
        })
    for item in rq.get("in_flight", []):
        out.append({
            "id": _stable_id("research", item["title"]),
            "title": item["title"], "source": "research",
            "assigned_agent": item.get("assigned_agent"),
            "_section_hint": "in_flight",
            "created_at": now, "moved_at": now, "details": None,
        })

    lint = data.get("lint_reports", {})
    for line in (lint.get("raw_body") or "").splitlines():
        m = _LINT_LINE_RE.match(line.strip())
        if not m:
            continue
        severity, msg, target = m.groups()
        title = f"[{severity}] {msg}" + (f" ({target})" if target else "")
        out.append({
            "id": _stable_id("lint", title),
            "title": title, "source": "lint",
            "assigned_agent": None, "_section_hint": "pending",
            "created_at": now, "moved_at": now, "details": None,
        })

    eval_run = data.get("eval_last_run", {})
    for case in eval_run.get("cases", []):
        if case.get("status") != "failed":
            continue
        title = f"Eval failing: {case['id']}"
        out.append({
            "id": _stable_id("eval", title),
            "title": title, "source": "eval",
            "assigned_agent": None, "_section_hint": "todo",
            "created_at": now, "moved_at": now, "details": None,
        })

    mt = data.get("manual_tickets", {})
    for section_name, hint in [("todo", "todo"), ("in_progress", "in_progress"), ("done", "done")]:
        for item in mt.get(section_name, []):
            out.append({
                "id": _stable_id("manual", item["title"]),
                "title": item["title"], "source": "manual",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now, "details": None,
            })

    if include_job_feed:
        for p in data.get("job_feed", {}).get("top_fit", []):
            title = f"{p['company']} · {p['title']}"
            out.append({
                "id": _stable_id("feed", title),
                "title": title, "source": "feed",
                "assigned_agent": "Sean",
                "_section_hint": p.get("status", "new"),
                "created_at": now, "moved_at": now,
                "details": f"fit {p.get('fit_score')}",
            })

    return out
