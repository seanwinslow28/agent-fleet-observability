# Product

## Register

brand

> Inferred from project context (no live interview). The dashboard is a real operations tool Sean uses daily, but its strategic purpose — and the reason design quality matters — is portfolio: a 30-second recruiter cold-open, a Substack hero image, a Loom walkthrough. Design IS the product. Override to `product` if internal-ops use ever becomes primary; the visual decisions in DESIGN.md don't change either way.

## Users

**Primary — recruiters and hiring managers** doing a 30-second cold-open assessment of Sean's AI/PM credibility. Land on [fleet.seanwinslow.com](https://fleet.seanwinslow.com) from a Substack post, LinkedIn, or a referrer link. They are not vault operators. They will not read the README. They will read the hero, glance the agent grid, and decide whether to keep clicking. Most arrive on desktop; an iPhone screenshot from a recruiter passing the link sideways also has to survive.

**Secondary — Sean himself**, opening the private mirror at `file:///Users/seanwinslow/Sites/agent-fleet-private/index.html` once a morning to verify the fleet ran overnight, check Gemini DR headroom, and triage the kanban. This use is real, daily, and load-bearing on the design even though the audience is one person.

**Tertiary — outside readers** via Substack post 2, GitHub stars, or "look at this" Slack drops. Same job as the recruiter, longer attention span, more likely to read the regression story end-to-end.

The job to be done across all three: **build trust in 30 seconds that Sean ships, operates, and recovers a multi-agent system**.

## Product Purpose

A static, nightly-built observability dashboard for an 8-agent local-first AI fleet. Two render passes (public + private) from one pipeline. The public pass exists to be looked at by people who do not work here; the private pass exists to be looked at by Sean before coffee.

Success looks like:

- One or more attributable recruiter engagements traced back to this artifact.
- The 9-day regression chart reads, on first glance, as "this person caught their own bug" — not as a graph that needs explaining.
- Sean's daily ops triage runs through this surface, not through a folder of CSVs.
- Page weight stays under 50 KB pre-data; cold-cache TTFB under 200ms; the page survives screenshots.

Why this artifact exists at all: most "look at my agent stack" portfolio pieces are tool inventories. This is operational evidence. **Recovered failures are the credibility story.**

## Brand Personality

**Confident, personal, operationally honest.**

- *Confident* — display numerals are 112px Sora; the regression is the hero, not a footnote; there is no "thanks for visiting" copy.
- *Personal* — warm OLED, not cold blue-gray. Asterisk Spark mascot anchors the corner. Empty states speak in Sean's voice ("Synth napped 9 nights this month. MBP was asleep.").
- *Operationally honest* — every number traces to a verifiable file. No spinners that never resolve. No mock data. Empty states describe what actually happened.

Voice in microcopy is plain-language with a slight wink. Not corporate. Not cute. The kind of thing a senior operator types into a postmortem at 6am.

The Asterisk Spark mascot — amber-to-purple gradient sparkle — is the color brand. Every color on every surface traces back to it. If the Spark doesn't have a color, the page doesn't either.

## Anti-references

Things this should specifically NOT look like, in order of how aggressively the design avoids them:

1. **Datadog / Grafana / generic-SaaS observability.** Cold blue-gray surface, 11-color Chart.js noise, monospace-everywhere techbro, "Powered by [tool]" footer. This is the default the visual system is reflexively against — that's why the palette is warm purple-amber OLED, not cold blue.
2. **The hero-metric SaaS template** (big number, gradient accent, three supporting stats in a row of icon-cards). The hero here IS a big number, but rendered with editorial-grade scale and gradient *because the gradient is the mascot's gradient* — not because it's the SaaS template.
3. **"Look at all the tools I use" tile grids.** Every tile on this page is a *running agent* with a last-run timestamp and a real cost, or it's not on the page.
4. **Chart.js with default colors.** 4 chart colors max, all from the mascot palette. No teal-because-it-was-in-the-palette, no green-that's-not-status-green.
5. **Live spinners, polling, "loading…" states.** This is a static nightly snapshot. The page either shows real data or shows an honest empty state. There is no third option.
6. **Modal-first interaction patterns.** This is a read-only dashboard. Anything that wants a modal is wrong about the medium.
7. **The "everything is a card" reflex grid.** Cards exist on this page, but the hero is full-width, the agent grid is tighter than a card grid would be, and the regression chart breathes.

## Design Principles

Strategic, not visual. Use these to make calls when the spec is silent.

1. **Recovered failures are the credibility story.** The 9-night silent regression is the hero, not an annotation. Whenever there's tension between "show off the working system" and "show the honest timeline," show the honest timeline.
2. **Every number traces to a verifiable file.** No aspirational copy. No mocked data. If a panel has nothing to show, it shows "what actually happened" — never a placeholder.
3. **Privacy is structural, not policy.** The public render pass physically cannot read `vault/.job-feed.db`. The two output directories and the `include_job_feed` flag are the entire privacy boundary. Do not weaken this — feature flags or runtime checks would be policy. Files in separate places are structure.
4. **Static beats interactive.** Daily cadence is enough. The build is < 60 seconds cron-fire-to-live; the page is < 50 KB pre-data; charts are inline SVG, not Chart.js. Resist every urge to add a websocket, a poll, or a "live" badge.
5. **The mascot is the brand.** If a color appears on the page, it traces back to the Spark. Amber, purple, the gradient between them — that's the palette. Status green and alert red exist because the data already semantically encodes them. Everything else is monotony broken by the gradient appearing in three load-bearing places (hero numeral, regression band, mascot arms) and nowhere else.

## Accessibility & Inclusion

- **Reduced motion.** All three signature animations (hero count-up, regression band wipe, mascot spin+blink) are wrapped in `prefers-reduced-motion: reduce` and become static. Mascot becomes a static sigil; numerals appear at their final value; the band fills instantly. Tested via OS setting.
- **Mobile floor: 375px.** Single iPhone screenshot must survive. KPI cards collapse 4→2→1; agent grid 4→2→1; kanban 5-col → horizontal scroll on tablet → stacked accordion on mobile.
- **Color is not the only signal.** Status dots always have text adjacent (`● 8/8 HEALTHY`). The regression chart's segments are colored *and* annotated. The kanban filter chips show counts as numerals.
- **WCAG AA on the warm palette.** `#F4EFE6` body text on `#0E0B14` clears 14:1. Secondary `#A89FB0` on the same background clears 6.7:1. Hairlines and disabled states drop below AA on purpose — they're decorative, never load-bearing.
- **No flicker, no autoplay, no carousels.** The page is a static snapshot. Animations exist but are scoped and one-shot.
