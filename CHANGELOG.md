# Changelog

All notable changes to the Agent Fleet Observability Dashboard.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dates are
absolute (no relative "yesterday" / "last week" — those rot). v2 (locked, gated on
1+ recruiter engagement OR 4 weeks live) is tracked in
[docs/project_agent_fleet_dashboard_kanban_v2.md](docs/project_agent_fleet_dashboard_kanban_v2.md).

---

## [1.2.0] — 2026-05-19

Kanban refresh: card distillation + multi-source enrichment. Tightens what v1.1
shipped after observing the 2026-05-18 snapshot. Pre-v2 polish; locked v2 stays
gated.

Plan: [docs/2026-05-19-kanban-v1-2-plan.md](docs/2026-05-19-kanban-v1-2-plan.md) ·
PR [#5](https://github.com/seanwinslow28/agent-fleet-observability/pull/5).

### Added

- **Eval-case ticket emitter** — `_eval_cases_to_tickets` pulls failing cases
  from `evals/vault-synthesizer/last-run.md` per design §3e. Previously only
  `agent_runs` failures became eval tickets.
- **Click-to-modal for ticket details** — vanilla JS (`assets/kanban-modal.js`,
  ~50 lines): Escape close, backdrop close, focus restore. Full prose lives in
  `data-details` and renders inside the modal dialog.
- **Uniform ticket schema** — every source (research, lint, eval-from-runs,
  eval-from-cases, manual, feed) now emits `headline`, `subheadline`, `details`,
  plus `title` as a back-compat alias.
- **Per-source date subheadline** — lint shows the report date, eval the failure
  date (or `run_id` prefix), feed the `first_seen_at` date. Research stays empty
  (no per-item date in the source file).
- **`lib/statuses.py`** — single source of truth for `ERR_STATUSES` /
  `OK_STATUSES` (was duplicated in `lib/kanban.py` + two locations in
  `lib/aggregations.py`).
- **Manual tickets schema doc** at
  [docs/manual-tickets-schema.md](docs/manual-tickets-schema.md). Vault file
  `vault/00_inbox/tickets.md` seeded with the section skeleton (Todo / In
  Progress / Done) so the Manual chip can light up when bullets land.
- **Followup-gap tests** — 4 regression-net tests close the
  v1.1-followups-flagged invariants (empty-runs, status case-norm,
  multi-failure-same-agent, all-empty-inputs).

### Changed

- **Bold 2-line headline + small mono date subheadline** replace the
  prior single-line `.ticket-title`. Headline clamped via `-webkit-line-clamp:
  2` + `line-clamp: 2`. Cards are visibly compact.
- **Lint headline drops the `(Tn)` tier** — tier now appears only in the meta
  line (closes followups §template-polish "Tier redundancy on lint cards").
- **Eval-from-runs headline** is now `{agent} failed: {status_word}` — notes
  move to `details` (read in the modal). Was previously the truncated notes
  inline.
- **Ticket element** is now `<button type="button">` (was `<div>`) — native
  keyboard activation (Enter/Space), `aria-haspopup="dialog"`, `:focus-visible`
  outline.
- **Modal styling** — backdrop with both `-webkit-backdrop-filter` and
  `backdrop-filter` for Safari; close button has `:focus-visible` since it
  receives programmatic focus on open.

### Fixed

- **`_parse_research_title` empty-input guard** — whitespace-only or
  done-tail-only inputs no longer return `headline=""`; they now return
  `(no title)` with the raw input preserved in `details`.

### Tests

- 97 → 101 passing.
- 15 new tests across the schema, eval-case emitter, template render, and
  followup-gap groups.

---

## [1.1.0] — 2026-05-18

Kanban redesign + activity-timeline integration. Built on top of v1.0 to fix
real shapes in the data and tighten the visual layer.

Plan: [docs/2026-05-18-kanban-v1-1-plan.md](docs/2026-05-18-kanban-v1-1-plan.md) ·
followups: [docs/2026-05-18-kanban-v1-1-followups.md](docs/2026-05-18-kanban-v1-1-followups.md).

### Added

- **Activity timeline panel** ([lib/activity_timeline.py](lib/activity_timeline.py))
  — 24-hour per-agent lane view with `run` density bars (PRs #1, #2, #3, #4).
- **`compute_agent_state`** — normalized agent name → fleet health for the
  per-ticket agent dot.
- **`compute_column_sparklines`** — 7-day series per kanban column (ToDo /
  InProgress / Done).
- **Two-line ticket card** with agent dot + column sparklines.
- **Real-shape lint composer** + research title parser (`_parse_research_title`
  with `Topic N — Title.` distillation, 80-char truncation, done-tail strip).
- **Eval source reads from `agent_runs` failures** with 7-day window + latest-
  failure-wins logic.
- **`test_anonymize`** pins agent_state + column_sparklines through `public_pass`.
- **`_LINT_BULLET_RE` em-dash separator** (path field reserves `—` as the column
  delimiter).

### Fixed

- **Research queue regex** — `[x]` (done) bullets stuck under stale `## Pending`
  headers no longer surface as live tickets.

### Changed

- **Kanban meta gap** — replaced bare `4px` with `var(--space-1)` for token
  consistency.

### Tests

- 55 baseline → 97 passing across the v1.1 build.

---

## [1.0.0] — 2026-05-16

Initial ship — design-doc-complete static-site generator dashboard. Public
surface at `fleet.seanwinslow.com` (Vercel + Cloudflare CNAME) plus private
mirror at `~/Sites/agent-fleet-private/`. Daily cron at 06:00 ET.

Design: [docs/2026-05-15-agent-fleet-dashboard-design.md](docs/2026-05-15-agent-fleet-dashboard-design.md) ·
plan: [docs/2026-05-15-agent-fleet-dashboard-plan.md](docs/2026-05-15-agent-fleet-dashboard-plan.md).

### Added

- **Two-pass build pipeline** ([build.py](build.py)) — reads 12 vault data
  sources (CSV / JSON / SQLite / Markdown), aggregates, and renders public-safe
  + private HTML from one codebase.
- **Privacy boundary (structural)** ([lib/anonymize.py](lib/anonymize.py)) —
  public pass zeros `job_feed`, `target_companies`, `warm_intros`; redacts
  vault paths in notes + titles; private pass is the unredacted full set.
- **SVG chart library** ([lib/svg_charts.py](lib/svg_charts.py)) — `line_chart`,
  `sparkline`, `donut`, `stacked_area`. No JS framework, no CDN. Inline SVG
  only.
- **Hero regression chart** — 60-day synthesizer telemetry with annotated
  9-night silent regression + eval catch-point marker.
- **KPI row** — 4 cards (eval pass · fleet spend · local-only share · spend
  governors).
- **Agent grid** — 8 tiles with status dot, last-run timestamp, last cost.
- **Below-fold panels** — 30-day cost trend, model mix donut, recent runs
  table, synth telemetry deep dive, eval case grid.
- **Private below-fold panels** — Job Hunt funnel (Target-30, warm-intros,
  next actions, Tier-A guardrail check), cloud spend governance (Gemini DR +
  LLM Council).
- **Kanban v1 (read-only)** — 5 columns (Backlog · ToDo · InProgress ·
  Testing · Done) sourced from research-queue, lint reports, eval failures,
  manual tickets, job feed (private only). Live-pulse dot for InProgress.
- **Asterisk Spark mascot** — 32px CSS spark with 12s spin + 5.5s blink.
  `prefers-reduced-motion: reduce` disables animations.
- **Microcopy voice** — Sean-voice empty states ("Synth napped 9 nights this
  month. MBP was asleep.").
- **Dark hybrid palette** (Vercel-deployment-log mood) + Sora/Inter/JetBrains
  Mono typography stack.
- **Mobile responsive** — 4-up → 2-up → 1-up cascade with 375px iPhone floor.
- **launchd cron** at 06:00 ET daily ([schedules/com.sean.agent-fleet-dashboard.plist](schedules/com.sean.agent-fleet-dashboard.plist)).
- **Vercel static-site config** ([vercel.json](vercel.json)) — overrides Python
  auto-detection (`framework: null`); repo is served as committed.
- **`make deploy`** — diff-and-commit-push public artifacts (`index.html`,
  `kanban.html`, `data.json`) only when changed.

### Tests

- 55 tests across readers (fixture files), aggregations, kanban column
  membership, anonymize stripping, SVG chart helpers, and a render smoke test.

---

[1.2.0]: https://github.com/seanwinslow28/agent-fleet-observability/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/seanwinslow28/agent-fleet-observability/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/seanwinslow28/agent-fleet-observability/releases/tag/v1.0.0
