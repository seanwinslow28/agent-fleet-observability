"""Inline SVG chart helpers.

Every helper returns a complete `<svg>...</svg>` string. No CSS classes inside
the SVG — colors and strokes are inlined so the markup is self-contained when
copy-pasted into Substack or screenshotted.
"""
from __future__ import annotations

import math
from datetime import date

# Palette mirrors design doc Section 5b
GREEN = "#3fb950"
TEAL = "#18b894"
AMBER = "#f0b429"
RED = "#f85149"
BLUE = "#58a6ff"
PURPLE = "#c084fc"
TEXT = "#e6edf3"
SECONDARY = "#8b949e"
PANEL = "#11151c"
GRID = "#1a2230"
_AGENT_COLORS = [TEAL, GREEN, AMBER, BLUE, PURPLE, "#ff7b72", "#79c0ff", "#d2a8ff"]


def _scale(val: float, src_lo: float, src_hi: float, dst_lo: float, dst_hi: float) -> float:
    if src_hi == src_lo:
        return (dst_lo + dst_hi) / 2
    return dst_lo + (val - src_lo) * (dst_hi - dst_lo) / (src_hi - src_lo)


def line_chart(
    series: list[dict],
    width: int,
    height: int,
    annotation: dict | None = None,
    color: str = TEAL,
    pad_top: int = 20,
    pad_right: int = 20,
    pad_bottom: int = 28,
    pad_left: int = 40,
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
        'font-family="JetBrains Mono, monospace">'
    ]
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}"/>')
    for i in range(4):
        gy = pad_top + i * inner_h / 3
        parts.append(f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')

    if annotation:
        ax = x(annotation["start_date"])
        bx = x(annotation["end_date"])
        parts.append(f'<rect x="{ax:.1f}" y="{pad_top}" width="{(bx - ax):.1f}" '
                     f'height="{inner_h}" fill="{RED}" fill-opacity="0.10" '
                     f'stroke="{RED}" stroke-width="1" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{ax + 4:.1f}" y="{pad_top - 6}" font-size="9" fill="{RED}" '
                     f'font-weight="700">{annotation["label"]}</text>')

    pts: list[str] = []
    for s in series:
        if s["value"] is None:
            if pts:
                parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" '
                             f'points="{" ".join(pts)}"/>')
                pts = []
            continue
        pts.append(f"{x(s['date']):.1f},{y(s['value']):.1f}")
    if pts:
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" '
                     f'points="{" ".join(pts)}"/>')

    # x-axis labels — first, middle, last
    label_dates = [dates[0], dates[len(dates) // 2], dates[-1]]
    for d in label_dates:
        parts.append(f'<text x="{x(d):.1f}" y="{height - 6}" font-size="9" fill="{SECONDARY}" '
                     f'text-anchor="middle">{d.isoformat()}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def sparkline(values: list[float | int], width: int = 80, height: int = 16,
              color: str = GREEN) -> str:
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
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'points="{" ".join(pts)}"/></svg>'
    )


def donut(segments: list[dict], size: int = 120, stroke: int = 14) -> str:
    """`segments`: list of {'value': float, 'color': str}. Values normalize to 360°."""
    total = sum(s["value"] for s in segments) or 1.0
    radius = (size - stroke) / 2
    cx = cy = size / 2
    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">']
    angle = -90.0  # start at 12 o'clock
    for seg in segments:
        sweep = seg["value"] / total * 360.0
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
            f'<path d="{d_attr}" fill="none" stroke="{seg["color"]}" stroke-width="{stroke}"/>'
        )
        angle += sweep
    parts.append("</svg>")
    return "".join(parts)


def stacked_area(
    days: list[str],
    series: dict[str, list[float]],
    width: int,
    height: int,
    pad_top: int = 12,
    pad_right: int = 12,
    pad_bottom: int = 24,
    pad_left: int = 36,
) -> str:
    inner_w = width - pad_left - pad_right
    inner_h = height - pad_top - pad_bottom
    n = len(days)
    if n == 0:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'
    stack: list[list[float]] = [[0.0] * n]
    agents = list(series.keys())
    for a in agents:
        stack.append([stack[-1][i] + series[a][i] for i in range(n)])
    total_max = max(stack[-1]) or 1.0
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="JetBrains Mono, monospace">'
    ]
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}"/>')

    def x(i: int) -> float:
        return pad_left + i * inner_w / max(1, n - 1)

    def y(v: float) -> float:
        return pad_top + inner_h - v * inner_h / total_max

    for idx, _a in enumerate(agents):
        color = _AGENT_COLORS[idx % len(_AGENT_COLORS)]
        upper = stack[idx + 1]
        lower = stack[idx]
        pts = [f"{x(i):.1f},{y(upper[i]):.1f}" for i in range(n)]
        pts += [f"{x(i):.1f},{y(lower[i]):.1f}" for i in range(n - 1, -1, -1)]
        parts.append(f'<polygon fill="{color}" fill-opacity="0.85" '
                     f'points="{" ".join(pts)}"/>')
    parts.append(f'<text x="{pad_left}" y="{height - 6}" font-size="9" fill="{SECONDARY}">'
                 f'{days[0]}</text>')
    parts.append(f'<text x="{width - pad_right}" y="{height - 6}" font-size="9" fill="{SECONDARY}" '
                 f'text-anchor="end">{days[-1]}</text>')
    parts.append("</svg>")
    return "".join(parts)
