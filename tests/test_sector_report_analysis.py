from sector_report import md_to_html


def test_md_heading_becomes_h3():
    assert "<h3>Title</h3>" in md_to_html("# Title")


def test_md_bold():
    assert "<strong>bold</strong>" in md_to_html("a **bold** b")


def test_md_unordered_list():
    html = md_to_html("- one\n- two")
    assert "<ul>" in html and html.count("<li>") == 2


def test_md_paragraph():
    assert "<p>hello world</p>" in md_to_html("hello world")


def test_md_escapes_html_special_chars():
    html = md_to_html("a < b & c > d")
    assert "&lt;" in html and "&amp;" in html and "&gt;" in html


from sector_report import analysis_section, build_html


def _min_market():
    ret = {"1d": 1.0, "1w": 1.0, "1m": 1.0, "3m": 1.0}
    rel = {"1d": 0.5, "1w": 0.5, "1m": 0.5, "3m": 0.5}
    return {
        "label": "JP", "as_of": "2026-07-03",
        "benchmark": {"ticker": "1306.T", "name": "TOPIX", "ret": ret},
        "sectors": [{"ticker": "1631.T", "name": "銀行", "ret": ret, "rel": rel,
                     "score": 10, "verdict": "強気", "momentum": "横ばい"}],
    }


def _min_data():
    return {"generated_at": "2026-07-05T00:00:00", "jp": _min_market()}


def test_analysis_section_skips_null_blocks():
    html = analysis_section({"jp": "# J", "us": None, "strategist": "**m**"})
    assert "日本株の背景分析" in html
    assert "米国株の背景分析" not in html
    assert "統合見解" in html


def test_analysis_section_empty_when_all_null():
    assert analysis_section({"jp": None, "us": None, "strategist": None}) == ""


def test_build_html_without_analysis_is_backcompat():
    assert "背景分析" not in build_html(_min_data())


def test_build_html_with_analysis_renders_section():
    html = build_html(_min_data(), {"jp": "# 日本\n\n本文", "us": None,
                                    "strategist": "統合"})
    assert "背景分析" in html
    assert "日本株の背景分析" in html
    assert "米国株の背景分析" not in html
