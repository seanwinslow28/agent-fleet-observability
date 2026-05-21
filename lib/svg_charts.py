"""Inline SVG chart helpers — Spark Console palette.

Every helper returns a complete `<svg>...</svg>` string. No CSS classes inside
the SVG — colors are inlined so markup is self-contained when copy-pasted
into Substack or screenshotted.

Token rule (locked in DESIGN.md): four working colors total.
- AMBER  primary signal · local-first · healthy series
- PURPLE secondary · cloud spend · regression annotation
- ALERT  failures only
- OK     legacy "healthy" status dot — kept for fleet status semantics

NEVER add a fifth chart color. If you reach for one, you're saying something
the data doesn't actually justify. Use AMBER + PURPLE intensities instead.
"""
from __future__ import annotations

import math
from datetime import date

# Spark palette — DESIGN.md is the source of truth, this mirrors it
AMBER = "#F0B429"
AMBER_SOFT = "rgba(240,180,41,0.35)"
PURPLE = "#C084FC"
PURPLE_SOFT = "rgba(192,132,252,0.35)"
ALERT = "#FF5C46"
OK = "#3FB950"

# Surfaces / text — match DESIGN.md
TEXT = "#F4EFE6"
SECONDARY = "#A89FB0"
TERTIARY = "#6B6478"
PANEL = "#0A0810"          # recessed plate (deeper than raised — charts sit inside)
GRID = "rgba(192,132,252,0.06)"

# Backwards-compatibility aliases — old code/templates may still import these.
# All collapse to the four working colors per DESIGN.md.
GREEN = OK             # status dots only
TEAL = AMBER           # was used for synth-recovery line; now amber
RED = ALERT
BLUE = PURPLE          # was used for "info/job-feed"; now purple
PANEL_LEGACY = PANEL

# Chart stack — semantic bands for cost-trend and model-mix.
# Collapses the prior 8-color agent cycle down to three layers:
#   local · cloud-anthropic · cloud-gemini  (per DESIGN.md anti-noise rule)
_STACK_COLORS = [AMBER, PURPLE, ALERT]
_STACK_LOCAL_TAGS = {"local", "local-qwen", "local-nomic", "local-other", "qwen", "nomic"}
_STACK_ANTHROPIC_TAGS = {"cloud-anthropic", "anthropic", "claude", "sonnet"}
_STACK_GEMINI_TAGS = {"cloud-gemini", "gemini", "google", "cloud"}


def _scale(val: float, src_lo: float, src_hi: float, dst_lo: float, dst_hi: float) -> float:
    if src_hi == src_lo:
        return (dst_lo + dst_hi) / 2
    return dst_lo + (val - src_lo) * (dst_hi - dst_lo) / (src_hi - src_lo)


def _collapse_to_semantic_bands(series: dict[str, list[float]]) -> dict[str, list[float]]:
    """Fold any number of agent/model keys into 3 semantic bands."""
    if not series:
        return {}
    n = len(next(iter(series.values())))
    bands = {"local": [0.0] * n, "cloud-anthropic": [0.0] * n, "cloud-gemini": [0.0] * n}
    for key, values in series.items():
        lk = key.lower()
        if any(t in lk for t in _STACK_ANTHROPIC_TAGS):
            band = "cloud-anthropic"
        elif any(t in lk for t in _STACK_GEMINI_TAGS):
            band = "cloud-gemini"
        elif any(t in lk for t in _STACK_LOCAL_TAGS):
            band = "local"
        else:
            band = "local"  # default — local-first system
        for i, v in enumerate(values):
            bands[band][i] += v
    # Drop empty bands so legend stays honest
    return {k: v for k, v in bands.items() if any(v)}


def line_chart(
    series: list[dict],
    width: int,
    height: int,
    annotation: dict | None = None,
    color: str = AMBER,
    pad_top: int = 24,
    pad_right: int = 24,
    pad_bottom: int = 32,
    pad_left: int = 44,
    fill_area: bool = True,
) -> str:
    inner_w = width - pad_left - pad_right
    inner_h = height - pad_top - pad_bottom
    if not series:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'
    values = [s["value"] for s in series if s["value"] is not None] or [0]
    v_lo, v_hi = 0, max(max(values), 1)
    dates = [s["date"] for s in series]
    d_lo, d_hi = dates[0].toordinal(), dates[-1].toordinal()

    def x(d: date) -> float:
        return pad_left + _scale(d.toordinal(), d_lo, d_hi, 0, inner_w)

    def y(v: float) -> float:
        return pad_top + inner_h - _scale(v, v_lo, v_hi, 0, inner_h)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        'font-family="JetBrains Mono, ui-monospace, monospace">'
    ]
    # No solid background rect — the parent .hero-plate / .panel already provides surface + glow
    # Grid lines — purple-tinted hairlines
    for i in range(4):
        gy = pad_top + i * inner_h / 3
        parts.append(
            f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" '
            f'stroke="{PURPLE}" stroke-opacity="0.06" stroke-width="1"/>'
        )

    # Annotation band — purple, not red; the regression is the story, not an emergency
    if annotation:
        ax = x(annotation["start_date"])
        bx = x(annotation["end_date"])
        parts.append(
            f'<rect class="hero-band-wipe" x="{ax:.1f}" y="{pad_top}" '
            f'width="{(bx - ax):.1f}" height="{inner_h}" '
            f'fill="{PURPLE}" fill-opacity="0.12" '
            f'stroke="{PURPLE}" stroke-width="1" stroke-dasharray="4 3"/>'
        )
        label = annotation["label"]
        parts.append(
            f'<text x="{ax + 6:.1f}" y="{pad_top - 8}" font-size="9" fill="{PURPLE}" '
            f'font-weight="700" letter-spacing="0.06em">{label}</text>'
        )

    # Build polyline points (split on None gaps so we don't bridge missing data)
    segments: list[list[str]] = [[]]
    for s in series:
        if s["value"] is None:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(f"{x(s['date']):.1f},{y(s['value']):.1f}")
    segments = [seg for seg in segments if seg]

    # Optional area fill under the line — subtle amber wash
    if fill_area and segments:
        baseline_y = y(0)
        for seg in segments:
            first_x = seg[0].split(",")[0]
            last_x = seg[-1].split(",")[0]
            area_pts = [f"{first_x},{baseline_y:.1f}"] + seg + [f"{last_x},{baseline_y:.1f}"]
            parts.append(
                f'<polygon fill="{color}" fill-opacity="0.10" '
                f'points="{" ".join(area_pts)}"/>'
            )

    for seg in segments:
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'points="{" ".join(seg)}"/>'
        )

    # x-axis labels — first, middle, last
    label_dates = [dates[0], dates[len(dates) // 2], dates[-1]]
    for d in label_dates:
        parts.append(
            f'<text x="{x(d):.1f}" y="{height - 8}" font-size="9" fill="{TERTIARY}" '
            f'text-anchor="middle" letter-spacing="0.04em">{d.isoformat()}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def sparkline(values: list[float | int], width: int = 80, height: int = 16,
              color: str = AMBER) -> str:
    if not values:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'
    v_lo, v_hi = min(values), max(values)
    if v_hi == v_lo:
        v_hi += 1
    pts: list[str] = []
    for i, v in enumerate(values):
        x = i * (width - 2) / max(1, len(values) - 1) + 1
        y = height - 1 - (v - v_lo) * (height - 2) / (v_hi - v_lo)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="display: inline-block; vertical-align: middle;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'points="{" ".join(pts)}"/></svg>'
    )


def donut(segments: list[dict], size: int = 140, stroke: int = 16,
          center_label: str | None = None, center_sub: str | None = None,
          css_class: str | None = None, aria_hidden: bool = False) -> str:
    """`segments`: list of {'value': float, 'color': str}. Values normalize to 360°.

    Renders with explicit width/height so the SVG stays at its intrinsic size
    (without these, browsers stretch the viewBox to fill any flex/grid cell).
    Optional center_label/center_sub render inside the ring — typically the
    dominant share, e.g. "92.2%" over "LOCAL".

    `css_class` and `aria_hidden` let callers stamp the root <svg> with a class
    + decorative-a11y marker at the source (used by the small KPI-row donut).
    """
    total = sum(s["value"] for s in segments) or 1.0
    radius = (size - stroke) / 2
    cx = cy = size / 2
    class_attr = f' class="{css_class}"' if css_class else ''
    aria_attr = ' aria-hidden="true"' if aria_hidden else ''
    parts = [
        f'<svg{class_attr}{aria_attr} '
        f'viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="flex-shrink: 0; display: block;" '
        f'font-family="Sora, system-ui, sans-serif">'
    ]
    # Background ring — purple hairline so the donut has a track even when one segment is 100%
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{radius:.2f}" fill="none" '
        f'stroke="{PURPLE}" stroke-opacity="0.10" stroke-width="{stroke}"/>'
    )
    angle = -90.0  # start at 12 o'clock
    for seg in segments:
        sweep = seg["value"] / total * 360.0
        if sweep <= 0:
            continue
        # If a segment is exactly 100%, draw it as a full circle instead of an arc
        # (an arc from angle to angle+360 collapses to a point in SVG path syntax).
        if sweep >= 359.999:
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{radius:.2f}" fill="none" '
                f'stroke="{seg["color"]}" stroke-width="{stroke}"/>'
            )
            angle += sweep
            continue
        large = 1 if sweep > 180 else 0
        a1 = math.radians(angle)
        a2 = math.radians(angle + sweep)
        x1 = cx + radius * math.cos(a1)
        y1 = cy + radius * math.sin(a1)
        x2 = cx + radius * math.cos(a2)
        y2 = cy + radius * math.sin(a2)
        d_attr = (
            f'M {x1:.2f} {y1:.2f} A {radius:.2f} {radius:.2f} 0 {large} 1 {x2:.2f} {y2:.2f}'
        )
        parts.append(
            f'<path d="{d_attr}" fill="none" stroke="{seg["color"]}" '
            f'stroke-width="{stroke}" stroke-linecap="round"/>'
        )
        angle += sweep
    if center_label:
        parts.append(
            f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" '
            f'font-size="20" font-weight="700" fill="{TEXT}" '
            f'font-variant-numeric="tabular-nums" letter-spacing="-0.02em">{center_label}</text>'
        )
    if center_sub:
        parts.append(
            f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
            f'font-size="9" fill="{TERTIARY}" letter-spacing="0.08em" '
            f'font-family="JetBrains Mono, monospace">{center_sub}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def stacked_area(
    days: list[str],
    series: dict[str, list[float]],
    width: int,
    height: int,
    pad_top: int = 24,
    pad_right: int = 24,
    pad_bottom: int = 32,
    pad_left: int = 44,
) -> str:
    """Stacked area chart — collapses any input series to 3 semantic bands.

    Input `series` may have one key per agent (legacy). We fold to local /
    cloud-anthropic / cloud-gemini so the chart never exceeds 3 colors.

    Each band gets a fill at 0.45 opacity plus a 1.5px top-stroke at the band's
    color for definition — softens the prior hard polygons.
    """
    inner_w = width - pad_left - pad_right
    inner_h = height - pad_top - pad_bottom
    n = len(days)
    if n == 0:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'

    bands = _collapse_to_semantic_bands(series)
    if not bands:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'

    stack: list[list[float]] = [[0.0] * n]
    band_names = list(bands.keys())
    for b in band_names:
        stack.append([stack[-1][i] + bands[b][i] for i in range(n)])
    total_max = max(stack[-1]) or 1.0

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="JetBrains Mono, ui-monospace, monospace">'
    ]

    def x(i: int) -> float:
        return pad_left + i * inner_w / max(1, n - 1)

    def y(v: float) -> float:
        return pad_top + inner_h - v * inner_h / total_max

    # Grid lines
    for i in range(4):
        gy = pad_top + i * inner_h / 3
        parts.append(
            f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" '
            f'stroke="{PURPLE}" stroke-opacity="0.06" stroke-width="1"/>'
        )

    for idx, _b in enumerate(band_names):
        color = _STACK_COLORS[idx % len(_STACK_COLORS)]
        upper = stack[idx + 1]
        lower = stack[idx]
        area_pts = [f"{x(i):.1f},{y(upper[i]):.1f}" for i in range(n)]
        area_pts += [f"{x(i):.1f},{y(lower[i]):.1f}" for i in range(n - 1, -1, -1)]
        parts.append(
            f'<polygon fill="{color}" fill-opacity="0.42" '
            f'points="{" ".join(area_pts)}"/>'
        )
        # Top-of-band stroke for definition
        top_pts = [f"{x(i):.1f},{y(upper[i]):.1f}" for i in range(n)]
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-opacity="0.9" points="{" ".join(top_pts)}"/>'
        )

    # Today marker — small dot at the last datum, top-of-stack
    if band_names:
        last_top = stack[-1][n - 1]
        parts.append(
            f'<circle cx="{x(n - 1):.1f}" cy="{y(last_top):.1f}" r="3" '
            f'fill="{AMBER}" stroke="{PANEL}" stroke-width="1.5"/>'
        )

    parts.append(
        f'<text x="{pad_left}" y="{height - 8}" font-size="9" fill="{TERTIARY}" '
        f'letter-spacing="0.04em">{days[0]}</text>'
    )
    parts.append(
        f'<text x="{width - pad_right}" y="{height - 8}" font-size="9" fill="{TERTIARY}" '
        f'text-anchor="end" letter-spacing="0.04em">{days[-1]} · today</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


# ───────── KPI-row inline primitives ─────────
# Each helper renders a small inline SVG that sits inside one .kpi-card. The
# point is that every card gets a visually DIFFERENT primitive — eye picks up
# data shape before reading the kpi-value text. All primitives are decorative
# (aria-hidden on the wrapping element) and have viewBoxes so they scale at
# narrower widths when the .kpi-row collapses 4→2→1.


def kpi_eval_dots(passed: int, failed: int, skipped: int, total: int) -> str:
    """Row of `total` small circles — passed (amber fill), failed (alert fill),
    skipped (hollow amber). Matches the `7 / 10` eval-pass card. If `total`
    is zero, returns 10 muted hollow dots (placeholder for no-eval state).

    If passed+failed+skipped exceeds `total`, the row grows to fit all cases
    rather than silently dropping the trailing ones.
    """
    if total <= 0:
        # Empty placeholder — 10 hollow tertiary dots
        passed = failed = skipped = 0
        total = 10
        empty = True
    else:
        # Grow total to fit overflow rather than dropping trailing statuses
        total = max(total, passed + failed + skipped)
        empty = False
    r = 3.0
    gap = 4.0
    diameter = r * 2
    n = total
    width = n * diameter + (n - 1) * gap
    height = diameter
    parts = [
        f'<svg viewBox="0 0 {width:.1f} {height:.1f}" '
        f'preserveAspectRatio="xMinYMid meet" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'class="kpi-dots" aria-hidden="true">'
    ]
    cy = r
    for i in range(n):
        cx = r + i * (diameter + gap)
        if empty:
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="none" stroke="{TERTIARY}" stroke-width="1"/>'
            )
        elif i < passed:
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{OK}"/>'
            )
        elif i < passed + failed:
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{ALERT}"/>'
            )
        elif i < passed + failed + skipped:
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="none" stroke="{AMBER}" stroke-width="1.2"/>'
            )
        else:
            # Cases counted in total but not passed/failed/skipped — hollow tertiary
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="none" stroke="{TERTIARY}" stroke-width="1"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


def kpi_spend_sparkline(daily_totals: list[float], color: str = AMBER) -> str:
    """30-day spend sparkline. Width is responsive (100%), height fixed.
    Empty data renders as a flat baseline so the card height stays stable.
    """
    width = 120.0
    height = 22.0
    if not daily_totals or all(v <= 0 for v in daily_totals):
        # Flat baseline placeholder
        y_mid = height - 1
        return (
            f'<svg viewBox="0 0 {width:.0f} {height:.0f}" '
            f'preserveAspectRatio="none" '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'class="kpi-sparkline" aria-hidden="true">'
            f'<line x1="0" y1="{y_mid:.1f}" x2="{width:.0f}" y2="{y_mid:.1f}" '
            f'stroke="{TERTIARY}" stroke-width="1.2" stroke-linecap="round" '
            f'stroke-dasharray="2 3"/>'
            f'</svg>'
        )
    v_lo, v_hi = min(daily_totals), max(daily_totals)
    if v_hi == v_lo:
        v_hi = v_lo + 1
    pts: list[str] = []
    n = len(daily_totals)
    for i, v in enumerate(daily_totals):
        x = i * (width - 2) / max(1, n - 1) + 1
        y = height - 2 - (v - v_lo) * (height - 4) / (v_hi - v_lo)
        pts.append(f"{x:.1f},{y:.1f}")
    baseline_y = height - 1
    area_pts = [f"1,{baseline_y:.1f}"] + pts + [f"{width - 1:.1f},{baseline_y:.1f}"]
    return (
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" '
        f'preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'class="kpi-sparkline" aria-hidden="true">'
        f'<polygon fill="{color}" fill-opacity="0.18" '
        f'points="{" ".join(area_pts)}"/>'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'points="{" ".join(pts)}"/>'
        f'</svg>'
    )


def kpi_fill_bar(current: float, cap: float, color: str = AMBER) -> str:
    """Horizontal fill bar: current spend as fraction of cap. Bar is
    100%-width of its container, 6px tall, pill-shaped. Over-cap renders the
    bar full with a thin alert outline. Zero/empty renders an empty track.
    """
    width = 120.0
    height = 6.0
    radius = height / 2
    track_fill = "rgba(192,132,252,0.10)"  # var(--hairline)-ish, recessed track
    if cap <= 0:
        ratio = 0.0
    else:
        ratio = max(0.0, current / cap)
    over = ratio > 1.0
    capped_ratio = min(ratio, 1.0)
    bar_w = max(0.0, width * capped_ratio)
    parts = [
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" '
        f'preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'class="kpi-fill-bar" aria-hidden="true">',
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" '
        f'rx="{radius:.1f}" ry="{radius:.1f}" fill="{track_fill}"/>',
    ]
    if bar_w > 0:
        parts.append(
            f'<rect x="0" y="0" width="{bar_w:.2f}" height="{height:.0f}" '
            f'rx="{radius:.1f}" ry="{radius:.1f}" fill="{color}"/>'
        )
    if over:
        parts.append(
            f'<rect x="0.5" y="0.5" width="{width - 1:.1f}" height="{height - 1:.1f}" '
            f'rx="{radius:.1f}" ry="{radius:.1f}" fill="none" '
            f'stroke="{ALERT}" stroke-width="1"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def kpi_donut(local_pct: float, size: int = 28, stroke: int = 4) -> str:
    """Tiny inline donut for the local-only share card. Amber arc for local
    share, purple-soft arc for cloud share. No center text — kpi-value text
    sits BESIDE the donut, not inside.

    `local_pct` is clamped to [0, 100] — a negative input would invert the
    donut and a >100 input only renders correctly by accident.
    """
    local_pct = max(0.0, min(100.0, float(local_pct)))
    cloud_pct = 100.0 - local_pct
    return donut(
        segments=[
            {"value": local_pct, "color": AMBER},
            {"value": cloud_pct, "color": PURPLE_SOFT},
        ],
        size=size,
        stroke=stroke,
        css_class="kpi-donut",
        aria_hidden=True,
    )
