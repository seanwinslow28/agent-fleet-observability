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
