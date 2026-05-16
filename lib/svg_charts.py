"""Inline SVG chart helpers.

Every helper returns a complete `<svg>...</svg>` string. No CSS classes inside
the SVG — colors and strokes are inlined so the markup is self-contained when
copy-pasted into Substack or screenshotted.
"""
from __future__ import annotations

from datetime import date, timedelta


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
