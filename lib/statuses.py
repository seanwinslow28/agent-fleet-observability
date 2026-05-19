"""Single source of truth for agent-run terminal status sets.

Kept in its own module so kanban.py + aggregations.py can import from one
place; adding a new terminal status only needs one edit. See
docs/2026-05-18-kanban-v1-1-followups.md §1 for the motivation.
"""
from __future__ import annotations

ERR_STATUSES: frozenset[str] = frozenset({"error", "failed", "capped", "timeout"})
OK_STATUSES: frozenset[str] = frozenset({"ok", "success", "completed", "passed"})
