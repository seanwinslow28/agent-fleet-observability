---
name: Kanban v1.1 — Spark Console kanban redesign
description: Fix the four silent ticket sources, replace eval data origin with agent-run failures, and redesign the card + column anatomy to be scannable in 5 seconds. Read-only v1 scope preserved.
type: project
parent: docs/2026-05-15-agent-fleet-dashboard-design.md §3e
v2_gate: locked — 1+ recruiter engagement OR 4 weeks live, whichever first
---

# Kanban v1.1 — Spark Console kanban redesign

## 1. Why

The May 2026 build of `/kanban` ships read-only with 5 chips and 5 columns, but only one chip (Research) produces tickets, and every ticket is a 300+ character wall of prose. Two diagnoses, each verified against live vault state on 2026-05-18:

1. **Four of five sources silently produce zero tickets:**
   - `research`: the regex in `lib/readers.py:247` (`_BULLET_RE = re.compile(r"^- \[[ x]\]\s*(.+?)…")`) treats the character class `[ x]` as "space OR x", so it matches both unchecked and **completed** items. Every "pending" research ticket in `data.json` today is actually a done research topic. The `## Pending` header in the source file is stale.
   - `lint`: the composer in `lib/kanban.py:12` expects `- [HIGH|MEDIUM|LOW] msg — \`target\``. The real lint-report format is `- **rule-name** (T1): path — context`, organized under `## CRITICAL / HIGH / MEDIUM / LOW` section headers. 640 lint issues today, 0 matches.
   - `eval`: `evals/vault-synthesizer/last-run.md` was specified in the locked design doc but the synthesizer eval suite never writes it. Only `cases.yaml` exists.
   - `manual`: `vault/00_inbox/tickets.md` was "a new file Sean maintains" — never created.

2. **The card body shows full source text verbatim.** Research items are deep-researcher prompts with internal structure (`Topic 8 — Short Title. Long prose with citations. — done 2026-05-12 02:54 → [[wikilink]]`). The composer takes the whole title field. The card has no title/subtitle/meta hierarchy — every card reads as one long run-on.

The design contract from `2026-05-15-agent-fleet-dashboard-design.md` §3e remains valid; the implementation drifted from it as upstream content patterns changed.

## 2. Goal

Make the kanban scannable in 5 seconds at 06:05 ET. Honor the locked v1 read-only scope. Strengthen the visual cross-link between `/fleet` and `/kanban` so they read as one design system, not two routes that share a header.

Audience: daily-driver legibility wins. Recruiter wow is a free byproduct of doing the operational view well — confirmed during brainstorming 2026-05-18. Every micro-decision uses **"does this help me scan the board in 5 seconds"** as the tie-breaker.

## 3. Sources — what each chip means in v1.1

| Chip | Change | Origin |
|---|---|---|
| **Research** | Fix `[ ]` vs `[x]` regex bug (only unchecked = pending). Parse `Topic N — Short Title` prefix for card title; preserve full prose in `data.json`. Strip the trailing `— done DATE → [[…]]` tail. | `vault/00_inbox/research-queue.md` (unchanged) |
| **Lint** | Rewrite composer to walk `## CRITICAL / HIGH / MEDIUM / LOW` section structure with `**rule** (Tn): path — context` bullets. Cap at **top 20 cards total** — drain CRITICAL first, then HIGH, then MEDIUM, then LOW; within a tier, preserve report file order. Avoids the 640-card flood. | `vault/health/<latest>-lint-report.md` (unchanged) |
| **Eval** | Source swap: drop `last-run.md` dependency. Read `agent-run-history.csv`; emit one ticket per (agent × most-recent failure with no subsequent success) within the **last 7 days** — failures older than that age off the board. Chip label stays "Eval" — no template, CSS, or anonymize changes required by the rename of the underlying data. | `vault/90_system/agent-logs/agent-run-history.csv` |
| **Manual** | Lane revived. User-side step: `touch vault/00_inbox/tickets.md`. Existing reader already handles empty file. Chip renders "Manual 0" when empty. | `vault/00_inbox/tickets.md` (created by user) |
| **Feed** | Unchanged. Private only. | `vault/.job-feed.db` |

## 4. Card anatomy — two-line uniform

Every card, every source, the same shape. Content varies within fixed slots.

```
┌──────────────────────────────────────────────┐
│ ● Topic 8 — OpenRouter Python integ…        │  Sora 13px / 600, primary text, 2-line clamp
│                                              │
│ research · ● deep_researcher · 2026-05-12   │  JBMono 10px, tertiary text, tabular-nums
└──────────────────────────────────────────────┘
  ↑ 2px left border in source color
```

**Line 1 — title (Sora 13px, weight 600, 2-line clamp, ellipsis):**

- `research`: regex `^Topic \d+[a-z]? —\s+([^.]+)` → group 1. Fallback: first sentence truncated to 80 chars + `…`. Full prose stored in `ticket.details` for v2 expand-on-hover.
- `lint`: `**rule** (Tn) · {basename(path)}`. Full path stored in `ticket.details`.
- `eval`: `{agent} failed: {notes_or_status}`. Uses CSV `notes` if non-empty, else the `status` word (e.g., "timeout", "error"). Truncate at 60 chars + `…`. Full notes stored in `ticket.details`.
- `manual`: title as-written from `tickets.md` (Sean's convention is short).
- `feed`: `{company} · {role}`. Fit score in meta footer.

**Line 2 — meta footer (JetBrains Mono 10px, tertiary text):**

`{source} · {agent_dot}@{agent} · {timestamp_or_extra}`

Format per source:
- `research`: `research · ●@{agent_or_owner_if_present} · {parsed_date}` — agent and date both optional
- `lint`: `lint · T{tier} · {date_of_report}`
- `eval`: `eval · ●@{agent} · {failure_ts}`
- `manual`: `manual · ●@{agent_if_assigned}`
- `feed`: `feed · @Sean · fit {fit_score}`

**Live-pulse dot** (green, existing) appears at start of line 1 only when `is_running == true`. Reuses the existing CSS rule.

**Left border** stays the existing source-colored 2px stripe — research=purple, lint=amber, eval=alert, manual=gray, feed=purple. No new CSS for borders.

**Hover** keeps the existing rule: ring shifts to amber-soft (`var(--shadow-hover)`).

## 5. Column header — count + sparkline

```
ToDo  4       ▁▂▁▃▂▅▂
              ↑ inline SVG sparkline, 7d, ~48×12
```

- Count: JBMono 12px tabular-nums (existing).
- Sparkline: inline SVG via `lib/svg_charts.py` (existing helper), single-color, 7 data points, no axis, no labels. Height = column-header line-height; **no layout reflow**.
- Series source — all from `agent-run-history.csv`, last 7 days, one number per day:
  - **ToDo** sparkline: count of `status == 'failed'` runs per day, color `var(--accent-alert)`
  - **InProgress** sparkline: count of `status == 'started'` runs per day, color `var(--accent-amber)`
  - **Done** sparkline: count of `status == 'ok'` runs per day, color `var(--accent-ok)`
- **Backlog + Testing render no sparkline** — count only. We don't snapshot ticket-state history daily, so there's no honest 7-day series for "items currently in Backlog." This is the empty-state discipline applied at the column level. If we want Backlog/Testing parity later, the trigger is starting a daily ticket-count snapshot; v2 territory.

## 6. Agent state dot — cross-link to `/fleet`

The cheapest cross-link between the two routes:

- Each card with `assigned_agent` shows a 6px dot before the `@{agent}` token in line 2.
- States (same thresholds as the fleet ribbon):
  - **healthy** (green `#3FB950`) — latest run for this agent was `ok`/`completed` within expected cadence
  - **degraded** (amber `#F0B429`) — latest run was `failed` OR cadence missed by ≥1 day
  - **down** (red `#FF5C46`) — ≥3 consecutive failed runs OR no run in ≥7 days
- Cards without `assigned_agent` (research without owner, all lint, unowned manual) show **no dot** — no falsy "unknown" state.
- New aggregation: `lib/aggregations.py :: compute_agent_state(runs: list[dict]) -> dict[str, str]`. If the fleet-ribbon template currently inlines this logic, refactor it out into the new helper so both `/fleet` and `/kanban` consume the same source of truth.

The thresholds above are the verbal contract; concrete day-count constants get pinned in the implementation plan once we verify what the current `/fleet` ribbon actually uses.

## 7. Filter chips, empty states, microcopy

Filter chips: unchanged. `blur(2px) saturate(0.3) opacity(0.35)` on filter-out (existing CSS). Counts update from new totals. `[private]` suffix on `feed` stays.

Empty-state copy (voice locked in `2026-05-15-agent-fleet-dashboard-design.md` §5e):
- Manual chip with 0 tickets: chip renders "Manual 0", non-clickable. No "create your first ticket" CTA.
- Lint with 0 issues from latest report: "Knowledge clean as of {date}. No lint tickets."
- Eval with 0 open failures: "No agent failures in the last 7 days."
- Empty column: "Nothing in {column} right now."

## 8. Privacy

No new anonymization rules. The eval-source swap reads `agent-run-history.csv` — already used by the fleet ribbon and KPIs. Failure timestamps and agent names are already public per the locked anonymization table (§3f of the parent design doc). The new `compute_agent_state` map and column sparkline series both derive from data that was already crossing the public boundary.

## 9. v2 gate — still locked

Nothing in this design crosses the gate:
- No drag, no write-back
- No `tickets.json` source-of-truth
- No expand-on-hover (full prose is stored in `data.json` for a future v2 to surface, but nothing in v1.1 renders it)
- No activity-timeline strip on the kanban (`/fleet` already has one; the kanban does not get its own in v1.1)

Gate stays at: 1+ recruiter engagement attributed to v1 OR 4 weeks live, whichever first.

## 10. Files this touches

In REPO 1 (`agent-fleet-observability`):

| File | Change |
|---|---|
| `lib/readers.py` | Fix `_BULLET_RE` to exclude done items (split into `_BULLET_PENDING_RE` and `_BULLET_DONE_RE`). Refactor `read_lint_reports` to return parsed `issues: list[dict]` instead of `raw_body`. |
| `lib/kanban.py` | Add `_parse_research_title()` (Topic-prefix parser + fallback). Rewrite lint section to consume parsed issues. Add `_failures_to_tickets(runs)`. Drop the eval-from-`cases` branch. |
| `lib/aggregations.py` | New `compute_agent_state(runs) -> dict[str, str]`. New `compute_column_sparklines(runs) -> dict[str, list[int]]`. |
| `lib/svg_charts.py` | Reuse existing sparkline helper; possibly thinner variant for column-header sizing. |
| `templates/partials/kanban_board.html` | New two-line card markup. Agent state dot. Column-header sparkline render. |
| `assets/styles.css` | New: `.ticket-title`, `.ticket-meta`, `.agent-dot`, `.column-spark`. Reuse existing chip/ticket/column rules. |
| `tests/test_kanban.py` | Title parsers, lint composer, failures-from-runs composer. |
| `tests/test_aggregations.py` | Agent-state map, column sparkline series. |
| `tests/test_readers.py` | `[x]` items no longer match pending; lint reader returns parsed issues. |
| `tests/fixtures/` | Add real-shape fixtures for the new lint report format and a `research-queue.md` with mixed `[ ]` / `[x]` items. |

In REPO 2 (the vault):
- `touch /Users/seanwinslow/Code-Brain/code-brain/vault/00_inbox/tickets.md` — one-line user step; falls into the plan as a manual prerequisite.

No schema changes anywhere. No new dependencies.

## 11. Test additions (sketch)

- `test_research_regex_does_not_match_done_items`
- `test_topic_prefix_parser_extracts_short_title`
- `test_topic_prefix_parser_falls_back_to_first_sentence_under_80_chars`
- `test_research_title_strips_trailing_done_link`
- `test_lint_composer_parses_section_structure`
- `test_lint_composer_caps_at_20_by_severity_order`
- `test_failures_composer_one_ticket_per_open_failure`
- `test_failures_composer_resolves_ticket_when_subsequent_success_exists`
- `test_failures_composer_skips_failures_older_than_7_days`
- `test_agent_state_thresholds_match_fleet_ribbon`
- `test_column_sparkline_7day_series_from_runs`
- `test_column_sparkline_missing_for_backlog_and_testing`
- `test_empty_manual_chip_renders_zero_count`

## 12. Out of scope

- Drag-to-reassign, agent write-back, `tickets.json` source-of-truth — v2 only
- Activity-timeline strip on `/kanban` — v2 only
- Hover-expand for full research prose — v2 only
- Daily ticket-count snapshot for Backlog/Testing sparklines — v2 only
- Reskinning the chip taxonomy (Knowledge/Engineering/Hunt facets instead of source-based) — v2 only
- Wiring the synthesizer eval suite to write `last-run.md` — separate cross-repo project; if/when it ships, the eval source can merge `last-run.md` cases with the failures stream behind the same chip

## 13. Acceptance — done means

- All 55 existing tests still pass; the new tests in §11 pass.
- `python build.py --dry-run` reports tickets from at least 3 sources (research with only `[ ]` items, lint with cap-20, eval with failures from runs) plus manual=0 and feed (private only).
- Visual: every card on `kanban.html` fits the two-line shape; no card exceeds 2 visual lines for the title.
- Visual: ToDo / InProgress / Done columns show a 7-point sparkline; Backlog / Testing show count only.
- Visual: every card with an `@agent` token has a colored dot whose state matches the fleet ribbon for the same agent.
- `index.html` and the rest of `/fleet` are unchanged. Page weight stays under 50 KB pre-data.
