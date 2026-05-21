from datetime import date

from lib import svg_charts


def test_line_chart_returns_svg_string():
    series = [
        {"date": date(2026, 5, d), "value": v}
        for d, v in enumerate([10, 0, 0, 0, 90, 114], start=8)
    ]  # noqa: E501
    svg = svg_charts.line_chart(series, width=600, height=160)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "viewBox" in svg


def test_line_chart_with_annotation_includes_band():
    series = [{"date": date(2026, 5, d), "value": 0} for d in range(1, 11)]
    svg = svg_charts.line_chart(
        series,
        width=600,
        height=160,
        annotation={
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 5, 10),
            "label": "9-DAY SILENT REGRESSION",
        },
    )
    assert "9-DAY SILENT REGRESSION" in svg
    # red dashed rect
    assert "stroke-dasharray" in svg


def test_line_chart_handles_none_gaps():
    series = [
        {"date": date(2026, 5, 1), "value": 0},
        {"date": date(2026, 5, 2), "value": None},
        {"date": date(2026, 5, 3), "value": 5},
    ]
    svg = svg_charts.line_chart(series, width=400, height=120)
    # Should still emit valid SVG, just skip the None
    assert svg.startswith("<svg")


def test_sparkline_renders():
    svg = svg_charts.sparkline([1, 2, 3, 4, 7, 7, 7, 7, 6, 7, 7, 7, 7, 7], width=80, height=16)
    assert svg.startswith("<svg")


def test_donut_renders_segments():
    segments = [
        {"label": "local-qwen", "value": 78, "color": "#18b894"},
        {"label": "cloud-anthropic", "value": 22, "color": "#58a6ff"},
    ]
    svg = svg_charts.donut(segments, size=120)
    assert svg.startswith("<svg")
    assert "local-qwen" not in svg  # labels rendered separately by template


def test_donut_small_wedge_renders_as_single_path():
    """Each wedge is exactly ONE <path>, never split into two adjacent paths.

    Regression: an earlier draft of donut() drew the small (<180°) wedge as
    two arc commands meeting head-to-toe, which produced a visible seam at
    the boundary. With 92.7% / 7.3%, the correct output is:
      - one path for the big wedge (large-arc-flag=1, >180°)
      - one path for the small wedge (large-arc-flag=0, <180°)
    Plus the always-present background ring <circle>. No more, no less.
    """
    segments = [
        {"label": "a", "value": 92.7, "color": "#F0B429"},
        {"label": "b", "value": 7.3, "color": "#C084FC"},
    ]
    svg = svg_charts.donut(segments, size=160, stroke=18)
    # Exactly one <path> per wedge (2 paths for 2 wedges).
    assert svg.count("<path") == 2
    # Sanity: small wedge uses large-arc-flag=0, big wedge uses large-arc-flag=1.
    # The flag sits between the rotation (0) and sweep (1) in `A rx ry 0 L 1 x y`.
    assert svg.count(" 0 1 1 ") == 1  # large=1 sweep=1 → the big wedge
    assert svg.count(" 0 0 1 ") == 1  # large=0 sweep=1 → the small wedge
    # Background ring is a <circle>, not a path — one of them.
    assert svg.count("<circle") == 1


def test_donut_three_wedges_renders_three_paths():
    """Three small wedges (each <180°) → exactly three <path> elements."""
    segments = [
        {"value": 50, "color": "#F0B429"},
        {"value": 30, "color": "#C084FC"},
        {"value": 20, "color": "#FF5C46"},
    ]
    svg = svg_charts.donut(segments, size=120, stroke=14)
    assert svg.count("<path") == 3


def test_stacked_area_handles_multi_agent():
    days = [f"2026-05-{d:02d}" for d in range(1, 8)]
    series = {"vault_synthesizer": [0] * 7, "daily_driver": [0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]}
    svg = svg_charts.stacked_area(days, series, width=400, height=120)
    assert svg.startswith("<svg")


# ───── KPI-row primitives (Task 5) ─────


def test_kpi_eval_dots_renders_one_circle_per_case():
    """7 passed · 2 failed · 1 skipped → 7 OK + 2 ALERT + 1 hollow amber."""
    svg = svg_charts.kpi_eval_dots(passed=7, failed=2, skipped=1, total=10)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'class="kpi-dots"' in svg
    assert 'aria-hidden="true"' in svg
    # 10 circles total
    assert svg.count("<circle") == 10
    # 7 OK-green fills (passed)
    assert svg.count(f'fill="{svg_charts.OK}"') == 7
    # 2 alert-red fills (failed)
    assert svg.count(f'fill="{svg_charts.ALERT}"') == 2
    # 1 hollow amber stroke (skipped)
    assert svg.count(f'stroke="{svg_charts.AMBER}"') == 1


def test_kpi_eval_dots_empty_state_renders_10_hollow_placeholders():
    """No eval data → 10 hollow tertiary dots (placeholder, not blank)."""
    svg = svg_charts.kpi_eval_dots(passed=0, failed=0, skipped=0, total=0)
    assert svg.count("<circle") == 10
    # All dots are hollow (no solid fills) and use tertiary stroke
    assert f'fill="{svg_charts.OK}"' not in svg
    assert f'fill="{svg_charts.ALERT}"' not in svg
    assert svg.count(f'stroke="{svg_charts.TERTIARY}"') == 10


def test_kpi_spend_sparkline_renders_polyline_with_data():
    daily = [0.0, 0.1, 0.2, 0.3] * 7 + [0.4, 1.2]  # 30 days
    svg = svg_charts.kpi_spend_sparkline(daily)
    assert 'class="kpi-sparkline"' in svg
    assert 'aria-hidden="true"' in svg
    assert "<polyline" in svg


def test_kpi_spend_sparkline_empty_renders_dashed_baseline():
    svg = svg_charts.kpi_spend_sparkline([])
    assert 'class="kpi-sparkline"' in svg
    # Placeholder uses a dashed line (no polyline / no polygon area fill)
    assert "stroke-dasharray" in svg
    assert "<polyline" not in svg


def test_kpi_fill_bar_renders_track_and_fill():
    svg = svg_charts.kpi_fill_bar(current=8.0, cap=50.0)
    assert 'class="kpi-fill-bar"' in svg
    assert 'aria-hidden="true"' in svg
    # Two rects: track + fill
    assert svg.count("<rect") == 2


def test_kpi_fill_bar_over_cap_adds_alert_outline():
    svg = svg_charts.kpi_fill_bar(current=60.0, cap=50.0)
    # track + full-width fill + alert outline = 3 rects
    assert svg.count("<rect") == 3
    assert f'stroke="{svg_charts.ALERT}"' in svg


def test_kpi_fill_bar_zero_current_renders_only_track():
    svg = svg_charts.kpi_fill_bar(current=0.0, cap=50.0)
    # No fill bar drawn when current is zero — only the track
    assert svg.count("<rect") == 1


def test_kpi_donut_carries_class_and_aria_hidden():
    svg = svg_charts.kpi_donut(local_pct=92.7, size=28, stroke=4)
    assert 'class="kpi-donut"' in svg
    assert 'aria-hidden="true"' in svg
    # Underlying donut renders two arcs (local + cloud) plus background ring
    assert svg.count("<path") == 2


def test_kpi_donut_clamps_out_of_range_local_pct():
    """Negative and >100 inputs must not invert or distort the donut.

    Boundaries 0/100 render as a full ring of the appropriate color.
    """
    # Negative clamps to 0 — should look identical to local_pct=0 (full purple)
    neg = svg_charts.kpi_donut(local_pct=-5)
    zero = svg_charts.kpi_donut(local_pct=0)
    assert neg == zero
    # >100 clamps to 100 — should look identical to local_pct=100 (full amber)
    over = svg_charts.kpi_donut(local_pct=105)
    full = svg_charts.kpi_donut(local_pct=100)
    assert over == full
    # 0 boundary: no amber arc, single full purple ring (cloud=100%)
    assert f'stroke="{svg_charts.PURPLE_SOFT}"' in zero
    # 100 boundary: full amber ring (local=100%), no purple arc
    assert f'stroke="{svg_charts.AMBER}"' in full


def test_donut_accepts_css_class_and_aria_hidden_kwargs():
    """donut() stamps the root <svg> with caller-supplied class + a11y attrs."""
    segments = [{"value": 70, "color": "#F0B429"}, {"value": 30, "color": "#C084FC"}]
    svg = svg_charts.donut(segments, size=40, stroke=6, css_class="my-cls", aria_hidden=True)
    assert 'class="my-cls"' in svg
    assert 'aria-hidden="true"' in svg
    # Default: neither attr present
    plain = svg_charts.donut(segments, size=40, stroke=6)
    assert "class=" not in plain.split(">", 1)[0]  # no class on root <svg>
    assert "aria-hidden" not in plain


def test_kpi_eval_dots_overflow_grows_row_not_drops_cases():
    """If passed+failed+skipped > total, the row expands to hold all cases.

    Was previously a silent-drop: trailing statuses fell through the fence-post
    and emitted no circles.
    """
    # passed+failed+skipped = 12 but total=10 → grow to 12 circles
    svg = svg_charts.kpi_eval_dots(passed=7, failed=3, skipped=2, total=10)
    assert svg.count("<circle") == 12
    # 7 OK + 3 alert + 2 hollow amber — every case accounted for
    assert svg.count(f'fill="{svg_charts.OK}"') == 7
    assert svg.count(f'fill="{svg_charts.ALERT}"') == 3
    assert svg.count(f'stroke="{svg_charts.AMBER}"') == 2
