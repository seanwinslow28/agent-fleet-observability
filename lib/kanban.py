"""Kanban ticket composer + column membership rules.

Implements design doc Section 3e (sources) + 3e column rules. Tickets are
deterministic dicts; column assignment is computed after composition.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta
from os.path import basename, splitext

from lib.statuses import ERR_STATUSES, OK_STATUSES

_TOPIC_PREFIX_RE = re.compile(r"^(Topic \d+[a-z]?\s+—\s+.+?)(?=\.\s|\.$)")
_DONE_TAIL_RE = re.compile(r"\s*—\s*done\s+\d{4}-\d{2}-\d{2}.*$")
_RUN_ID_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

# Meta-error details substrings — eval tickets whose details match any of these
# (case-insensitive substring) are dropped as un-actionable noise. The
# eval-runner's "stderr was redirected, we lost the real failure" placeholders
# go here. Extend by appending; keep entries lowercase.
_META_ERROR_PATTERNS: tuple[str, ...] = (
    "check stderr output for details",
    "command failed with exit code",
)

# Acronyms that should stay uppercase when humanizing file slugs.
_ACRONYMS: frozenset[str] = frozenset({
    "mcp", "llm", "api", "cli", "ui", "ux", "mbp", "pi", "ai", "pm", "os",
})


def _humanize_slug(slug: str) -> str:
    """Turn a file slug like ``mcp-server-and-knowledge-graph-synergy.md``
    into ``MCP server and knowledge graph synergy``.

    Rules:
        - Strip any file extension.
        - Replace hyphens and underscores with spaces.
        - Title-case ONLY the first word; remaining words stay lowercase.
        - Known acronyms (see ``_ACRONYMS``) stay uppercase.

    Empty / whitespace input falls back to the input verbatim.
    """
    if not slug or not slug.strip():
        return slug
    stem, _ext = splitext(slug)
    stem = stem or slug  # filename with no extension
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return slug
    words = cleaned.split()
    out_words: list[str] = []
    for i, word in enumerate(words):
        lower = word.lower()
        if lower in _ACRONYMS:
            out_words.append(lower.upper())
        elif i == 0:
            out_words.append(word[:1].upper() + word[1:].lower())
        else:
            out_words.append(lower)
    return " ".join(out_words)


def _is_meta_error_details(details: str | None) -> bool:
    """Return True when ``details`` is one of the known eval-runner meta-error
    placeholders and therefore should not surface as a kanban ticket."""
    if not details:
        return False
    haystack = details.lower()
    return any(pat in haystack for pat in _META_ERROR_PATTERNS)


def _parse_research_title(raw: str) -> dict:
    """Distill a research-queue prompt into a card-sized headline + full details.

    Returns:
        {
          "headline": short distilled title (≤ 80 chars, no trailing prose),
          "details": full cleaned prose, minus the "— done DATE → wikilink" tail.
        }

    Rules:
      1. Empty/whitespace input → headline="(no title)", details=raw or "".
      2. Strip `— done DATE → [[wikilink]]` tail if present.
      3. If body starts with `Topic N — Short Title.`, headline = that prefix
         (everything up to and not including the first period).
      4. Else if body is ≤ 80 chars, headline = body verbatim.
      5. Else truncate to 80 chars + `…`.
    """
    if not raw or not raw.strip():
        return {"headline": "(no title)", "details": raw or ""}
    cleaned = _DONE_TAIL_RE.sub("", raw).strip()
    if not cleaned:
        return {"headline": "(no title)", "details": raw}
    m = _TOPIC_PREFIX_RE.match(cleaned)
    if m:
        headline = m.group(1).strip()
    elif len(cleaned) <= 80:
        headline = cleaned
    else:
        headline = cleaned[:80].rstrip() + "…"
    return {"headline": headline, "details": cleaned}


def _stable_id(source: str, title: str) -> str:
    h = hashlib.sha1(f"{source}|{title}".encode()).hexdigest()
    return f"{source}-{h[:8]}"


def compose_tickets(
    data: dict, *, include_job_feed: bool, redact_paths: bool = False
) -> list[dict]:
    """Build a single list of tickets across all sources.

    Each ticket has: id, title, source, assigned_agent, column (filled by
    compute_columns), is_running (default False), created_at, moved_at, details,
    plus optional source-specific fields (_severity for lint, etc.).

    When ``redact_paths=True`` (the public pass), every field that flows from
    raw vault paths/notes through to the public surface is redacted via
    ``lib.anonymize._redact_paths`` before it ever lands on a ticket dict.
    This extends the privacy boundary into the ticket pipeline — the prior
    boundary stopped at the aggregation layer, but lint/research/manual tickets
    are composed from raw source data and bypassed redaction. The public pass
    in ``build.py`` is the only caller that should pass ``redact_paths=True``.
    """
    # Local import — anonymize already imports kanban transitively in some
    # call paths via tests; keep this lazy so a circular import is impossible.
    from lib.anonymize import _redact_paths

    def _scrub(text: str | None) -> str | None:
        if not redact_paths:
            return text
        if text is None:
            return None
        return _redact_paths(text)

    out: list[dict] = []
    now = datetime.now(UTC).isoformat()

    # --- research --------------------------------------------------------
    rq = data.get("research_queue", {})
    for section_name, hint in [("pending", "pending"), ("in_flight", "in_flight")]:
        for item in rq.get(section_name, []):
            parsed = _parse_research_title(item["title"])
            headline = _scrub(parsed["headline"]) or parsed["headline"]
            details = _scrub(parsed["details"])
            out.append({
                "id": _stable_id("research", headline),
                "title": headline,          # back-compat alias for data.json consumers
                "headline": headline,
                "subheadline": "",          # pending research has no per-item date
                "source": "research",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": details,
            })

    # --- lint (top 20, severity-drain; duplicate ids collapsed) ----------
    lint = data.get("lint_reports", {})
    lint_date = lint.get("latest_date") or ""
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues = lint.get("issues", []) or []
    ordered = sorted(
        enumerate(issues),
        key=lambda pair: (severity_order.get(pair[1].get("severity"), 99), pair[0]),
    )
    # Compose distinct lint tickets up to a cap of 20. Multiple edges that
    # share the same (severity|rule|path) id collapse into one ticket whose
    # headline gets a ``· N edges`` suffix and whose details concatenates each
    # constituent edge's context, deduplicated and newline-separated.
    lint_by_id: dict[str, dict] = {}
    lint_order: list[str] = []
    for _idx, iss in ordered:
        # Stable id keys on the *raw* path so the public and private passes
        # agree on which edges collapse together. Only the surfaced strings
        # (edge_detail, slug) are redacted — the id is internal.
        ticket_id = _stable_id("lint", f"{iss['severity']}|{iss['rule']}|{iss['path']}")
        scrubbed_path = _scrub(iss["path"]) or iss["path"]
        scrubbed_context = _scrub(iss.get("context") or "") or ""
        edge_detail = f"{scrubbed_path} — {scrubbed_context}"
        if ticket_id in lint_by_id:
            ticket = lint_by_id[ticket_id]
            # Asymmetric on purpose: details dedupe (we don't want to show the
            # same context twice in the modal), count does not (the badge
            # reflects raw edge cardinality, e.g. "8 edges" even when several
            # share an identical context string).
            if edge_detail not in ticket["_edge_details"]:
                ticket["_edge_details"].append(edge_detail)
            ticket["count"] += 1
            continue
        if len(lint_by_id) >= 20:
            continue
        slug = basename(iss["path"])
        humanized = _humanize_slug(slug)
        ticket = {
            "id": ticket_id,
            "title": "",  # filled in after collapsing
            "headline": "",
            "subheadline": lint_date,
            "source": "lint",
            "assigned_agent": None,
            "_section_hint": "pending",
            "_severity": iss["severity"],
            "_tier": iss["tier"],
            "_rule": iss["rule"],
            "_slug": slug,
            "_humanized": humanized,
            "_edge_details": [edge_detail],
            "count": 1,
            "created_at": now, "moved_at": now,
        }
        lint_by_id[ticket_id] = ticket
        lint_order.append(ticket_id)
    for ticket_id in lint_order:
        ticket = lint_by_id[ticket_id]
        base_headline = f"{ticket['_rule']} · {ticket['_humanized']}"
        if ticket["count"] > 1:
            headline = f"{base_headline} · {ticket['count']} edges"
        else:
            headline = base_headline
        ticket["headline"] = headline
        ticket["title"] = headline
        # The headline is humanized; the raw filename is preserved inside each
        # edge detail row ("{path} — {context}"), so the modal still surfaces
        # the filename without a redundant prefix line.
        ticket["details"] = "\n".join(ticket["_edge_details"])
        # Drop transient bookkeeping that consumers don't need.
        del ticket["_edge_details"]
        out.append(ticket)

    # --- eval (agent_runs failures + failing eval cases) -----------------
    runs = data.get("agent_runs") or []
    eval_tickets = list(_failures_to_tickets(runs))
    eval_tickets.extend(_eval_cases_to_tickets(data.get("eval_last_run", {}) or {}))
    for t in eval_tickets:
        t["details"] = _scrub(t.get("details"))
    out.extend(eval_tickets)

    # --- manual ----------------------------------------------------------
    mt = data.get("manual_tickets", {})
    for section_name, hint in [("todo", "todo"), ("in_progress", "in_progress"), ("done", "done")]:
        for item in mt.get(section_name, []):
            title = _scrub(item["title"]) or item["title"]
            out.append({
                "id": _stable_id("manual", title),
                "title": title,
                "headline": title,
                "subheadline": "",
                "source": "manual",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": None,
            })

    # --- feed (private only) ---------------------------------------------
    if include_job_feed:
        for p in data.get("job_feed", {}).get("top_fit", []):
            headline = f"{p['company']} · {p['title']}"
            first_seen = (p.get("first_seen_at") or "")[:10]  # YYYY-MM-DD prefix
            out.append({
                "id": _stable_id("feed", headline),
                "title": headline,
                "headline": headline,
                "subheadline": first_seen,
                "source": "feed",
                "assigned_agent": "Sean",
                "_section_hint": p.get("status", "new"),
                "created_at": now, "moved_at": now,
                "details": f"fit {p.get('fit_score')}",
            })

    return out


_HERO_WINDOW_DAYS = 7
_HERO_SOURCES: tuple[str, ...] = ("research", "lint", "eval", "manual", "feed")


def compose_kanban_hero_stats(
    tickets: list[dict],
    today: datetime | date | None = None,
) -> dict:
    """Roll up the ticket list into the /kanban hero-plate stats.

    Counts tickets whose ``created_at`` falls within the last 7 days
    (inclusive of the 7th day), bucketed by source. Tickets with no
    ``created_at`` (or ``created_at == None``) are treated as "now" and
    therefore always counted — we never silently drop a ticket.

    Args:
        tickets: composed ticket dicts (from ``compose_tickets``).
        today: anchor datetime for the 7-day window. Defaults to now (UTC).
               A ``date`` is accepted and lifted to UTC midnight.

    Returns:
        ``{"total_7d": int, "by_source": {source: int, ...}, "is_quiet_week": bool}``.
        ``by_source`` always contains every key in ``_HERO_SOURCES`` so the
        template can iterate without KeyError. ``feed`` is included
        unconditionally; on the public pass the caller passes a feed-less
        ticket list and the count naturally stays at 0 — the privacy
        boundary is enforced upstream by ``compose_tickets(include_job_feed=...)``.
    """
    if today is None:
        anchor = datetime.now(UTC)
    elif isinstance(today, datetime):
        anchor = today if today.tzinfo else today.replace(tzinfo=UTC)
    else:  # date
        anchor = datetime(today.year, today.month, today.day, tzinfo=UTC)
    cutoff = anchor - timedelta(days=_HERO_WINDOW_DAYS)

    by_source: dict[str, int] = dict.fromkeys(_HERO_SOURCES, 0)
    total = 0
    for t in tickets:
        created_at = t.get("created_at")
        if not created_at:
            created_dt = anchor
        else:
            try:
                created_dt = datetime.fromisoformat(created_at)
            except (TypeError, ValueError):
                created_dt = anchor
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=UTC)
        if created_dt < cutoff:
            continue
        total += 1
        src = t.get("source")
        if src in by_source:
            by_source[src] += 1

    return {
        "total_7d": total,
        "by_source": by_source,
        "is_quiet_week": total == 0,
    }


_FAILURE_WINDOW = timedelta(days=7)


def _failures_to_tickets(runs: list[dict]) -> list[dict]:
    """Emit one ticket per (agent × most-recent unresolved failure within 7 days).

    "Unresolved" = there is no `ok`/`success`/`completed`/`passed` run for the
    same agent at a timestamp AFTER the failure. Failures older than 7 days age
    off; subsequent successes resolve.

    Ticket shape:
        headline    = "{agent} failed: {status_word}"  (status lower-cased)
        subheadline = "{YYYY-MM-DD}"                   (the failure date)
        details     = the full notes string (or None when notes is empty)
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
        # Sort newest first: the `is None` guard on latest_success_ts then
        # captures the most-recent success, and `break` after latest_failure
        # skips older, irrelevant failures.
        agent_runs.sort(key=lambda r: r["ts"], reverse=True)
        latest_failure: dict | None = None
        latest_success_ts = None
        for r in agent_runs:
            status = r["status"].lower()
            if status in OK_STATUSES and latest_success_ts is None:
                latest_success_ts = r["ts"]
            if status in ERR_STATUSES:
                latest_failure = r
                break
        if not latest_failure:
            continue
        # If any success exists after the failure timestamp, ticket is resolved
        if latest_success_ts is not None and latest_success_ts > latest_failure["ts"]:
            continue

        notes = (latest_failure.get("notes") or "").strip()
        if _is_meta_error_details(notes):
            continue  # eval-runner placeholder, not a real failure description
        status_word = latest_failure["status"].lower()
        headline = f"{agent} failed: {status_word}"
        out.append({
            "id": _stable_id("eval", f"{agent}|{latest_failure['ts'].isoformat()}"),
            "title": headline,
            "headline": headline,
            "subheadline": latest_failure["ts"].strftime("%Y-%m-%d"),
            "source": "eval",
            "assigned_agent": agent,
            "_section_hint": "todo",
            "created_at": latest_failure["ts"].isoformat(),
            "moved_at": latest_failure["ts"].isoformat(),
            "details": notes or None,
        })
    return out


def _eval_cases_to_tickets(eval_last_run: dict) -> list[dict]:
    """Emit one ticket per failing eval case in evals/vault-synthesizer/last-run.md.

    Design doc §3e: "Failing eval cases from evals/vault-synthesizer/last-run.md".
    Only `status == "failed"` rows become tickets; passed/skipped/unknown are
    silently dropped. Each ticket's headline is `eval failed: {case_id}`;
    subheadline is the first 10 chars of run_id when it looks date-shaped
    (YYYY-MM-DD…), else empty.
    """
    now = datetime.now(UTC).isoformat()
    out: list[dict] = []
    run_id = eval_last_run.get("run_id") or ""
    subheadline = run_id[:10] if _RUN_ID_DATE_RE.match(run_id) else ""
    for case in eval_last_run.get("cases", []) or []:
        if (case.get("status") or "").lower() != "failed":
            continue
        case_id = case.get("id") or ""
        if not case_id:
            continue
        # Filter cases whose own details payload is an eval-runner meta-error
        # placeholder. The synthesized `case_details` string below can never
        # contain a meta-error pattern, so we only inspect the upstream field.
        if _is_meta_error_details(case.get("details")):
            continue
        category = case.get("category") or ""
        case_details = f"{case_id} ({category}) failed in eval run {run_id or 'current'}"
        headline = f"eval failed: {case_id}"
        out.append({
            "id": _stable_id("eval-case", f"{case_id}|{run_id or 'current'}"),
            "title": headline,
            "headline": headline,
            "subheadline": subheadline,
            "source": "eval",
            "assigned_agent": None,
            "_section_hint": "todo",
            "_eval_case_id": case_id,
            "created_at": now, "moved_at": now,
            "details": case_details,
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
