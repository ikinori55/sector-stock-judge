from sector_history_report import color_scale, cell_color, build_html


def test_color_scale_reads_given_key_over_sectors_only():
    sections = [{"sectors": [{"daily": [1, 2, 3, 4], "weekly": [50, 60]}]}]
    assert color_scale(sections, "daily") > 0
    assert color_scale(sections, "weekly") >= 50


def test_color_scale_all_none_returns_one():
    sections = [{"sectors": [{"daily": [None, None]}]}]
    assert color_scale(sections, "daily") == 1.0


def test_cell_color_none_is_gray():
    bg, _ = cell_color(None, 5)
    assert bg == "#f3f4f6"


def test_cell_color_sign_maps_to_green_red():
    assert "16,150,105" in cell_color(2.0, 5)[0]
    assert "220,38,38" in cell_color(-2.0, 5)[0]


def _min_data():
    return {
        "generated_at": "2026-07-05T00:00:00", "days": 2, "weeks": 2,
        "jp": {
            "label": "JP",
            "benchmark": {"ticker": "1306.T", "name": "TOPIX",
                          "daily": [0.0, 0.0], "weekly": [0.0, 0.0]},
            "dates": ["2026-07-02", "2026-07-03"],
            "weekly_dates": ["2026-06-27", "2026-07-04"],
            "sectors": [{"ticker": "1631.T", "name": "銀行",
                         "daily": [0.3, -0.1], "cum": 0.2,
                         "weekly": [1.0, -0.5], "weekly_cum": 0.5}],
        },
    }


def test_build_html_omits_benchmark_row():
    html = build_html(_min_data())
    assert "銀行" in html
    assert "TOPIX" not in html


def test_build_html_has_daily_and_weekly_tables():
    html = build_html(_min_data())
    assert "日次相対" in html
    assert "週次相対" in html
