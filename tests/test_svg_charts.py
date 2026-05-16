from datetime import date

from lib import svg_charts


def test_line_chart_returns_svg_string():
    series = [{"date": date(2026, 5, d), "value": v} for d, v in enumerate([10, 0, 0, 0, 90, 114], start=8)]
    svg = svg_charts.line_chart(series, width=600, height=160)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "viewBox" in svg


def test_line_chart_with_annotation_includes_band():
    series = [{"date": date(2026, 5, d), "value": 0} for d in range(1, 11)]
    svg = svg_charts.line_chart(
        series,
        width=600, height=160,
        annotation={"start_date": date(2026, 5, 1), "end_date": date(2026, 5, 10),
                    "label": "9-DAY SILENT REGRESSION"},
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
