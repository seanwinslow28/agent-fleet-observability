"""Data source loaders for the Agent Fleet Observability Dashboard.

All readers return plain dicts / lists of dicts — no domain models. Aggregation
happens downstream in lib/aggregations.py. Empty inputs return empty containers,
not None, so callers can blindly iterate.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path


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
