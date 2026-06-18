# Fleet Dashboard — Portfolio Alignment & Live-Hero Refresh

**Date:** 2026-06-18
**Status:** Approved (brainstorming → spec)
**Scope:** Visual + behavioral polish of the public + private fleet dashboard so it reads as an extension of the SW portfolio, plus two bug fixes.

## Goal

Make `fleet.seanwinslow.com` feel like it belongs to the same family as the SW portfolio (`sw-ai-pm-portfolio`), and remove three sources of staleness / brokenness:

1. Re-color the dashboard from **amber + purple** to **teal + orange** ("Teal & Ember").
2. Replace the rotating glowing "Asterisk Spark" mascot with a restrained, sharp, mono **chrome-register mark**.
3. Turn the frozen "8 consecutive nights" regression hero into a **live, incident-aware streak**.
4. Fix the **24-hour activity timeline** rendering nothing.
5. Fix the **eval-suite "SKIPPED" pills** overflowing their cards.

Non-goals: no new chart library, no JS framework, no change to the public/private privacy boundary, no kanban redesign, no change to data sources/readers.

## Context: the portfolio family

The portfolio (`sw-ai-pm-portfolio/DESIGN.md`) is **light-mode**: deep teal chrome (`#0A3E42`), warm ambers/oranges (`#7C2D12` stamp, `#FAC775` mid, `#E89060` warm), cream paper (`#FFF9F0`), ink (`#1A1A1E`), on a "pencil-test mounted in a Vercel-grade frame" north star. Its two registers are **hand-drawn warmth on paper** and **restrained mono chrome in the nav** (SW wordmark, sharp corners, JetBrains Mono, wire-service voice).

The fleet dashboard is **dark-mode only** and is *all chrome* (no paper surface). So it maps to the portfolio's **chrome register**, not its paper register. This is why the glowing rotating asterisk is the least-faithful element and why the replacement mark should be sharp/mono/restrained. We are not recreating the portfolio's hand-drawn character here.

## Critical invariant: three-file token sync

Color tokens live in three places that MUST stay in sync (per CLAUDE.md + DESIGN.md):

- `DESIGN.md` (repo root) — front-matter token values + prose.
- `assets/styles.css` `:root` — the consumed CSS custom properties (lines ~5–43).
- `lib/svg_charts.py` — module constants `AMBER`, `PURPLE`, `ALERT`, `OK`, `NEUTRAL`, `GRID`, etc., consumed by every inline-SVG chart.

A color change is only correct when all three are updated together. Tests and the build assert/observe these; the design doc is the contract.

---

## 1. Color system: "Teal & Ember"

### Decision
Only **two hues change**. `ok` green (`#3FB950`) and `alert` red (`#FF5C46`) stay because the data encodes them (healthy dot, failures). The **semantic roles are preserved** so chart logic does not move — only the hex values behind each role change.

| Role (unchanged) | Was | Becomes |
|---|---|---|
| Primary signal · healthy · local-first | amber `#F0B429` | **warm orange `#E89060`** |
| Primary warm, light fill / highlight | `#FFD66B` | **`#F4A672`** |
| Secondary · cloud · regression annotation | purple `#C084FC` | **bright teal `#2DD4BF`** |
| Cool deep (gradient end / deep fills) | — | **deep teal `#0F6E56`** |
| Failures | alert `#FF5C46` | unchanged |
| Healthy status dot | ok `#3FB950` | unchanged |
| Surface undertone (hairlines, glows) | purple-tinted | **teal-tinted** |

### Token changes

**`assets/styles.css` `:root`:**
- `--accent-amber*` family → rename-in-place to the warm orange values OR keep the variable names but change values. **Decision: keep the existing variable names** (`--accent-amber`, `--accent-purple`, etc.) to avoid touching every consumer; change only their *values*. (The names become slightly inaccurate, but the alternative is editing dozens of call sites and the svg output. A short comment in `:root` notes "amber = warm orange, purple = teal as of 2026-06-18.") This keeps the diff small and the backwards-compat aliases (`--accent-blue: var(--accent-purple)` etc.) intact.
  - `--accent-amber: #E89060`, `--accent-amber-soft: rgba(232,144,96,0.35)`
  - `--accent-purple: #2DD4BF`, `--accent-purple-soft: rgba(45,212,191,0.35)`
  - `--accent-cloud: #2DD4BF` (or a teal tint)
- Surface ladder + hairlines: shift purple-tinted rgba to teal-tinted:
  - `--hairline: rgba(45,212,191,0.08)`, `--hairline-strong: rgba(45,212,191,0.18)`
  - `--glow-amber: rgba(232,144,96,0.05)`, `--glow-purple → --glow-teal-ish`: `rgba(45,212,191,0.06)`
  - `--bg-base/raised/recessed`: re-tint from purple-undertone (`#0E0B14`) to a **teal-undertone** dark (e.g. `#0B1012` base, `#121A1B` raised, `#080D0D` recessed) — exact values tuned visually on build.
  - Elevation ring shadows that use `rgba(192,132,252,…)` → `rgba(45,212,191,…)`.
- `--gradient-spark`: `linear-gradient(135deg, #2DD4BF 0%, <mid> 50%, #E89060 100%)` — teal→orange. The exact mid-stop (candidates: `#5EEAD4` light-teal, `#FAC775` warm bridge, or a 2-stop with no mid) is **tuned visually during implementation** to avoid a muddy interpolation midpoint. The token name `--gradient-spark` is retained.
- `--amber-glow` background radial gradients: re-tint to teal+orange.

**`lib/svg_charts.py` constants:**
- `AMBER` → `#E89060`, `PURPLE` → `#2DD4BF`, keep `ALERT`/`OK`, `NEUTRAL`/`GRID`/`axis-text` re-tinted teal-neutral. The model-mix mapping in `lib/render.py` (`_MODEL_MIX_COLORS`: local→AMBER, cloud-anthropic→PURPLE, cloud-gemini→ALERT) is unchanged structurally — it inherits the new hues via the constants.

**`DESIGN.md`:**
- Front-matter `surface`, `accent`, `gradient`, `chart` blocks updated to the new values.
- Prose rewritten: the "warm OLED with purple undertone" → "warm-dark with teal undertone"; the amber→purple gradient narrative → teal→orange; the "Anti-pattern: scattering teal, blue, green…" list updated (teal is now in-palette).

### Acceptance
- No `#C084FC` / `#F0B429` / `192,132,252` / `240,180,41` literals remain in `styles.css`, `svg_charts.py`, or `DESIGN.md` (grep clean).
- Charts render in teal/orange; `ok` green dot + `alert` red preserved.
- Page weight still <50KB pre-data; still inline-SVG only.

---

## 2. Mascot → chrome-register mark

### Decision
Replace the CSS "Asterisk Spark" (`templates/partials/mascot.html` + `.spark*` rules in `styles.css` ~694–726) with a **sharp, static, mono mark**: four corner ticks forming an animation/cel **frame bracket** around a single center dot. The center dot **tints by fleet state** (teal healthy / orange degraded / red down) for a quiet glanceable status nod — but **no rotation, no glow-pulse** (the sci-fi motion is what broke the chrome register). Static by default; trivially reduced-motion safe.

Rationale: references the portfolio's frame numbers (`A-1`), sharp-corner rule, and wire-service chrome. The status-light *function* is already carried by the health-pill dot (`● 5/8 HEALTHY`), so the mark is identity-first.

### Implementation notes
- New `templates/partials/mascot.html`: small inline SVG or pure-CSS frame mark. Keep the `data-state` attribute contract (`healthy|degraded|down`) so `lib/render.py`'s `mascot_state` plumbing is untouched.
- Replace `.spark*` CSS with `.mark*` (or reuse class names) — remove `@keyframes m-spin`, keep an optional subtle reduced-motion-guarded treatment only if it still reads as chrome.
- **The exact glyph is finalized visually:** build → screenshot (Playwright or `make build` + open) → iterate with Sean before locking. ASCII cannot adjudicate the pixels.
- `DESIGN.md` "Identity" section rewritten: drop "The mascot is the brand / if a color isn't in the mascot it doesn't belong." The new framing: the dashboard is the portfolio's **chrome register** — sharp, mono, teal+orange, restrained. The mark is a wire-service frame, not a character.

### Acceptance
- Topbar renders the new mark; `data-state` still drives the dot color.
- No rotating/pulsing animation on the mark (or only a reduced-motion-guarded subtlety that reads as chrome).
- `tests/test_render_smoke.py` still passes (mark renders in both passes).

---

## 3. Hero → incident-aware streak

### Behavior
The hero (`templates/partials/hero_regression.html`) auto-selects one of two states from live data each build:

- **All-clear (default):** big numeral = **nights since the most recent caught regression**, label `NIGHTS CLEAN`. Grows +1 each night. Prose: synth has written every night since the recovery date, eval green, fleet inside governors.
- **Active incident (auto-flip):** when the **trailing** present-but-zero streak (ending at/near `end_date`) is **≥3 nights**, numeral = that streak, label `NIGHTS DARK`, red/degraded styling. Prose: "the eval suite flagged it this morning."

The May incident's proof-of-maturity story is **preserved** via:
- the existing chart annotation band (`compute` already passes `annotation` when `regression_window.nights >= 3`), and
- a small "last caught: `<regression_window.end>`" line in the all-clear prose.

It is simply no longer frozen as the headline.

### Data / logic
New helper in `lib/aggregations.py`:

```
def compute_clean_streak(manifests, end_date) -> dict:
    # Scan present-but-zero nights (concepts_written == 0) — same signal as
    # compute_regression_window, but track the MOST RECENT zero-run, not the longest.
    # Returns:
    #   {
    #     "nights_clean": int,        # days from most-recent-zero-run END to end_date
    #     "last_regression_end": date|None,
    #     "active_incident": bool,    # trailing zero-run ends at/near end_date AND len >= 3
    #     "incident_nights": int,     # length of the trailing zero-run (0 if none)
    #   }
```

Rules:
- A **missing** night (no manifest, `concepts=None`) is a benign MBP-asleep gap and does NOT count as a regression or reset the clean streak (matches `compute_regression_window`, which only iterates existing manifests).
- A **present-but-zero** night (`concepts_written == 0`) is the regression signature.
- `nights_clean` anchors to the **most recent** zero-run end (not the longest). If no zero-run exists in the window, `nights_clean = window length` (60) and is displayed as `60+`.
- `active_incident` is true only when the **most recent present manifest** has `concepts_written == 0` AND the zero-run ending at that latest-manifest date has length ≥3. (If the latest nights are *missing* — no manifest, MBP asleep — the fleet is not "actively failing"; show the clean streak counted from the prior zero-run.) Reuses the `>= 3` threshold already in the template.
- Threshold constant `REGRESSION_THRESHOLD_NIGHTS = 3` defined once and shared.

`lib/render.py` `_common_context` passes the `clean_streak` dict into context alongside the existing `regression_window`. The template chooses state from `clean_streak.active_incident`.

### Template
`hero_regression.html` rewritten to three branches: active-incident (red, `NIGHTS DARK`), all-clear (`NIGHTS CLEAN`, with last-caught line), and the existing no-data fallback. Count-up animation (`data-countup`) reused for the numeral. Honest empty-state copy retained when there is genuinely no synth data.

### Acceptance
- With current fixtures (May regression, recovered), hero shows `NIGHTS CLEAN` with a growing number, not "8 consecutive nights."
- A fixture with a ≥3 trailing zero-run flips to `NIGHTS DARK`.
- A single missing/benign night does not reset the streak.
- New unit tests in `tests/test_aggregations.py` cover: clean streak after recovery, active trailing incident, no-regression (60+), benign-gap tolerance, most-recent-vs-longest anchoring.

---

## 4. 24-hour activity timeline (bug fix)

### Root cause
`assets/styles.css` `.timeline-dot` (~line 648) sets `height: 8px` and `border-radius: 4px` but **no `width`**. The dots are empty absolutely-positioned spans, so they shrink to 0px wide and render invisible (only a faint box-shadow smear). The "8 agents · 6 runs" eyebrow proves the dots exist in the DOM — the composer (`lib/activity_timeline.py`) is correct.

### Fix
Add `width: 8px;` to `.timeline-dot` so it pairs with the existing `height: 8px` + `border-radius: 4px` → circular dots. No template or Python change.

### Acceptance
- Build + screenshot shows dots on lanes that have runs in the 24h window.
- Empty lanes still render (honest "agent exists but was silent" state).
- No regression to `tests/test_activity_timeline.py`.

---

## 5. Eval-suite pills (bug fix)

### Root cause
`assets/styles.css` `.eval-case` (~line 992) grid `grid-template-columns: 10px 18px 80px 1fr auto`. The `1fr` category column has an implicit `minmax(min-content, 1fr)` floor; a long hyphenated category (`output-completeness`, `stale-overweighting`, `source-attribution`) has a min-content width that can't shrink, pushing the `auto` "SKIPPED" pill (the widest pill label) past the card's right edge. Exactly the long-category cards clip.

### Fix
- `.eval-case` grid: category column → `minmax(0, 1fr)` so it can shrink below min-content.
- `.eval-category { min-width: 0; overflow-wrap: anywhere; }` so the long word wraps instead of overflowing.
- `.eval-status-pill { white-space: nowrap; justify-self: end; }` so the pill never breaks internally and never overflows.
- (Optional polish: nudge the card `minmax(280px, 1fr)` / id column if needed after screenshot.)

### Acceptance
- Build + screenshot: no `SKIPPED`/`PASSED`/`FAILED` pill clips its card at any column width (desktop + the 767px breakpoint).
- No regression to `tests/test_render_smoke.py`.

---

## Testing & verification

- Run full `make test` suite; add unit tests for `compute_clean_streak`.
- `make lint` (ruff) clean.
- `make build` produces `index.html` + `kanban.html` + `data.json`; visually verify via screenshots (Playwright MCP or browser) for: topbar mark, hero (clean state), 24h timeline dots, eval pills, chart colors.
- Confirm no em-dashes leak into rendered copy (existing build grep).
- Confirm privacy boundary untouched: public pass still anonymizes; `include_job_feed=False` for public.
- Confirm page weight <50KB pre-data; inline-SVG only; no CDN/JS-lib added.

## Files touched (anticipated)

- `DESIGN.md` — tokens + Identity/Color prose.
- `assets/styles.css` — `:root` tokens, `.timeline-dot`, `.eval-case`/`.eval-category`/`.eval-status-pill`, mascot `.spark`→mark rules.
- `lib/svg_charts.py` — color constants.
- `lib/aggregations.py` — new `compute_clean_streak`, shared threshold constant.
- `lib/render.py` — pass `clean_streak` into context.
- `templates/partials/mascot.html` — new mark.
- `templates/partials/hero_regression.html` — incident-aware branches.
- `tests/test_aggregations.py` — clean-streak tests.

## Open items deferred to implementation (visual tuning, not design)
- Exact mascot glyph (build → screenshot → confirm with Sean).
- Exact gradient mid-stop and surface-ladder dark values (tuned visually).
