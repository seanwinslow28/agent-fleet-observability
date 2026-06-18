---
name: Agent Fleet Observability · Spark Console
version: 1.0
mode: dark
spec: https://github.com/google/design-md
surface:
  base:        "#0C100F"
  raised:      "#141917"
  recessed:    "#080B0A"
  hairline:    "rgba(45,212,191,0.08)"
  hairline-strong: "rgba(45,212,191,0.18)"
  glow-amber:  "rgba(232,144,96,0.05)"
  glow-purple: "rgba(45,212,191,0.06)"
text:
  primary:     "#F4EFE6"
  secondary:   "#A0AEAB"
  tertiary:    "#66736F"
accent:
  amber:       "#E89060"
  amber-soft:  "rgba(232,144,96,0.35)"
  purple:      "#2DD4BF"
  purple-soft: "rgba(45,212,191,0.35)"
  ok:          "#3FB950"
  alert:       "#FF5C46"
  cloud:       "#2DD4BF"
gradient:
  spark:       "linear-gradient(135deg, #E89060 0%, #F4A672 40%, #2DD4BF 100%)"
  amber-glow:  "radial-gradient(ellipse at center, rgba(232,144,96,0.18), transparent 60%)"
typography:
  display:
    family: "Sora"
    weight: 700
    size:   "clamp(56px, 9vw, 112px)"
    tracking: "-0.035em"
    leading:  "0.95"
  h1:
    family: "Sora"
    weight: 600
    size:   "20px"
    tracking: "-0.01em"
  body:
    family: "Sora"
    weight: 400
    size:   "14px"
    leading:  "1.55"
  eyebrow:
    family: "JetBrains Mono"
    weight: 500
    size:   "10px"
    tracking: "0.08em"
    transform: "uppercase"
  mono:
    family: "JetBrains Mono"
    weight: 500
    features: "tnum"
spacing:   { 1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 40, 7: 64, 8: 96 }
radius:    { sm: 4, md: 8, lg: 14, hero: 20, pill: 999 }
elevation:
  panel: "0 1px 0 rgba(244,239,230,0.04) inset, 0 0 0 1px rgba(45,212,191,0.08), 0 8px 24px -12px rgba(0,0,0,0.6)"
  hero:  "0 1px 0 rgba(244,239,230,0.06) inset, 0 0 0 1px rgba(45,212,191,0.12), 0 40px 80px -40px rgba(232,144,96,0.25)"
  hover: "0 1px 0 rgba(244,239,230,0.06) inset, 0 0 0 1px rgba(232,144,96,0.20), 0 12px 32px -12px rgba(0,0,0,0.7)"
motion:
  ease-out:    "cubic-bezier(0.23, 1, 0.32, 1)"
  ease-spark:  "cubic-bezier(0.34, 1.56, 0.64, 1)"
  ease-in-out: "cubic-bezier(0.77, 0, 0.175, 1)"
  fast: "160ms"
  base: "240ms"
  slow: "600ms"
  hero: "800ms"
chart:
  primary:   "#E89060"  # amber — local-first share, healthy (warm orange)
  secondary: "#2DD4BF"  # purple — cloud spend, regression annotation (teal)
  alert:     "#FF5C46"  # red — failures, regression band
  neutral:   "#A0AEAB"  # teal-tinted gray — context series
  grid:      "rgba(45,212,191,0.06)"
  axis-text: "#66736F"
---

# Agent Fleet Observability · Spark Console

> Design system for a static observability dashboard rendered nightly on a Mac Mini. Dark mode only. Anchored by the Asterisk Spark mascot whose colors are the brand.

## Identity

The mascot is the brand. Every appearance of color on this page traces back to the Spark — amber to purple, gradient or solid. The page reads as one designed object: the mascot in the top-left, the gradient on the hero numeral, the amber pulse on healthy agents, the purple chip on private mode. **If a color is on the page, it's because it's in the mascot.**

Anti-pattern: scattering accent colors (blue, green, red, purple, amber) at equal weight across charts. The current build does this and reads as Chart.js noise. Spark Console collapses to four working colors: **amber** (warm orange, primary signal, healthy, local), **purple** (teal, secondary, cloud, regression annotation), **alert-red** (failures only), **status-green** (the existing `healthy` dot — kept because the data already encodes it).

## Color

**Surface ladder** is warm-dark with a teal undertone. Replaces the previous cold blue-gray (`#0a0d12` → `#0C100F`). Hairlines are teal-tinted, not gray. Text is warm off-white (`#F4EFE6`), not clinical white (`#e6edf3`).

**Why warm:** the dashboard opens at 06:00. A blue-cold UI reads as Datadog/Grafana SaaS at that hour. Warm reads as a personal operations console. Same data, completely different feel.

**The orange→teal gradient** is a single token (`--gradient-spark`) — a 135° three-stop ramp (`#E89060 → #F4A672 → #2DD4BF`) used in three load-bearing places: (1) the hero numeral via `background-clip: text`, (2) the regression-window annotation band, (3) the mascot arms. Hero and mascot share the exact same gradient so the page reads as one designed object. Nothing else gets the gradient — its scarcity is what makes it feel intentional.

## Typography

`Sora` across the board (display, headings, body). `JetBrains Mono` for all numerals, eyebrow labels, and telemetry — anything that should look measured. **Inter dropped entirely** — it was the AI-slop signal.

**Display numeral** is Sora 700 at `clamp(56px, 9vw, 112px)` with `letter-spacing: -0.035em` and `line-height: 0.95`. Used exactly once per page: the regression-night count in the hero. Editorial-grade scale on a single number that carries the story.

Tabular numerals everywhere mono is used (`font-variant-numeric: tabular-nums`) so 9-day spans, dollar amounts, and timestamps don't shift width.

## Surfaces & shape

- Panel radius: **14px** (raised from 8px). Larger radius reads less utilitarian, more designed.
- Hero plate radius: **20px**.
- Panel elevation uses **three layered shadows**: 1px inset highlight + 1px purple ring + 8px outer drop. This is the depth recipe — single `shadow-lg` was the prior slop signal.
- Hover state for interactive cards: ring color shifts from purple-soft to amber-soft. The hover *feels* like the Spark looked at the card.

## Motion

Three signature moments, each with one purpose:

1. **Hero count-up** — the regression-night numeral counts 0 → N over 800ms on first viewport entry. Re-enacts the silent regression building up.
2. **Regression band wipe** — `clip-path: inset(0 100% 0 0) → inset(0 0 0 0)` over 1200ms, fires after the count-up settles. The band fills in left-to-right exactly like the silent nights accumulated.
3. **Spark pulse tied to fleet state** — the mascot core's `box-shadow` slow-pulses amber when healthy, purple when degraded, red when down. Mascot becomes a glanceable status light.

Plus the invisible-correctness layer per Emil Kowalski's rules: `:active` press = `scale(0.97)` 160ms ease-out; stagger reveals 50ms between siblings; kanban filter uses blur+desaturate (not `display:none`) so spatial memory is preserved; all motion wrapped in `prefers-reduced-motion`.

**No GSAP, no Lenis, no React.** Total motion code under 100 LOC of vanilla JS in `assets/motion.js`. Honors the static-site philosophy and the <50KB page-weight budget.

## Charts

Single rule: **four colors max per chart**, drawn from the chart palette (`amber`, `purple`, `alert`, `neutral`). No teal, no blue, no green-other-than-status-dots, no GitHub red. The cost-trend stacked area collapses from 11 agent-colors to 3 semantic bands (local · cloud-anthropic · cloud-gemini). The model-mix donut shows the same three.

Inline SVG only — no Chart.js, no CDN. Charts consume tokens from this file via `lib/svg_charts.py`. Grid lines are `rgba(45,212,191,0.06)`. Axis labels are `JetBrains Mono` 10px in `#66736F`.

## Honest empty states

Microcopy is locked per `docs/2026-05-15-agent-fleet-dashboard-design.md` §5e. Never "No data." Always "Synth napped 9 nights this month. MBP was asleep."

## What this file is for

This is the machine-readable contract. `assets/styles.css` consumes the tokens; `lib/svg_charts.py` consumes the chart palette; future Claude sessions read the front-matter to stay on-brand. When you change a token here, it changes everywhere — that's the point.

When in doubt: **does the Spark mascot have this color? If no, don't use it.**
