"""Public-pass anonymization for the Agent Fleet Observability Dashboard.

Implements the privacy boundary described in design doc Sections 2c + 3f.
Rules:
1. Job Feed data source is fully zeroed (skipped on public pass).
2. Target-30 + Warm-Intro trackers are fully zeroed (§4d live-wire — private-only data).
3. Vault path references in notes / titles are replaced with `vault/[redacted]`.
4. Dollar amounts are PRESERVED — they tell the architectural story.
5. Eval case names, agent names, run timestamps are PRESERVED.
"""
from __future__ import annotations

import copy
import re

_VAULT_PATH_RE = re.compile(r"vault/[\w\-/.]+")


def _redact_paths(text: str | None) -> str:
    if not text:
        return text or ""
    return _VAULT_PATH_RE.sub("[redacted]", text)


def public_pass(agg: dict) -> dict:
    """Return a deep copy of `agg` with public-safe substitutions."""
    out = copy.deepcopy(agg)
    for tile in out.get("fleet_status", []):
        tile["last_notes"] = _redact_paths(tile.get("last_notes"))
    for r in out.get("recent_runs", []):
        r["notes"] = _redact_paths(r.get("notes"))
    out["job_feed"] = {"total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0}
    out["job_feed_manifests"] = {"latest": None, "last_7": []}
    # §4d live-wire: zero private-only trackers
    out["target_companies"] = {
        "tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0
    }
    out["warm_intros"] = {"active": [], "prospecting": [], "second_degree": [], "total": 0}
    for section in ("pending", "in_flight", "done"):
        for item in out.get("research_queue", {}).get(section, []):
            item["title"] = _redact_paths(item.get("title"))
    for section in ("todo", "in_progress", "done"):
        for item in out.get("manual_tickets", {}).get(section, []):
            item["title"] = _redact_paths(item.get("title"))
    out["_public_pass_applied"] = True
    return out
