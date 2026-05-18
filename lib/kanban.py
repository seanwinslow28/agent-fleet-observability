"""Kanban ticket composer + column membership rules.

Implements design doc Section 3e (sources) + 3e column rules. Tickets are
deterministic dicts; column assignment is computed after composition.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from os.path import basename

_TOPIC_PREFIX_RE = re.compile(r"^(Topic \d+[a-z]?\s+—\s+[^.]+)")
_DONE_TAIL_RE = re.compile(r"\s*—\s*done\s+\d{4}-\d{2}-\d{2}.*$")


def _parse_research_title(raw: str) -> dict:
    """Distill a research-queue prompt into a card-sized title.

    Order of rules:
        1. Strip the `— done DATE → [[wikilink]]` tail if present.
        2. If the body starts with `Topic N — Short Title.`, use everything
           up to (and not including) the first period.
        3. Else if the whole body is ≤ 80 chars, use it verbatim.
        4. Else truncate to 80 chars + `…`.

    Returns dict with `title` (display) and `details` (original prose,
    minus the done-tail, for v2 expand-on-hover).
    """
    cleaned = _DONE_TAIL_RE.sub("", raw).strip()
    m = _TOPIC_PREFIX_RE.match(cleaned)
    if m:
        title = m.group(1).strip()
    elif len(cleaned) <= 80:
        title = cleaned
    else:
        title = cleaned[:80].rstrip() + "…"
    return {"title": title, "details": cleaned}


def _stable_id(source: str, title: str) -> str:
    h = hashlib.sha1(f"{source}|{title}".encode()).hexdigest()
    return f"{source}-{h[:8]}"


def compose_tickets(data: dict, *, include_job_feed: bool) -> list[dict]:
    """Build a single list of tickets across all sources.

    Each ticket has: id, title, source, assigned_agent, column (filled by
    compute_columns), is_running (default False), created_at, moved_at, details,
    plus optional source-specific fields (_severity for lint, etc.).
    """
    out: list[dict] = []
    now = datetime.now(UTC).isoformat()

    # --- research --------------------------------------------------------
    rq = data.get("research_queue", {})
    for section_name, hint in [("pending", "pending"), ("in_flight", "in_flight")]:
        for item in rq.get(section_name, []):
            parsed = _parse_research_title(item["title"])
            out.append({
                "id": _stable_id("research", parsed["title"]),
                "title": parsed["title"],
                "source": "research",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": parsed["details"],
            })

    # --- lint (top 20, severity-drain) -----------------------------------
    lint = data.get("lint_reports", {})
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues = lint.get("issues", []) or []
    ordered = sorted(
        enumerate(issues),
        key=lambda pair: (severity_order.get(pair[1].get("severity"), 99), pair[0]),
    )
    for _idx, iss in ordered[:20]:
        title = f"{iss['rule']} ({iss['tier']}) · {basename(iss['path'])}"
        out.append({
            "id": _stable_id("lint", f"{iss['severity']}|{iss['rule']}|{iss['path']}"),
            "title": title,
            "source": "lint",
            "assigned_agent": None,
            "_section_hint": "pending",
            "_severity": iss["severity"],
            "_tier": iss["tier"],
            "created_at": now, "moved_at": now,
            "details": f"{iss['path']} — {iss['context']}",
        })

    # --- eval (failures from agent_runs) ---------------------------------
    # Implemented in Task 5; passes through empty for now.
    runs = data.get("agent_runs") or []
    for ticket in _failures_to_tickets(runs):
        out.append(ticket)

    # --- manual ----------------------------------------------------------
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

    # --- feed (private only) ---------------------------------------------
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


_ERR_STATUSES = {"error", "failed", "capped", "timeout"}
_OK_STATUSES = {"ok", "success", "completed", "passed"}
_FAILURE_WINDOW = timedelta(days=7)


def _failures_to_tickets(runs: list[dict]) -> list[dict]:
    """Emit one ticket per (agent × most-recent unresolved failure within 7 days).

    "Unresolved" = there is no `ok`/`success`/`completed`/`passed` run for the
    same agent at a timestamp AFTER the failure. Failures older than 7 days
    age off; subsequent successes resolve. Title format:
    "{agent} failed: {notes_or_status_word}" truncated to 60 chars + ….
    """
    now = datetime.now(UTC)
    cutoff = now - _FAILURE_WINDOW
    by_agent: dict[str, list[dict]] = {}
    for r in runs:
        if r["ts"] < cutoff:
            continue
        by_agent.setdefault(r["agent"], []).append(r)

    out: list[dict] = []
    for agent, agent_runs in by_agent.items():
        # Sort newest first so we find the latest failure quickly
        agent_runs.sort(key=lambda r: r["ts"], reverse=True)
        latest_failure: dict | None = None
        latest_success_ts = None
        for r in agent_runs:
            status = r["status"].lower()
            if status in _OK_STATUSES and latest_success_ts is None:
                latest_success_ts = r["ts"]
            if status in _ERR_STATUSES:
                latest_failure = r
                break
        if not latest_failure:
            continue
        # If any success exists after the failure timestamp, ticket is resolved
        if latest_success_ts is not None and latest_success_ts > latest_failure["ts"]:
            continue

        notes = (latest_failure.get("notes") or "").strip()
        tail = notes if notes else latest_failure["status"].lower()
        if len(tail) > 60:
            tail = tail[:60].rstrip() + "…"
        title = f"{agent} failed: {tail}"
        out.append({
            "id": _stable_id("eval", f"{agent}|{latest_failure['ts'].isoformat()}"),
            "title": title,
            "source": "eval",
            "assigned_agent": agent,
            "_section_hint": "todo",
            "created_at": latest_failure["ts"].isoformat(),
            "moved_at": latest_failure["ts"].isoformat(),
            "details": notes or None,
        })
    return out


RUNNING_WINDOW = timedelta(minutes=10)


def _recent_started_agents(runs: list[dict], now: datetime) -> set[str]:
    started: set[str] = set()
    completed: set[str] = set()
    for r in runs:
        if r["ts"] < now - RUNNING_WINDOW:
            continue
        if r["status"] == "started":
            started.add(r["agent"])
        elif r["status"] in ("ok", "error", "failed", "completed"):
            completed.add(r["agent"])
    return started - completed


def compute_columns(tickets: list[dict], runs: list[dict]) -> list[dict]:
    """Apply design doc Section 3e column rules to every ticket.

    Mutates each dict to add `column` and `is_running` keys; returns the list.
    """
    now = datetime.now(UTC)
    running = _recent_started_agents(runs, now)
    for t in tickets:
        agent = t.get("assigned_agent")
        section = t.get("_section_hint")
        if section == "done":
            t["column"] = "done"
            t["is_running"] = False
            continue
        if agent and agent in running:
            t["column"] = "in_progress"
            t["is_running"] = True
            continue
        if section == "in_progress":
            t["column"] = "in_progress"
            t["is_running"] = False
            continue
        if section == "todo":
            t["column"] = "todo"
            t["is_running"] = False
            continue
        if agent or (t["source"] == "eval"):
            t["column"] = "todo"
            t["is_running"] = False
            continue
        t["column"] = "backlog"
        t["is_running"] = False
    return tickets
