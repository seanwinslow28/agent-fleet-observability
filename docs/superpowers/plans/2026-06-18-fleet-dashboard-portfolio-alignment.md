# Fleet Dashboard — Portfolio Alignment & Live-Hero Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the fleet dashboard to a teal+orange "Teal & Ember" palette that reads as an extension of the SW portfolio, replace the glowing asterisk mascot with a restrained chrome-register mark, turn the frozen regression hero into a live incident-aware streak, and fix the invisible 24h-timeline dots and overflowing eval pills.

**Architecture:** Static site generator (Python + Jinja2 + inline SVG). Color tokens are mirrored across three files that must stay in sync: `DESIGN.md` (contract), `assets/styles.css` (`:root`), and `lib/svg_charts.py` (constants). Hero behavior is driven by a new pure-function aggregation `compute_clean_streak` consumed by `templates/partials/hero_regression.html`.

**Tech Stack:** Python 3.12, Jinja2, ruff, pytest, vanilla CSS (no framework), inline SVG (no chart lib). Visual verification via the Playwright MCP browser.

## Global Constraints

- Python 3.12. Run tests with `.venv/bin/pytest`; lint with `make lint` (ruff, 100-char lines, py312, selects E/F/I/W/B/UP).
- **Three-file color sync:** any color change updates `DESIGN.md` + `assets/styles.css` + `lib/svg_charts.py` together. (CLAUDE.md invariant.)
- **Inline SVG only.** No Chart.js, no CDN chart lib, no React/GSAP/Lenis. Total page weight <50KB pre-data.
- **Privacy is structural.** Do not touch the public/private boundary: `render_public()` still calls `anonymize.public_pass(agg)`; `compose_tickets(..., include_job_feed=False)` for public. Do not read `vault/.job-feed.db` in the public path.
- **Honest empty states.** Every panel renders "what actually happened" copy when data is missing — no spinners, no mock data.
- **No em dashes (`—`) or `--` in rendered copy.** The build greps for them. Use commas, colons, semicolons, periods, parentheses.
- **Single `lib/render.py`, two functions** (`render_public`/`render_private`). Do not split (LOCKED DEVIATION).
- All motion wrapped in `prefers-reduced-motion`.

### Color literal mapping (apply identically across all three files)

| Old (amber/purple) | New (Teal & Ember) | Role |
|---|---|---|
| `#F0B429` | `#E89060` | warm orange — primary signal / healthy / local |
| `#FFD66B` | `#F4A672` | warm light fill / gradient mid |
| `240,180,41` (rgb) | `232,144,96` | warm orange in rgba() |
| `#C084FC` | `#2DD4BF` | bright teal — secondary / cloud / annotation |
| `192,132,252` (rgb) | `45,212,191` | teal in rgba() |
| `#A78BFA` (cloud) | `#2DD4BF` | cloud accent → teal |
| `#A89FB0` (text-secondary) | `#A0AEAB` | neutral, re-tinted teal-gray |
| `#6B6478` (text-tertiary) | `#66736F` | neutral, re-tinted teal-gray |
| `#0E0B14` (bg-base) | `#0C100F` | surface, teal undertone |
| `#171320` (bg-raised) | `#141917` | surface, teal undertone |
| `#0A0810` (bg-recessed) | `#080B0A` | surface, teal undertone |
| `--gradient-spark` value | `linear-gradient(135deg, #E89060 0%, #F4A672 40%, #2DD4BF 100%)` | warm→cool ramp |

`#3FB950` (ok green) and `#FF5C46` / `255,92,70` (alert red) are **unchanged** — the data encodes them. Surface dark values and the gradient mid-stop are starting points; final values are tuned on-screen during review.

### Preview-render command (reused by visual-verification steps)

Renders the public dashboard from test fixtures into `/tmp/fleet-preview` with assets copied so relative paths resolve:

```bash
.venv/bin/python -c "
from datetime import date
from pathlib import Path
from tests.test_render_smoke import _data
from lib import aggregations, kanban, render
data = _data()
agg = aggregations.compute_all(data, end=date(2026, 5, 14))
tickets = kanban.compute_columns(
    kanban.compose_tickets(
        {**data, 'lint_reports': {**data['lint_reports'], 'raw_body': ''}},
        include_job_feed=False),
    data['agent_runs'])
render.render_public(agg, tickets, Path('/tmp/fleet-preview'))
print('rendered /tmp/fleet-preview/index.html')
" && cp -r assets /tmp/fleet-preview/assets
```

Then open `file:///tmp/fleet-preview/index.html` with the Playwright MCP browser and screenshot. (Fixture data ends 2026-05-14: a 10-night May regression that recovered 05-11, so the hero renders the **clean-streak** state.)

---

### Task 1: Teal & Ember color system (three-file sync)

**Files:**
- Modify: `lib/svg_charts.py:22-50` (color constants + stack)
- Modify: `assets/styles.css:5-105` (`:root` tokens, base wash, link colors) + `:506` (hero numeral drop-shadow literal)
- Modify: `DESIGN.md:6-77` (front-matter surface/accent/gradient/chart) + prose §Identity/§Color
- Modify: `tests/test_svg_charts.py:71-72,88-89,199` (donut/legend input hexes — for consistency)
- Test: `tests/test_svg_charts.py` (new palette-lock test)

**Interfaces:**
- Consumes: nothing.
- Produces: `svg_charts.AMBER == "#E89060"`, `svg_charts.PURPLE == "#2DD4BF"`, `svg_charts.AMBER_SOFT == "rgba(232,144,96,0.35)"`, `svg_charts.PURPLE_SOFT == "rgba(45,212,191,0.35)"` — relied on by every chart and by `lib/render.py:_MODEL_MIX_COLORS`.

- [ ] **Step 1: Write the failing palette-lock test**

Add to `tests/test_svg_charts.py`:

```python
def test_palette_is_teal_and_ember():
    assert svg_charts.AMBER == "#E89060"
    assert svg_charts.PURPLE == "#2DD4BF"
    assert svg_charts.AMBER_SOFT == "rgba(232,144,96,0.35)"
    assert svg_charts.PURPLE_SOFT == "rgba(45,212,191,0.35)"
    # status colors are data-encoded and must NOT change
    assert svg_charts.OK == "#3FB950"
    assert svg_charts.ALERT == "#FF5C46"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_svg_charts.py::test_palette_is_teal_and_ember -v`
Expected: FAIL (`AMBER` is still `#F0B429`).

- [ ] **Step 3: Recolor `lib/svg_charts.py` constants**

Replace lines 22-34 with:

```python
AMBER = "#E89060"
AMBER_SOFT = "rgba(232,144,96,0.35)"
PURPLE = "#2DD4BF"
PURPLE_SOFT = "rgba(45,212,191,0.35)"
ALERT = "#FF5C46"
OK = "#3FB950"

# Surfaces / text — match DESIGN.md
TEXT = "#F4EFE6"
SECONDARY = "#A0AEAB"
TERTIARY = "#66736F"
PANEL = "#080B0A"          # recessed plate (deeper than raised — charts sit inside)
GRID = "rgba(45,212,191,0.06)"
```

Update the module docstring lines 8-9 to read `AMBER  primary signal · local-first · healthy series (warm orange)` and `PURPLE secondary · cloud spend · regression annotation (teal)`. Leave the `_STACK_*` tag sets unchanged (they reference the constants).

- [ ] **Step 4: Update donut/legend input hexes in the test (consistency)**

In `tests/test_svg_charts.py`, replace `"#F0B429"` → `"#E89060"` and `"#C084FC"` → `"#2DD4BF"` at lines 71-72, 88-89, 199. (These are test *inputs*, not palette assertions; they pass either way, but keep them on-palette.)

- [ ] **Step 5: Run the SVG chart tests**

Run: `.venv/bin/pytest tests/test_svg_charts.py -v`
Expected: PASS (including the new lock test).

- [ ] **Step 6: Recolor `assets/styles.css` `:root` and base**

Apply the Color-literal-mapping table to the whole file. Concretely:
- Lines 7-13: `--bg-base: #0C100F; --bg-raised: #141917; --bg-recessed: #080B0A; --hairline: rgba(45,212,191,0.08); --hairline-strong: rgba(45,212,191,0.18); --glow-amber: rgba(232,144,96,0.05); --glow-purple: rgba(45,212,191,0.06);`
- Lines 16-18: `--text-secondary: #A0AEAB; --text-tertiary: #66736F;` (`--text-primary` unchanged).
- Lines 21-27: `--accent-amber: #E89060; --accent-amber-soft: rgba(232,144,96,0.35); --accent-purple: #2DD4BF; --accent-purple-soft: rgba(45,212,191,0.35); --accent-cloud: #2DD4BF;` (`--accent-ok`, `--accent-alert` unchanged).
- Line 41: `--gradient-spark: linear-gradient(135deg, #E89060 0%, #F4A672 40%, #2DD4BF 100%);`
- Lines 42-43 `--amber-glow`: replace `rgba(240,180,41,0.10)` → `rgba(232,144,96,0.10)` and `rgba(192,132,252,0.08)` → `rgba(45,212,191,0.08)`.
- Lines 68-76 elevation: replace every `rgba(192,132,252,…)` → `rgba(45,212,191,…)` and the hero/hover `rgba(240,180,41,…)` → `rgba(232,144,96,…)`.
- Line ~6 comment: change "warm OLED with purple undertone" → "warm-dark with teal undertone".
- Line ~105 comment "Subtle ambient amber+purple wash" → "Subtle ambient orange+teal wash".
- Then globally replace any remaining `#F0B429`/`#FFD66B`/`#C084FC`/`#A78BFA` and `240,180,41`/`192,132,252` literals per the mapping (notably the `.hero-display .num` drop-shadow at line ~505: `rgba(240,180,41,0.35)` → `rgba(232,144,96,0.35)`).

- [ ] **Step 7: Verify no stale color literals remain in CSS**

Run: `grep -nE '#F0B429|#FFD66B|#C084FC|#A78BFA|240,180,41|192,132,252' assets/styles.css`
Expected: no output. (Spark-mascot pulse literals are removed in Task 5; if any remain here they belong to `.spark*` rules — leave them, Task 5 deletes that block.)

- [ ] **Step 8: Recolor `DESIGN.md` front-matter + prose**

In the front-matter (lines 6-77): apply the mapping to `surface`, `accent`, `gradient`, and `chart` blocks (e.g. `amber: "#E89060"`, `purple: "#2DD4BF"`, `spark: "linear-gradient(135deg, #E89060 0%, #F4A672 40%, #2DD4BF 100%)"`, `grid: "rgba(45,212,191,0.06)"`, hairlines/glows teal-tinted, surfaces per table). In §Color prose: change "warm OLED with a purple undertone" → "warm-dark with a teal undertone", "cold blue-gray" reference stays as the rejected past, "amber→purple gradient" → "orange→teal gradient", and update the anti-pattern color list so teal is in-palette. Leave the §Identity (mascot) prose for Task 5.

- [ ] **Step 9: Verify no stale color literals remain in DESIGN.md**

Run: `grep -nE '#F0B429|#FFD66B|#C084FC|#A78BFA|240,180,41|192,132,252' DESIGN.md`
Expected: no output.

- [ ] **Step 10: Visual check + commit**

Render the preview (Global Constraints command), open `file:///tmp/fleet-preview/index.html` in Playwright, screenshot. Confirm charts/hero/panels read teal+orange, healthy dots still green, failures still red. Then:

```bash
.venv/bin/pytest -q
git add lib/svg_charts.py assets/styles.css DESIGN.md tests/test_svg_charts.py
git commit -m "feat: recolor dashboard to Teal & Ember palette (three-file sync)"
```

---

### Task 2: Fix invisible 24h-timeline dots + overflowing eval pills

**Files:**
- Modify: `assets/styles.css:648-657` (`.timeline-dot`)
- Modify: `assets/styles.css:992-994` (`.eval-case` grid) + `:1026-1027` (`.eval-category`, `.eval-status-pill`)

**Interfaces:**
- Consumes: nothing. Produces: nothing (pure CSS).

- [ ] **Step 1: Fix the timeline dot width**

In `.timeline-dot` (line ~648), add `width: 8px;` immediately after `position: absolute;` so the rule becomes:

```css
.timeline-dot {
  position: absolute;
  width: 8px;
  top: 50%;
  transform: translate(-50%, -50%);
  height: 8px;
  border-radius: 4px;
  background: var(--accent-amber);
  box-shadow: 0 0 6px var(--accent-amber-soft);
  cursor: default;
}
```

- [ ] **Step 2: Fix the eval-case grid + category wrap + pill nowrap**

Change `.eval-case` `grid-template-columns` (line ~994) from `10px 18px 80px 1fr auto` to:

```css
  grid-template-columns: 10px 18px 80px minmax(0, 1fr) auto;
```

Update `.eval-category` (line ~1026) to:

```css
.eval-category { color: var(--text-secondary); font-size: 10px; min-width: 0; overflow-wrap: anywhere; }
```

Update `.eval-status-pill` (line ~1027) by adding `white-space: nowrap;` and `justify-self: end;` to its rule body.

- [ ] **Step 3: Visual verification (no rebuild needed — CSS is linked relatively)**

Open the committed dashboard directly so the edited CSS applies to real data:

```bash
.venv/bin/python -m http.server 8765 >/dev/null 2>&1 &
```

Open `http://localhost:8765/index.html` in Playwright. Confirm: (a) the "24-HOUR ACTIVITY" lanes show visible round dots where runs exist; (b) no `SKIPPED`/`PASSED`/`FAILED` pill clips its card. Resize the browser to 760px wide and re-check the eval grid. Kill the server when done (`kill %1`).

- [ ] **Step 4: Run the suite + commit**

```bash
.venv/bin/pytest -q
git add assets/styles.css
git commit -m "fix: render timeline dots (missing width) and contain eval pills (grid overflow)"
```

---

### Task 3: `compute_clean_streak` aggregation + wiring

**Files:**
- Modify: `lib/aggregations.py` (add constant + function near `compute_regression_window` ~line 195; wire into `compute_all` ~line 295)
- Modify: `lib/render.py:204-234` (`_common_context` — pass `clean_streak`)
- Test: `tests/test_aggregations.py`

**Interfaces:**
- Consumes: `manifests: list[dict]` (each `{"date": date, "concepts_written": int}`), `end: date`.
- Produces: `compute_clean_streak(manifests, end) -> dict` with keys `nights_clean: int`, `last_regression_end: date | None`, `active_incident: bool`, `incident_nights: int`; module constant `REGRESSION_THRESHOLD_NIGHTS = 3`. The hero template (Task 4) consumes `clean_streak` from render context with exactly these keys.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_aggregations.py`:

```python
def test_compute_clean_streak_counts_nights_since_recovery():
    manifests = [{"date": date(2026, 5, d), "concepts_written": 0} for d in range(1, 11)]
    manifests.append({"date": date(2026, 5, 11), "concepts_written": 90})
    manifests.append({"date": date(2026, 5, 13), "concepts_written": 114})
    out = aggregations.compute_clean_streak(manifests, end=date(2026, 5, 20))
    assert out["last_regression_end"] == date(2026, 5, 10)
    assert out["nights_clean"] == 10            # 05-20 minus 05-10
    assert out["active_incident"] is False
    assert out["incident_nights"] == 0


def test_compute_clean_streak_flags_active_trailing_incident():
    manifests = [
        {"date": date(2026, 5, 10), "concepts_written": 50},
        {"date": date(2026, 5, 11), "concepts_written": 0},
        {"date": date(2026, 5, 12), "concepts_written": 0},
        {"date": date(2026, 5, 13), "concepts_written": 0},
    ]
    out = aggregations.compute_clean_streak(manifests, end=date(2026, 5, 13))
    assert out["active_incident"] is True
    assert out["incident_nights"] == 3


def test_compute_clean_streak_no_regression_returns_full_window():
    manifests = [{"date": date(2026, 5, d), "concepts_written": 40 + d} for d in range(1, 15)]
    out = aggregations.compute_clean_streak(manifests, end=date(2026, 5, 20))
    assert out["last_regression_end"] is None
    assert out["nights_clean"] == 60
    assert out["active_incident"] is False


def test_compute_clean_streak_ignores_benign_missing_nights():
    manifests = [
        {"date": date(2026, 5, 9), "concepts_written": 30},
        {"date": date(2026, 5, 10), "concepts_written": 0},    # one dark night
        {"date": date(2026, 5, 13), "concepts_written": 88},   # 11,12 MISSING (asleep)
        {"date": date(2026, 5, 14), "concepts_written": 91},
    ]
    out = aggregations.compute_clean_streak(manifests, end=date(2026, 5, 20))
    assert out["last_regression_end"] == date(2026, 5, 10)
    assert out["active_incident"] is False
    assert out["incident_nights"] == 0


def test_compute_clean_streak_anchors_to_most_recent_not_longest():
    manifests = [{"date": date(2026, 5, d), "concepts_written": 0} for d in range(1, 9)]  # 8 dark (longest)
    manifests.append({"date": date(2026, 5, 9), "concepts_written": 70})
    manifests.append({"date": date(2026, 5, 15), "concepts_written": 0})   # recent single dark
    manifests.append({"date": date(2026, 5, 16), "concepts_written": 80})
    out = aggregations.compute_clean_streak(manifests, end=date(2026, 5, 20))
    assert out["last_regression_end"] == date(2026, 5, 15)
    assert out["nights_clean"] == 5
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_aggregations.py -k clean_streak -v`
Expected: FAIL (`module 'lib.aggregations' has no attribute 'compute_clean_streak'`).

- [ ] **Step 3: Implement the function + constant**

In `lib/aggregations.py`, add a module-level constant near the top of the module body (after imports, ~line 20):

```python
REGRESSION_THRESHOLD_NIGHTS = 3
```

Then add this function immediately after `compute_regression_window` (~line 213):

```python
def compute_clean_streak(manifests: list[dict], end: _date) -> dict:
    """Nights since the most recent caught regression, plus an active-incident flag.

    A 'caught regression' is a run of consecutive present-but-zero nights
    (concepts_written == 0). Missing nights (no manifest) are benign MBP-asleep
    gaps: they neither count as a regression nor reset the streak (mirrors
    compute_regression_window, which only iterates present manifests).

    Returns dict with:
      nights_clean        days from the most-recent zero-run END to `end`
                          (capped at the 60-night window; render shows "60+")
      last_regression_end date of the most-recent dark night, or None
      active_incident     latest present manifest is zero AND the trailing
                          zero-run length >= REGRESSION_THRESHOLD_NIGHTS
      incident_nights     length of that trailing zero-run (0 if none)
    """
    window = 60
    empty = {"nights_clean": window, "last_regression_end": None,
             "active_incident": False, "incident_nights": 0}
    if not manifests:
        return empty
    sorted_m = sorted(manifests, key=lambda m: m["date"])

    # Most-recent dark night (end of the most-recent zero-run).
    last_regression_end: _date | None = None
    for m in sorted_m:
        if m.get("concepts_written", 0) == 0:
            last_regression_end = m["date"]

    if last_regression_end is None:
        return empty

    # Trailing zero-run: consecutive zeros ending at the latest manifest.
    trailing = 0
    for m in reversed(sorted_m):
        if m.get("concepts_written", 0) == 0:
            trailing += 1
        else:
            break

    nights_clean = min(window, max(0, (end - last_regression_end).days))
    return {
        "nights_clean": nights_clean,
        "last_regression_end": last_regression_end,
        "active_incident": trailing >= REGRESSION_THRESHOLD_NIGHTS,
        "incident_nights": trailing,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_aggregations.py -k clean_streak -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Wire into `compute_all`**

In `lib/aggregations.py` `compute_all`, add to the returned dict right after the `"regression_window"` line (~line 295):

```python
        "clean_streak": compute_clean_streak(manifests, end),
```

- [ ] **Step 6: Pass `clean_streak` through render context**

In `lib/render.py` `_common_context`, add after the `"regression_window": agg["regression_window"],` line (~line 215):

```python
        "clean_streak": agg.get("clean_streak", {
            "nights_clean": 60, "last_regression_end": None,
            "active_incident": False, "incident_nights": 0,
        }),
```

- [ ] **Step 7: Run the full suite to confirm nothing regressed**

Run: `.venv/bin/pytest -q`
Expected: PASS (all existing tests + 5 new).

- [ ] **Step 8: Commit**

```bash
git add lib/aggregations.py lib/render.py tests/test_aggregations.py
git commit -m "feat: compute_clean_streak (nights since last caught regression) + render wiring"
```

---

### Task 4: Incident-aware hero template

**Files:**
- Modify: `templates/partials/hero_regression.html` (full rewrite of the branch logic)
- Modify: `assets/styles.css` (add `.hero-display--incident .num` override after line ~507)

**Interfaces:**
- Consumes: `clean_streak` (from Task 3: `nights_clean`, `last_regression_end`, `active_incident`, `incident_nights`), plus existing `hero_svg`, `regression_window`, `end_date`.
- Produces: nothing downstream.

- [ ] **Step 1: Rewrite `templates/partials/hero_regression.html`**

Replace the entire file with:

```jinja
{# Hero — incident-aware streak. Spark Console.
   Vars: hero_svg (rendered string), clean_streak {nights_clean, last_regression_end,
         active_incident, incident_nights}, regression_window {start,end,nights}, end_date #}
{% set cs = clean_streak %}
<section class="hero-plate" aria-labelledby="hero-headline">
  <div class="eyebrow">Vault Synthesizer · concepts written per night · 60 nights</div>

  {% if cs.active_incident %}
    <h1 class="hero-display hero-display--incident" id="hero-headline">
      <span class="num" data-countup="{{ cs.incident_nights }}" aria-label="{{ cs.incident_nights }}">{{ cs.incident_nights }}</span>
      <span class="label">nights dark</span>
    </h1>
    <p class="hero-prose">
      The synthesizer has written <strong>zero concepts</strong> for {{ cs.incident_nights }} nights running.
      The vault-synthesizer <strong>eval suite</strong> flagged it. This banner stays red until the
      synthesizer recovers, so the dashboard surfaces the regression instead of hiding it.
    </p>
  {% elif cs.last_regression_end %}
    <h1 class="hero-display" id="hero-headline">
      <span class="num" data-countup="{{ cs.nights_clean }}" aria-label="{{ cs.nights_clean }}">{{ cs.nights_clean }}{% if cs.nights_clean >= 60 %}+{% endif %}</span>
      <span class="label">nights clean</span>
    </h1>
    <p class="hero-prose">
      The synthesizer has written every night since the last dark night on {{ cs.last_regression_end }}.
      The <strong>eval suite</strong> runs each morning and the fleet stays inside its governors. The
      worst regression it has caught is preserved on the chart below.
    </p>
  {% else %}
    <h1 class="hero-display" id="hero-headline">
      <span class="num" data-countup="{{ cs.nights_clean }}" aria-label="{{ cs.nights_clean }}">{{ cs.nights_clean }}{% if cs.nights_clean >= 60 %}+{% endif %}</span>
      <span class="label">nights clean</span>
    </h1>
    <p class="hero-prose">
      No regression in the last 60 nights. The eval suite ran every morning, the synthesizer wrote,
      and the fleet stayed inside its governors.
    </p>
  {% endif %}

  <div class="hero-chart-wrap">
    {{ hero_svg|safe }}
  </div>
</section>
```

(Note: no em dashes in the copy — verified against the build grep.)

- [ ] **Step 2: Add the incident-state numeral override to CSS**

After `.hero-display .label { ... }` (line ~516) in `assets/styles.css`, add:

```css
.hero-display--incident .num {
  background: none;
  -webkit-text-fill-color: var(--accent-alert);
  color: var(--accent-alert);
  filter: drop-shadow(0 0 24px rgba(255,92,70,0.4));
}
```

- [ ] **Step 3: Verify the clean-streak render**

Run the preview-render command (Global Constraints). Open `file:///tmp/fleet-preview/index.html` in Playwright, screenshot the hero. Expected: headline reads `4 NIGHTS CLEAN` (fixture end 05-14 minus last dark night 05-10), gradient numeral, prose references 2026-05-10, no "8 consecutive nights".

- [ ] **Step 4: Verify the incident render (doctored manifests)**

```bash
.venv/bin/python -c "
from datetime import date
from pathlib import Path
from tests.test_render_smoke import _data
from lib import aggregations, kanban, render
data = _data()
# Force a trailing 3-night dark run ending at the window end.
data['synth_manifests'] = [
    {'date': date(2026,5,12), 'concepts_written': 0},
    {'date': date(2026,5,13), 'concepts_written': 0},
    {'date': date(2026,5,14), 'concepts_written': 0},
]
agg = aggregations.compute_all(data, end=date(2026,5,14))
tickets = kanban.compute_columns(kanban.compose_tickets({**data,'lint_reports':{**data['lint_reports'],'raw_body':''}}, include_job_feed=False), data['agent_runs'])
render.render_public(agg, tickets, Path('/tmp/fleet-incident'))
print('rendered /tmp/fleet-incident')
" && cp -r assets /tmp/fleet-incident/assets
```

Open `file:///tmp/fleet-incident/index.html` in Playwright. Expected: headline reads `3 NIGHTS DARK` in red, prose says the eval suite flagged it.

- [ ] **Step 5: Run the suite + commit**

```bash
.venv/bin/pytest -q
git add templates/partials/hero_regression.html assets/styles.css
git commit -m "feat: incident-aware live streak hero (NIGHTS CLEAN / NIGHTS DARK)"
```

---

### Task 5: Chrome-register mascot mark + DESIGN.md Identity rewrite

**Files:**
- Modify: `templates/partials/mascot.html` (replace asterisk markup with frame-bracket mark)
- Modify: `assets/styles.css:676-726` (replace `.spark*` rules + `@keyframes m-spin/m-blink/spark-pulse-*` with `.mark*`) and `:1069-1071` (reduced-motion block referencing `.spark`)
- Modify: `DESIGN.md` §Identity prose
- Test: existing `tests/test_render_smoke.py` (must still pass)

**Interfaces:**
- Consumes: `mascot_state` (`healthy|degraded|down`) from render context — keep the `data-state` attribute contract so `lib/render.py` is untouched.
- Produces: nothing downstream.

- [ ] **Step 1: Replace the mascot markup**

Replace `templates/partials/mascot.html` with a sharp frame-bracket mark (inline SVG, 32px, sharp corners; center dot tints by state via CSS):

```jinja
{# Chrome-register mark — animation/cel frame bracket around a status dot.
   `data-state` (healthy|degraded|down) tints the center dot via CSS.
   Static by default (no rotation/pulse); the health pill carries live status. #}
<div class="mark" data-state="{{ mascot_state | default('healthy') }}" aria-hidden="true">
  <svg viewBox="0 0 32 32" width="32" height="32" fill="none">
    <path class="mark-frame" d="M3 9V3h6M23 3h6v6M29 23v6h-6M9 29H3v-6"
          stroke="var(--accent-purple)" stroke-width="2" stroke-linecap="square"/>
    <rect class="mark-dot" x="13" y="13" width="6" height="6" rx="1"/>
  </svg>
</div>
```

- [ ] **Step 2: Replace the mascot CSS**

In `assets/styles.css`, delete the `@keyframes m-spin`, `@keyframes m-blink`, `@keyframes spark-pulse-healthy/degraded/down` blocks and all `.spark*` rules (lines ~677-726). Replace with:

```css
/* ───── Chrome-register mark — sharp frame + status dot, static ───── */
.mark { width: 32px; height: 32px; display: inline-flex; flex-shrink: 0; }
.mark svg { display: block; }
.mark .mark-frame { stroke: var(--accent-purple); }
.mark .mark-dot { fill: var(--accent-purple); }
.mark[data-state="degraded"] .mark-frame,
.mark[data-state="degraded"] .mark-dot { stroke: var(--accent-amber); fill: var(--accent-amber); }
.mark[data-state="down"] .mark-frame,
.mark[data-state="down"] .mark-dot { stroke: var(--accent-alert); fill: var(--accent-alert); }
```

(`--accent-purple` is teal post-Task-1; healthy = teal frame + teal dot, degraded = orange, down = red.) Then in the `prefers-reduced-motion` block (~line 1069), remove the now-dead `.spark .arms, .spark .core, .spark .eye { animation: none !important; }` lines (the mark has no animation, so nothing is needed there).

- [ ] **Step 3: Rewrite the DESIGN.md Identity section**

In `DESIGN.md` §Identity (lines ~83-87) and the line-81 summary, replace the "mascot is the brand / if a color is on the page it's because it's in the mascot" framing with the chrome-register framing: the dashboard is the SW portfolio's **chrome register** — sharp corners, JetBrains Mono wire-service labels, restrained teal+orange on warm-dark. The top-left mark is a sharp animation/cel **frame** (a nod to the portfolio's `A-1` frame numbers), not a character. Color discipline now traces to the four working colors (teal, orange, alert-red, status-green), not to a mascot. Update the closing line 138 ("does the Spark mascot have this color?") to reference the four-color palette instead.

- [ ] **Step 4: Verify render + reduced-motion**

Run the preview-render command (Global Constraints). Open `file:///tmp/fleet-preview/index.html` in Playwright, screenshot the topbar. Expected: a sharp teal frame-bracket with a teal center dot replaces the glowing asterisk; nothing rotates. Confirm no leftover `.spark` selectors: `grep -n '\.spark' assets/styles.css` → no output.

- [ ] **Step 5: Run the smoke test + suite, then commit**

```bash
.venv/bin/pytest -q
git add templates/partials/mascot.html assets/styles.css DESIGN.md
git commit -m "feat: replace asterisk mascot with chrome-register frame mark + update DESIGN.md identity"
```

---

## Self-Review

**Spec coverage:**
- §1 Color system → Task 1 (three-file sync, mapping table, lock test). ✓
- §2 Mascot → Task 5 (frame mark + Identity rewrite). ✓
- §3 Hero incident-aware streak → Task 3 (logic) + Task 4 (template). ✓
- §4 24h timeline bug → Task 2 step 1. ✓
- §5 Eval pills bug → Task 2 step 2. ✓
- Three-file sync invariant → Task 1 + grep guards. ✓
- Privacy / inline-SVG / <50KB / no-em-dash / single-render.py → Global Constraints, untouched by all tasks. ✓
- New unit tests for `compute_clean_streak` (5 cases incl. benign-gap + most-recent-vs-longest) → Task 3. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; verification commands are concrete with expected output. Surface dark values + gradient mid-stop are explicitly labeled "tuned on-screen during review," with concrete starting values given (not placeholders). ✓

**Type consistency:** `compute_clean_streak(manifests, end) -> dict` keys (`nights_clean`, `last_regression_end`, `active_incident`, `incident_nights`) are defined in Task 3 and consumed verbatim in Task 4's template and Task 3's render-context default. `REGRESSION_THRESHOLD_NIGHTS` defined once in Task 3. `svg_charts.AMBER`/`PURPLE` values asserted in Task 1 match the mapping table. `data-state` contract preserved in Task 5. ✓
