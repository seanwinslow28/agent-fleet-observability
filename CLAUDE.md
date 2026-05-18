# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
make test          # run pytest suite (55 tests)
make build         # full render (reads vault, writes index.html + kanban.html + data.json)
make lint          # ruff check + format --check
make format        # ruff format
make deploy        # build, then diff-commit-push public files only if changed

python build.py --dry-run    # plan only, write nothing
python build.py --no-push    # build + write, skip git commit/push
python build.py -v           # verbose logging

.venv/bin/pytest tests/test_aggregations.py::test_name -v   # single test
```

Python 3.12 required. Install dev env with `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.

## Architecture

This is a **static site generator** that renders a fleet observability dashboard from filesystem data sources. Two passes share ~90% of logic but produce different outputs:

- **Public pass** → repo root (`index.html`, `kanban.html`, `data.json`) → git push → Vercel auto-deploy.
- **Private pass** → `~/Sites/agent-fleet-private/` (gitignored at home level).

Daily build is driven by launchd ([schedules/com.sean.agent-fleet-dashboard.plist](schedules/com.sean.agent-fleet-dashboard.plist)) firing `build.py` at 06:00 local time. Logs land in `logs/build.{out,err}.log`.

### Data flow (one direction, no DB)

```
Vault (CSV / JSON / SQLite / Markdown)
   │  lib/readers.py     — 12 source loaders
   ▼
raw dict
   │  lib/aggregations.py — KPIs, regression window, model mix, sparklines
   │  lib/kanban.py       — ticket composer + column membership
   ▼
agg dict + tickets list
   │  lib/anonymize.public_pass()   — public pass ONLY (zeros job_feed,
   │                                  target_companies, warm_intros;
   │                                  redacts vault paths)
   ▼
   │  lib/render.py       — render_public() / render_private()
   │  templates/*.html    — Jinja2 (base + fleet + kanban + partials/)
   │  lib/svg_charts.py   — inline SVG (line, sparkline, donut, stacked area)
   ▼
HTML + data.json
```

### Critical invariants

- **Privacy is structural, not policy.** `render_public()` calls `anonymize.public_pass(agg)` BEFORE rendering, and `kanban.compose_tickets(..., include_job_feed=False)` is used for public. The public pass physically never reads `vault/.job-feed.db`. Do not weaken this — the two output directories and the `include_job_feed` flag are the whole privacy boundary.
- **Single `lib/render.py`, two functions.** Per the LOCKED DEVIATION comment in [lib/render.py](lib/render.py): do not split into `lib/public_render.py` + `lib/private_render.py`. The shared `_common_context()` and `_build_charts()` would just be re-imported.
- **Inline SVG only, no Chart.js / no CDN.** Page weight stays under 50 KB pre-data; charts survive screenshots. Add new chart types as helpers in [lib/svg_charts.py](lib/svg_charts.py), not via a JS library.
- **Honest empty states.** Every panel must render "what actually happened" copy when data is missing — no spinners, no mock data.
- **Vault paths are absolute from `$HOME`.** `VAULT`, `PRIVATE_OUT`, `EVAL_LAST_RUN`, etc. are defined as module constants in [build.py](build.py). The vault does not live in this repo; tests use fixtures in `tests/fixtures/`.

### Vercel deploy

[vercel.json](vercel.json) overrides Python auto-detection (`"framework": null`, empty build/install commands, `outputDirectory: "."`). The repo is served as a pure static site — Vercel just serves whatever is committed. The Makefile `deploy` target and `build.py` only commit `index.html`, `kanban.html`, `data.json` to keep the deploy surface minimal.

### Tests

55 pytest tests covering readers (with fixture files), aggregations, kanban column membership, anonymize stripping, SVG chart helpers, and a render smoke test. Run a single file: `.venv/bin/pytest tests/test_kanban.py -v`. Fixtures live in `tests/fixtures/`.

Ruff config in `pyproject.toml`: 100-char lines, py312 target, selects E/F/I/W/B/UP.
