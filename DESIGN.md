---
name: Agent Fleet Observability · Dailies Desk
version: 2.0
modes: [light, dark]
default-mode: system
spec: https://github.com/google/design-md
inherits: seanwinslow.com DESIGN.md §1 (inherited rules), §2 (palette), §4 (type)
color:
  light:
    ground:      "#FBF6EC"   # cream; the page
    raised:      "#FFFAF1"   # the card sheet
    sunk:        "#F3ECDF"   # meters, banner, recessed wells
    ink:         "#2A2622"   # graphite; text, Verified stamp, primary button
    sub:         "#6E655B"   # secondary text
    mark:        "#2F5D7C"   # drafting ink; marks only (see Accent)
    brick:       "#9C3B2A"   # Blocked and failed checks only
    rule:        "rgba(42,38,34,.12)"
    rule-strong: "rgba(42,38,34,.24)"
  dark:
    ground:      "#191714"   # warm charcoal
    raised:      "#221F1B"
    sunk:        "#13110F"
    ink:         "#F2EBDD"   # cream
    sub:         "#8F867A"
    mark:        "#6BA3C9"   # lifted ink
    brick:       "#D9826F"
    rule:        "rgba(242,235,221,.10)"
    rule-strong: "rgba(242,235,221,.22)"
typography:
  display: { family: "Anybody", axes: "wdth 50..150, wght 100..900", use: "desk headline, card question, lane stamps, needs-you counts. Nothing else." }
  body:    { family: "Schibsted Grotesk", weights: "400, 600, 700", use: "everything else, including every label, button and number" }
  numerals: "tabular-nums on times, money, durations and counts"
  scale-rem: { xs: 0.75, sm: 0.8125, base: 0.875, md: 1, lg: 1.125, xl: 1.3125, card-question: 1.625 }
  headline: { laptop: "clamp(2rem, 4.4vw, 3.375rem)", phone: "clamp(2.375rem, 11vw, 4rem)" }
space-px: [4, 8, 12, 16, 20, 24, 28, 32, 40]
radius: { all: 0, exception: "dots and the heartbeat are circles" }
shadow:
  sheet: "0 1px 0 var(--rule), 0 18px 40px -28px rgba(42,38,34,.35)"
motion:
  ease: "cubic-bezier(.22,1,.36,1)"   # ease-out-quint; no bounce, no elastic
  ui: "150–200ms"
  night-strip: "once per night, about 1.6s total"
breakpoint: { phone: "< 900px" }
---

# DESIGN.md · Dailies Desk

**Status:** agreed by Sean, 2026-10-04. This is the dashboard's design authority for both modes.
**Replaces** the "Spark Console" system (teal and amber on OLED, Sora, the sparkle mascot), which left with the old dashboard and lives in git history.
**Source:** variant A of the dashboard-design prototype in Sean's private brain repo, with variant C's phone headline. Colour and type come from `seanwinslow.com`'s design system, so the dashboard and the site read as one hand.

## 1 · Who it's for, and when

Sean opens it at about 6 a.m., most often on his phone, sometimes on the laptop, before the day job starts. He has a few minutes. He wants to know what ran overnight, what needs him, and to work through each finished piece of work at about three minutes a card. The public showcase replays the same screens for visitors, read-only.

That scene sets every rule below: **calm and legible beats dense.** Morning light varies, so the theme follows the device setting, and both grounds are first-class.

## 2 · Principles

1. **Shape before colour.** Every state reads in greyscale. Colour confirms; it never carries meaning alone.
2. **Unverified-done never looks like Verified.** Verified is the only solid stamp. Anything that finished without proof is an outline.
3. **One thing at a time.** One card, one question, one primary action. Everything else waits under More details.
4. **The evidence is the decoration.** No ornament, illustration or mascot. The only drawing on the page is the night strip, and it's data.
5. **Real and dated** (inherited). Every figure is real, current and named. A stale number is a bug.
6. **No pure black or white** (inherited). Every neutral carries the warm hue.

## 3 · Colour

Strategy: **restrained.** Warm neutrals, graphite ink, and two signal colours that each mean exactly one thing.

| Token | Light | Dark | Means |
|---|---|---|---|
| `ground` | `#FBF6EC` | `#191714` | the page, with a 3px dot grain at `rule` strength |
| `raised` | `#FFFAF1` | `#221F1B` | the card sheet |
| `sunk` | `#F3ECDF` | `#13110F` | meters, banner, recessed wells |
| `ink` | `#2A2622` | `#F2EBDD` | text, solid marks, primary buttons |
| `sub` | `#6E655B` | `#8F867A` | secondary text |
| `mark` | `#2F5D7C` | `#6BA3C9` | drafting ink: "your move" and the mark grammar |
| `brick` | `#9C3B2A` | `#D9826F` | Blocked, and a failed check. Nothing else. |

**Accent (drafting ink) appears only in this exhaustive list:** the current-tab underline, the hover underline draw-in, the keyboard focus mark, the underline on the needs-you count in the desk headline, and the Needs-decision stamp. It is never a fill, never a background wash, never body text.

**Contrast (WCAG 2.1), measured:**

| Pair | Light on ground / raised / sunk | Dark on ground / raised / sunk |
|---|---|---|
| ink | 13.9 / 14.4 / 12.8 | 15.1 / 13.8 / 15.9 |
| sub | 5.3 / 5.5 / 4.9 | 5.0 / 4.6 / 5.3 |
| mark | 6.6 / 6.8 / 6.0 | 6.6 / 6.0 / 6.9 |
| brick | 6.3 / 6.6 / 5.8 | 6.3 / 5.8 / 6.6 |

Every pair clears AA for body text. `sub` on dark `raised` (4.6) is the floor: don't put `sub` below 14px on the card sheet in dark mode. Hairlines (`rule`) are decorative and exempt.

## 4 · Type

- **Anybody** carries four things only: the desk headline (weight 900, uppercase, width ~105%), the card question (800, sentence case, width ~92%), lane stamps (800, uppercase, width ~85%, tracked 0.08em), and the needs-you counts (800). It never sets a button, a label, body text or a table.
- **Schibsted Grotesk** sets everything else. Section labels are sentence case at `md`, weight 600, in `ink`; **no tracked all-caps eyebrows** above sections (the prototype used them, and they're dropped here).
- Fixed rem scale (§ frontmatter), ratio about 1.15. Only the desk headline is fluid.
- `font-variant-numeric: tabular-nums` on every time, sum of money, duration and count, so columns of numbers line up. Not on host names or prose.
- `text-wrap: balance` on the headline and card question; `text-wrap: pretty` on answers. Answers cap at 65ch.

## 5 · The lane grammar

Four lanes, each a rubber stamp: Anybody 800 uppercase in a 1.5px box, rotated −1.5°, 6px × 9px padding.

| Lane | Stamp | Why |
|---|---|---|
| **Verified** | solid `ink` fill, `ground` text | the only solid stamp: proven |
| **Unverified done** | dashed `ink` outline, no fill | finished, not proven; must never pass for Verified |
| **Blocked** | solid `brick` outline, `brick` text | the only red on the page |
| **Needs decision** | `mark` outline, `mark` text | drafting ink means "your move" |

A **calibration** attempt adds the word "calibration" after the lane name in Schibsted 11px, inside the same stamp. A ticket that never started ("night ran out", "night budget spent") gets no stamp: it's a line of `sub` text under the strip.

**Check dots** (one per check, 10px circles, 1.5px stroke, in check order): pass is solid `ink`; unconfirmed is a dashed outline; fail is solid `brick`; skipped is a `rule-strong` outline. Hover or long-press shows the check's name.

**Evidence marks** in the claim map: ✓ quote found (`ink`), ≠ quote not on the page (`brick`), ? page didn't load (`ink`). Each has a text label for screen readers.

## 6 · Layout

### Desk (home)

- **Laptop (≥ 900px):** a three-column grid, `220px | 1fr | 240px`, gap 40px, max width 1280px, padding 28px 32px. Left: Health, Spend (meter against the night ceiling), Judge. Centre: the headline "Good morning." with a one-line lede ("**8 things** need you, about 9 minutes." plus the night's biggest anomaly), then the night strip, then not-started tickets. Right: Needs you (four stamps with counts) and the **Start review** button. Below the centre: Tonight's queue.
- **Phone (< 900px):** one column, in this order: the big headline **"8 things need you"** (count in words the reader can say aloud), the lede, a full-width **Begin** button, the night strip, needs-you, tonight's queue, then health, spend and judge last.
- **The night strip:** one row per ticket, in start order: time (tabular, `sub`), the question, then a track. A 1.5px `ink` line runs through three beads labelled preflight, agent and checker with their minutes, ending in the lane stamp. On a phone the stamp drops to its own line under the track.
- Top bar: "SWCB desk" wordmark (Anybody 900 uppercase), tabs Desk · Review · Queue · Brain · Evals · Agents (current tab underlined in `mark`), date and ramp day on the right.

### Review card

- One sheet, max width 680px, centred, padding 28px 30px (22px 18px on a phone), `raised` with the one `sheet` shadow. Square corners. No card ever nests inside another.
- Above the sheet: Previous · "2 of 4 · about 3 minutes each" · Next.
- Inside, top to bottom: the stamp and the **Listen** button; the question; "What happened" (check dots beside one plain sentence, between two hairlines); Answer; Evidence (claim, mark, source host per row, dotted rules); the spend line (`sub`, tabular); **More details** (native `<details>`: worker, run log, drew on, every check with its blind spot, the agent's own summary last); then the label step.
- **Label step:** a 1.5px `ink` rule, step bars (18px × 3px), the question in Schibsted 600 at `lg`, a one-line explainer in `sub`, then **Yes** (ink fill) and **No** (outline), full width and equal, at least 48px tall. Send back and Drop sit below as text links.
- Needs-decision, watchdog proposal, note-sample and threshold cards use the same sheet with a Needs-decision stamp, one plain question, big Yes / No, and "ask me in 3 weeks" as a link.

## 7 · Components and states

| Component | Default | Hover | Focus | Active | Disabled | Loading |
|---|---|---|---|---|---|---|
| Primary button | `ink` fill, `ground` text | underline draws in under the label (150ms) | 2px `mark` outline, 2px offset | 98% scale | 35% opacity, no hover | label stays; a 2px `sub` bar fills along the bottom edge |
| Outline button | 1.5px `ink` border | same draw-in | same | same | same | same |
| Text link | `sub`, underlined, 3px offset | `ink` | same | — | — | — |
| Listen | outline button | same | same | toggles to Pause | "No audio" with the reason in its title, when a check failed or the punctuation check failed | — |
| Tab | `sub` | `ink` | same | — | — | — |

- **Executing a draft** (send, spend, publish) is the only irreversible action. Its card states exactly what will happen above the button, and execution takes one confirm tap on both devices: the button becomes "Confirm: send to …" in `brick` for 5 seconds, then reverts.
- **Start screen and end screen:** the start screen is the desk. When the queue is empty the review view says **"Nothing needs you"** in the desk headline style, with tonight's queue below. No illustration.
- **Loading:** the dashboard reads files on the Mini and renders on load, so there's no spinner. If a file can't be read, the section says which file and when it was last good, in `sub`.
- **Public replay banner:** a full-width strip at the very top on `sunk` with a `rule-strong` bottom hairline, centred 13px `sub` text: "Replay of a real night, 2026-10-19, sanitized before publishing. Nothing here can be clicked into action." In public mode every action button is absent, not disabled.

## 8 · Motion

There are two kinds of motion, and nothing else moves.

1. **The night strip, once per night.** The first time the desk opens after a night's run finishes, each row's line draws left to right (scaleX from 0, 900ms) with rows staggered 220ms apart; each bead fades and scales up from 0.4 as the line reaches it (420ms, 240ms apart); the stamp lands last. About 1.6s for a four-ticket night. Every later visit that day shows the finished strip instantly, including the back button. "Seen" is keyed to the night's date in `localStorage`; if storage is unavailable, show it finished. The strip's final state is the default render, and the animation only plays over it, so a hidden tab or a headless capture never shows a blank strip.
2. **The mark grammar** (inherited): the hover underline draws in (150ms); the current-tab underline sits at full weight; focus is instant. Card-to-card is a 200ms crossfade.

All easing is ease-out-quint. No bounce, no elastic, no page-load choreography, no idle loops. **Reduced motion:** nothing animates; the strip renders finished, the underline appears instantly, cards swap without a fade.

## 9 · Accessibility

- Colour never carries meaning alone (§2, §5): stamps differ by fill and stroke style, dots by fill and dash, evidence by glyph.
- Touch targets at least 44 × 44px on a phone; Yes / No at least 48px tall.
- Every interactive element shows the `mark` focus outline.
- The check dots carry `aria-label` with the check name and result; evidence glyphs carry their text label.
- Kokoro narration is a separate audio file; nothing in the visual design depends on it.

## 10 · Bans

On top of the inherited rules (no pure black or white, real and dated figures, no stock imagery or placeholder copy):

- No side-stripe accent borders, gradient text, glass blur or glow.
- No tracked uppercase eyebrows above sections; no 01 / 02 / 03 section numbers.
- No hero-metric tiles or identical card grids. The desk is columns of lines, not tiles.
- No lane colour beyond the two signals. Verified and Unverified-done are both `ink`, told apart by shape.
- No mascot, illustration or cursor effect.
- No modals. Everything happens inline on the card.

## 11 · Not designed yet

The Queue, Brain, Evals and Agents tabs reuse this grammar (stamps, dots, sheet, type roles); their layouts are designed when they're built. The eval-set page's lane × label table follows the same rules: tabular counts, no single agreement percentage.
