---
name: Kanban v1.1 — items deferred to v2
description: Running list of refinements surfaced by the v1.1 code reviews that are out of scope for v1.1 but worth tracking for v2 planning.
type: project
parent: docs/2026-05-18-kanban-v1-1-redesign.md
---

# Kanban v1.1 — items deferred to v2

Captured during v1.1 implementation (2026-05-18) by the per-task code-quality reviews. Most items below are minor polish; the **status-set consolidation** is the only real architectural item.

## Closed by v1.2 (this plan: 2026-05-19)

- §1 Status sets consolidation → `lib/statuses.py` (Task 1)
- Edge case: `_parse_research_title` empty-input guard (Task 2)
- Template polish: tier redundancy on lint cards removed (Task 3)
- Tests: empty-runs, status case-norm, multi-failure-same-agent, all-empty-inputs (Task 8)
- Template polish: per-source dates now surfaced as subheadline (Tasks 3, 4)
- Card distillation: bold headline + small mono date + click-to-modal full prose (Tasks 5, 6, 7)
- Eval emitter now ALSO pulls failing eval cases from `eval_last_run` per design §3e (Task 4)

The remaining followup items (multi-bullet `_parse_lint_sections` test, naming refactors,
`_LINT_BULLET_RE` em-dash docstring, `_stable_id` severity-discriminator docstring) are
still open — none blocks v1.2 ship.

Plan reference: `docs/2026-05-19-kanban-v1-2-plan.md`.

## Material — worth doing before v2 ships

### 1. Promote status sets to a shared module

`_ERR_STATUSES` and `_OK_STATUSES` are now defined **three times** across two files:

- `lib/kanban.py:127-128` — module-level `_ERR_STATUSES` / `_OK_STATUSES`, used by `_failures_to_tickets`
- `lib/aggregations.py:50-51` — locals `_ok_statuses` / `_err_statuses` inside `compute_fleet_status`
- `lib/aggregations.py:131-132` — locals `err` / `ok` inside `compute_column_sparklines`

All three definitions are byte-for-byte identical. If a new terminal status is ever added (e.g., `killed`, `aborted`), it must be updated in three places. Promote to `lib/statuses.py` (or to `lib/aggregations.py` as module constants) and import from there. The right time to do this is **before a fourth caller arrives**.

## Minor polish — discretionary

These were flagged by the per-task code-quality reviews as nice-to-haves. None blocks anything; each is a 1-3 line change.

### Tests with structural-but-untested invariants

| Where | Gap | Why it might matter |
|---|---|---|
| `tests/test_kanban.py` | No empty-runs unit test for `_failures_to_tickets([])` | One-line explicit contract assertion |
| `tests/test_kanban.py` | No status case-normalization test for `_failures_to_tickets` (`"FAILED"`) | Function does `.lower()` but no test exercises it |
| `tests/test_kanban.py` | No "multiple failures, same agent, no success → picks latest" test for `_failures_to_tickets` | `break` logic relies on newest-first sort; worth a regression net |
| `tests/test_kanban.py` | No all-empty-inputs test for `compose_tickets({}, include_job_feed=False)` → `[]` | Cheap safety net |
| `tests/test_kanban.py` | No test for `Topic 5a — Foo.` `[a-z]?` suffix branch in `_parse_research_title` | Optional-suffix regex never exercised |
| `tests/test_aggregations.py` | No empty `fleet_status == []` test for `compute_agent_state` | Trivially returns `{}` from dict comp |
| `tests/test_aggregations.py` | No duplicate-normalized-name test for `compute_agent_state` | Structurally impossible today (deduplicated `agent_names`), but no regression net |
| `tests/test_readers.py` | No test for pre-section bullets in `_parse_lint_sections` (regression for the `current_severity is None` guard) | Key correctness invariant of the stateful loop |
| `tests/test_readers.py` | No test for multiple bullets in the same lint section | Primary loop accumulation path |

### Cosmetic / naming

- `compute_agent_state` is slightly generic — `fleet_status_to_agent_health` or `compute_agent_health_map` would make the input shape and value type obvious at call sites. Rename if it propagates further.
- `tests/fixtures/sample-research-queue.md` bug-reproducer `[x]` row could carry a `<!-- bug-reproducer: ... -->` comment so a future reader doesn't "clean it up." Self-descriptive title compensates today.
- `compute_column_sparklines` boundary is exclusive at 7 days (`delta_days >= 7`) — worth a brief inline comment.
- `_stable_id` discriminator for lint includes severity (`{severity}|{rule}|{path}`), so a path escalating from MEDIUM → CRITICAL gets a new ID. Correct (forces re-render) but worth a docstring note someday.
- `by_severity` accumulation in `read_lint_reports` uses a manual `dict.get(...)+1` loop where `collections.Counter` would be idiomatic.

### Edge cases left to v2

- `_parse_research_title` returns `title=""` silently for empty/whitespace input. Add a guard like `if not cleaned: return {"title": "(no title)", "details": raw}` once the empty-input path is reachable in practice.
- `_parse_research_title` truncation may cut mid-word at 80 chars (no word-boundary handling). Adds polish if word-boundary titles matter aesthetically.
- `_parse_research_title` produces `"Topic 1 —"` (trailing em-dash) for malformed input `"Topic 1 — "` (trailing space, no body). Extremely unlikely in practice.
- `_LINT_BULLET_RE` em-dash separator: paths containing a literal `—` truncate. Format-by-design — already noted with a code comment.

### Template / visual polish

- **Tier redundancy on lint cards.** Composer (Task 4) emits ticket title `"broken-wikilink (T1) · foo.md"`, then meta footer adds another `· T1`. Spec §4 explicitly asks for `lint · T{tier}` in meta — so the dual appearance is spec-correct, but visually `T1` appears twice. Resolve by either stripping `(Tn)` from the composer title OR dropping `_tier` from the meta footer for lint specifically.
- **Per-source dates dropped from card meta.** Spec §4 mentions `{parsed_date}` (research), `{date_of_report}` (lint), `{failure_ts}` (eval) in the meta line. The v1.1 template surfaces only `source · agent_dot · agent · tier? · feed_details?` — all timestamps silently dropped. Accepted v1.1 scope cut; revisit when v2 spec stabilizes.
- **Agent dot has no `aria-label`.** A 6px colored circle conveys agent health visually but not semantically. Single-user daily-driver dashboard, so low priority. Pre-existing `.pulse-dot` has the same pattern. Add `aria-label="agent {{ state }}"` if a11y becomes a goal.
- **`agent_state` template guard.** `agent_state.get(...)` in `templates/partials/kanban_board.html` would `AttributeError` if `agent_state` were ever `None`. Render-layer guard (`agg.get("agent_state", {})`) currently prevents this, but a template-level `{% set _agent_state = agent_state or {} %}` would close the second layer cheaply.

## v2 gate is still locked

This list does NOT alter the v1.1 gate. The gate stays at: **1+ recruiter engagement attributed to v1.1 OR 4 weeks live, whichever first**. Anything in this file blocks neither v1.1 ship nor v2 entry — these are sequenced after the gate trips.
