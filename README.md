# Agent Fleet Observability

[![dashboard](https://img.shields.io/badge/dashboard-fleet.seanwinslow.com-c084fc)](https://fleet.seanwinslow.com)

Static observability dashboard for a multi-agent local-first AI fleet.
Builds nightly on a Mac Mini. $0 cloud, 99% local-first inference.

> **The story:** for nine consecutive nights, my vault synthesizer wrote zero
> concepts. A 10-case eval suite caught it on day ten. This dashboard preserves
> the incident timeline + the recovery as proof of operational maturity.

---

## 1 · What problem this solves

A growing set of cron-scheduled AI agents (vault indexer, synthesizer, deep
researcher, meta-agent, daily driver, knowledge lint, flush, job feed)
generate ~30 runs/day across local + cloud models. Without a single surface,
you trust-fall every night: did the synthesizer run, did the eval pass, did
the Gemini budget hold?

This dashboard makes the fleet inspectable in 30 seconds: which agents are
healthy, what was last night's eval score, what's the 30-day spend pattern,
which tickets are mid-flight on the kanban board.

## 2 · How it works

```
Mac Mini cron (06:00 ET)
        │
        ├──▶ Read vault data (CSV + JSON + SQLite + Markdown)
        ├──▶ Aggregate (KPIs, sparklines, regression window, model mix)
        └──▶ Render two passes:
              ├─ public  → repo root → git push → Vercel auto-deploy
              └─ private → ~/Sites/agent-fleet-private/ (gitignored)
```

- **Backend:** Python 3.12 stdlib + Jinja2 + PyYAML, no framework, ~1,200 lines including tests.
- **Frontend:** Jinja2 templates + inline SVG charts (no Chart.js), ~14 KB stylesheet.
- **Auth:** none. Public read-only. Privacy is structural — the public render
  pass never reads `vault/.job-feed.db` or job-hunt trackers, period.
- **Hosting:** Vercel static deploy + Cloudflare DNS-only CNAME (gray cloud — Vercel terminates SSL).

## 3 · What's notable

- **Privacy boundary is structural, not policy.** Job-hunt data physically
  cannot leak — the data source is skipped on public render, the output paths
  are separate directories, and one is gitignored at the home level.
- **Honest empty states.** Every panel renders "what actually happened"
  copy when data is missing — no spinners-that-never-resolve, no mock data.
- **Regression as hero.** The 9-day silent regression is the central visual,
  not a buried annotation. Operational maturity is recovered failures.
- **All telemetry traces to a verifiable file.** Every number on the page
  has a CSV row, JSON record, SQLite row, or Markdown file behind it.
- **Inline SVG charts, no Chart.js.** Page weight stays under 50 KB pre-data;
  charts survive screenshots; no CDN race on cold-cache load.

## 4 · How to read this code

- [`build.py`](build.py) — orchestrator (read → aggregate → render).
- [`lib/readers.py`](lib/readers.py) — 12 data source loaders (CSV / JSON / SQLite / Markdown).
- [`lib/aggregations.py`](lib/aggregations.py) — KPI + regression window + model mix.
- [`lib/anonymize.py`](lib/anonymize.py) — public-pass stripping rules.
- [`lib/svg_charts.py`](lib/svg_charts.py) — inline SVG helpers (line, sparkline, donut, stacked area).
- [`lib/kanban.py`](lib/kanban.py) — ticket composer + column membership rules.
- [`lib/render.py`](lib/render.py) — public + private render orchestrators (one module, two functions).
- [`tests/`](tests/) — pytest suite (55 tests; `make test` to run).

### Local dev

```bash
git clone https://github.com/seanwinslow28/agent-fleet-observability
cd agent-fleet-observability
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
make test    # run the pytest suite
make build   # render against your vault (paths in build.py)
```

### Cron install

```bash
cp schedules/com.sean.agent-fleet-dashboard.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sean.agent-fleet-dashboard.plist
```

Fires at 06:00 local time daily; logs land in `logs/build.{out,err}.log`.

---

Built by [Sean Winslow](https://github.com/seanwinslow28) · 2026 · MIT
