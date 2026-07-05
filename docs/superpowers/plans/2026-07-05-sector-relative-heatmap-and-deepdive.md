# セクター相対ヒートマップ ＋ 深掘り選択フロー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 既存の日次ヒートマップ資産を対ベンチマーク相対＋週次3ヶ月に拡張し、「セクター分析して」に背景分析の深掘り選択フローを追加する。

**Architecture:** 時系列ヒートマップ（日次30営業日・週次13週の対ベンチマーク相対リターン）は既存 `sector_history.py`/`sector_history_report.py` を拡張して実装。背景分析（エージェントチーム出力）は `sector_report.py` に `--analysis` オプションで「背景分析」セクションとして追加。ネットワーク非依存の純粋関数に切り出してTDDする。

**Tech Stack:** Python 3.10 / pandas / yfinance / pytest 9.1.1（インストール済み）。HTMLは自己完結の文字列生成。

**Note (git):** このプロジェクトはgitリポジトリではない。プランの各タスク末尾は「コミット」ではなく `pytest` 実行で締める。

**参照spec:** `docs/superpowers/specs/2026-07-05-daily-weekly-relative-heatmap-design.md`

---

## File Structure

- Create: `tests/conftest.py` — `scripts/` を `sys.path` に載せる
- Create: `tests/test_sector_history.py` — 相対日次/週次の計算テスト
- Create: `tests/test_sector_history_report.py` — 色スケール/描画テスト
- Create: `tests/test_sector_report_analysis.py` — Markdown変換/背景分析セクションのテスト
- Modify: `scripts/sector_history.py` — 相対化＋週次＋純粋関数 `build_market_history`
- Modify: `scripts/sector_history_report.py` — 相対表示・ベンチ行非表示・週次表・別cap
- Modify: `scripts/sector_report.py` — `md_to_html` / `analysis_section` / `--analysis`
- Modify: `.claude/skills/sector-analysis/SKILL.md` — 新ワークフロー
- Modify: `CLAUDE.md` — 構成表・使い分け・データ仕様

---

### Task 1: テスト基盤

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: conftest を作成**

`scripts/` はパッケージ化されていないため、テストから import できるよう `sys.path` に追加する。

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
```

- [ ] **Step 2: 収集できることを確認**

Run: `cd "E:/claudecode/2_Areas/04_Stock_Judge/secter_stock_fable5" && python -m pytest tests -q`
Expected: `no tests ran`（エラーなく collection が動く）

---

### Task 2: sector_history.py — 相対日次/週次の純粋関数

**Files:**
- Modify: `scripts/sector_history.py`
- Test: `tests/test_sector_history.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_sector_history.py`:

```python
import numpy as np
import pandas as pd

from sector_history import build_market_history, weekly_returns


def make_closes():
    idx = pd.bdate_range("2026-01-01", periods=90)
    n = np.arange(len(idx))
    bench = pd.Series(100.0 * (1.01 ** n), index=idx)   # 毎営業日 +1%
    sector = pd.Series(100.0 * (1.02 ** n), index=idx)  # 毎営業日 +2%
    return pd.DataFrame({"B": bench, "S": sector})


def test_weekly_returns_index_is_friday():
    closes = make_closes()
    wr = weekly_returns(closes["B"])
    assert (wr.index.weekday == 4).all()


def test_daily_relative_is_sector_minus_bench():
    closes = make_closes()
    m = build_market_history(closes, {"S": "SectorS"}, ("B", "Bench"),
                             "L", days=30, weeks=13)
    row = m["sectors"][0]
    assert len(row["daily"]) == 30
    assert all(abs(v - 1.0) < 0.05 for v in row["daily"])   # 2% - 1% = 1%


def test_benchmark_row_relative_to_itself_is_zero():
    closes = make_closes()
    m = build_market_history(closes, {"S": "SectorS"}, ("B", "Bench"),
                             "L", days=30, weeks=13)
    assert all(v == 0.0 for v in m["benchmark"]["daily"])


def test_weekly_series_length_and_positive():
    closes = make_closes()
    m = build_market_history(closes, {"S": "SectorS"}, ("B", "Bench"),
                             "L", days=30, weeks=13)
    row = m["sectors"][0]
    assert len(row["weekly"]) == 13
    assert len(m["weekly_dates"]) == 13
    assert all(v > 0 for v in row["weekly"])   # 週次でもセクターが上回る
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_sector_history.py -q`
Expected: FAIL（`build_market_history` / `weekly_returns` が未定義で ImportError）

- [ ] **Step 3: 純粋関数を実装**

`scripts/sector_history.py` の `daily_returns` 関数の直後（28行目の後）に追加:

```python
def weekly_returns(closes: pd.Series):
    """終値系列から週次(W-FRI)リターン(%)系列を返す (index=週末金曜)。"""
    s = closes.dropna()
    weekly_close = s.resample("W-FRI").last()
    ret = weekly_close.pct_change() * 100
    return ret.dropna()


def _rel_series(sec_ret: pd.Series, bench_ret: pd.Series, dates) -> list:
    """dates に沿って (sector - benchmark) の相対リターン配列を返す。欠損は None。"""
    out = []
    for d in dates:
        sv = sec_ret.get(d) if d in sec_ret.index else None
        bv = bench_ret.get(d) if d in bench_ret.index else None
        if sv is None or bv is None or math.isnan(sv) or math.isnan(bv):
            out.append(None)
        else:
            out.append(round(float(sv) - float(bv), 2))
    return out


def build_market_history(closes: pd.DataFrame, sectors: dict, bench: tuple,
                         label: str, days: int, weeks: int) -> dict:
    """終値DataFrameから、対ベンチマーク相対の日次/週次ヒートマップ用dictを組み立てる。"""
    bench_daily = daily_returns(closes[bench[0]])
    dates = list(bench_daily.index[-days:])
    date_labels = [d.strftime("%Y-%m-%d") for d in dates]

    bench_weekly = weekly_returns(closes[bench[0]])
    wdates = list(bench_weekly.index[-weeks:])
    wdate_labels = [d.strftime("%Y-%m-%d") for d in wdates]

    brow = {
        "ticker": bench[0], "name": bench[1],
        "daily": _rel_series(bench_daily, bench_daily, dates),
        "weekly": _rel_series(bench_weekly, bench_weekly, wdates),
    }

    sec_rows = []
    for tkr, name in sectors.items():
        if tkr not in closes.columns:
            continue
        daily = _rel_series(daily_returns(closes[tkr]), bench_daily, dates)
        weekly = _rel_series(weekly_returns(closes[tkr]), bench_weekly, wdates)
        dvals = [x for x in daily if x is not None]
        wvals = [x for x in weekly if x is not None]
        sec_rows.append({
            "ticker": tkr, "name": name,
            "daily": daily, "cum": round(sum(dvals), 2) if dvals else None,
            "weekly": weekly, "weekly_cum": round(sum(wvals), 2) if wvals else None,
        })

    sec_rows.sort(key=lambda x: (x["cum"] is None, -(x["cum"] or 0)))
    return {
        "label": label,
        "benchmark": brow,
        "dates": date_labels,
        "weekly_dates": wdate_labels,
        "sectors": sec_rows,
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_sector_history.py -q`
Expected: PASS（4 tests）

---

### Task 3: sector_history.py — collect_market と main を新関数に接続

**Files:**
- Modify: `scripts/sector_history.py`

- [ ] **Step 1: collect_market を build_market_history 利用に置き換え**

既存 `collect_market`（31-71行）を丸ごと次に置き換える。取得期間は週次13週の pct_change に十分な余裕を持たせ `6mo` にする。

```python
def collect_market(sectors: dict, bench: tuple, label: str,
                   days: int, weeks: int) -> dict:
    tickers = list(sectors.keys()) + [bench[0]]
    raw = yf.download(tickers, period="6mo", interval="1d",
                      auto_adjust=True, progress=False)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    return build_market_history(closes, sectors, bench, label, days, weeks)
```

- [ ] **Step 2: main に --weeks を追加し weeks を渡す**

`main()` 内の argparse と呼び出しを更新する。`--days` の直後に追加:

```python
    ap.add_argument("--weeks", type=int, default=13)
```

`result` 初期化と各 `collect_market` 呼び出しを次に置き換える:

```python
    result = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "days": args.days, "weeks": args.weeks}
    if args.market in ("jp", "both"):
        print("Fetching JP daily history (TOPIX-17)...", file=sys.stderr)
        result["jp"] = collect_market(JP_SECTORS, JP_BENCH, "日本株 (TOPIX-17)",
                                       args.days, args.weeks)
    if args.market in ("us", "both"):
        print("Fetching US daily history (SPDR)...", file=sys.stderr)
        result["us"] = collect_market(US_SECTORS, US_BENCH, "米国株 (S&P500セクター)",
                                       args.days, args.weeks)
```

- [ ] **Step 3: 既存テストが引き続き通ることを確認**

Run: `python -m pytest tests -q`
Expected: PASS（Task2 の4 tests、collection エラーなし）

- [ ] **Step 4: ライブ実行でスモーク確認（ネットワーク必要）**

Run: `python scripts/sector_history.py --market both`
Expected: `data/history_latest.json` が更新され、`jp.weekly_dates` が約13件、各セクターに `weekly` 配列があること。確認コマンド:
`python -c "import json;d=json.load(open('data/history_latest.json',encoding='utf-8'));print(len(d['jp']['weekly_dates']), len(d['jp']['sectors'][0]['weekly']), d['jp']['benchmark']['daily'][:3])"`
Expected: 先頭2数が概ね 13、benchmark.daily 先頭が `[0.0, 0.0, 0.0]`

---

### Task 4: sector_history_report.py — 相対表示・週次表・ベンチ行非表示

**Files:**
- Modify: `scripts/sector_history_report.py`
- Test: `tests/test_sector_history_report.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_sector_history_report.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_sector_history_report.py -q`
Expected: FAIL（`color_scale` が現状 `(sections)` 1引数、build_html にベンチ行/週次表が無い）

- [ ] **Step 3: color_scale をキー指定・セクターのみに変更**

`color_scale`（17-28行）を置き換える:

```python
def color_scale(sections, key):
    """指定キーのセル絶対値95パーセンタイルを色スケール上限にする(セクター行のみ)."""
    vals = []
    for m in sections:
        for row in m["sectors"]:
            vals += [abs(v) for v in row.get(key, []) if v is not None]
    if not vals:
        return 1.0
    vals.sort()
    idx = int(len(vals) * 0.95)
    cap = vals[min(idx, len(vals) - 1)]
    return cap if cap > 0 else 1.0
```

- [ ] **Step 4: market_table を汎用 heatmap_table に置き換え**

`market_table`（45-78行）を丸ごと次に置き換える。日次/週次の両方を描け、ベンチマーク行は描かない。

```python
def heatmap_table(m, cap, dates_key, cells_key, cum_key, unit_label):
    dates = m[dates_key]
    ths = ['<th class="name">セクター</th>',
           f'<th class="cum">{unit_label}</th>']
    prev_week = None
    is_daily = dates_key == "dates"
    for d in dates:
        cls = ""
        if is_daily:
            import datetime as _dt
            y, mo, da = d.split("-")
            wk = _dt.date(int(y), int(mo), int(da)).isocalendar()[1]
            cls = "wk" if wk != prev_week else ""
            prev_week = wk
        ths.append(f'<th class="d {cls}"><span>{short_date(d)}</span></th>')

    def row_html(row):
        cum = row.get(cum_key)
        cum_txt = f'{cum:+.1f}%' if cum is not None else "—"
        cum_col, _ = cell_color(cum, cap * 6) if cum is not None else ("#f3f4f6", "")
        cells = ""
        for i, v in enumerate(row.get(cells_key, [])):
            bg, tc = cell_color(v, cap)
            title = f'{row["name"]} {short_date(dates[i])}: {v:+.2f}%' if v is not None else "—"
            cells += f'<td class="d" style="background:{bg};color:{tc}" title="{title}"></td>'
        return (f'<tr><td class="name">{row["name"]}</td>'
                f'<td class="cum" style="background:{cum_col}">{cum_txt}</td>{cells}</tr>')

    body = "".join(row_html(r) for r in m["sectors"])
    return f"""
  <div class="scroll"><table>
    <thead><tr>{''.join(ths)}</tr></thead>
    <tbody>{body}</tbody>
  </table></div>"""
```

- [ ] **Step 5: build_html を日次＋週次の2表構成に変更**

`build_html`（81-132行）内の `cap = color_scale(sections)` 以降と `tables` 生成、本文の見出し・凡例文言を更新する。関数を次に置き換える:

```python
def build_html(data):
    sections = [data[k] for k in ("jp", "us") if k in data]
    cap_d = color_scale(sections, "daily")
    cap_w = color_scale(sections, "weekly")
    parts = []
    for m in sections:
        parts.append(f'<h2>{m["label"]} '
                     f'<span class="asof">日次相対 直近{len(m["dates"])}営業日 '
                     f'({m["dates"][0]} 〜 {m["dates"][-1]})</span></h2>')
        parts.append(heatmap_table(m, cap_d, "dates", "daily", "cum", "累計"))
        parts.append(f'<h3 class="sub">週次相対 直近{len(m["weekly_dates"])}週 '
                     f'({m["weekly_dates"][0]} 〜 {m["weekly_dates"][-1]})</h3>')
        parts.append(heatmap_table(m, cap_w, "weekly_dates", "weekly", "weekly_cum", "累計"))
    tables = "".join(parts)
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>セクター相対ヒートマップ {data.get('generated_at','')[:10]}</title>
<style>
  body {{ font-family:"Segoe UI","Hiragino Sans","Meiryo",sans-serif; margin:24px auto;
          max-width:1240px; color:#111827; background:#f9fafb; }}
  h1 {{ font-size:22px; }}
  h2 {{ font-size:17px; border-bottom:2px solid #e5e7eb; padding-bottom:6px; margin-top:32px; }}
  h3.sub {{ font-size:14px; color:#374151; margin:20px 0 6px; }}
  .asof {{ font-size:12px; color:#6b7280; font-weight:normal; margin-left:10px; }}
  .scroll {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; background:#fff; font-size:11px; }}
  th,td {{ border:1px solid #eceef1; padding:0; }}
  th.name,td.name {{ text-align:left; padding:4px 8px; position:sticky; left:0;
                     background:#fff; min-width:120px; white-space:nowrap; z-index:1; }}
  th.name {{ background:#1f2937; color:#fff; }}
  th.cum,td.cum {{ text-align:right; padding:4px 6px; min-width:52px;
                   font-variant-numeric:tabular-nums; position:sticky; left:120px; z-index:1; }}
  th.cum {{ background:#1f2937; color:#fff; }}
  td.cum {{ background:#fff; }}
  th.d {{ height:56px; padding:0 1px; color:#6b7280; font-weight:500; vertical-align:bottom; }}
  th.d span {{ writing-mode:vertical-rl; transform:rotate(180deg); white-space:nowrap;
               font-size:9px; margin:2px auto; }}
  td.d {{ width:16px; height:20px; }}
  th.d.wk,td.d.wk {{ border-left:2px solid #9ca3af; }}
  .legend {{ display:flex; gap:16px; margin:10px 0; font-size:12px; color:#374151;
             align-items:center; flex-wrap:wrap; }}
  .sw {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-1px; }}
  .note {{ font-size:11px; color:#6b7280; margin-top:24px; line-height:1.6; }}
</style></head><body>
<h1>📆 セクター相対ヒートマップ <span class="asof">生成: {data.get('generated_at','')}</span></h1>
<p style="font-size:13px;color:#374151">
セクター × 期間の「対ベンチマーク相対リターン(%)」。緑=指数を上回る / 赤=下回る、濃いほど乖離大。
日次表の太い縦線は週の区切り。右端「累計」列は期間内の相対リターン単純累計。
マウスを当てると各セルの値が出ます。ベンチマーク自身は基準(0)のため行として表示していません。</p>
<div class="legend">
  <span><span class="sw" style="background:rgba(16,150,105,.9)"></span> 指数を上回る</span>
  <span><span class="sw" style="background:rgba(220,38,38,.9)"></span> 指数を下回る</span>
  <span><span class="sw" style="background:#f3f4f6"></span> データなし/休場</span>
  <span>色の濃さは各表のセル絶対値95パーセンタイルで正規化</span>
</div>
{tables}
<p class="note">
データソース: Yahoo Finance (日本=TOPIX-17 ETF 1617-1633 / 米国=SPDRセクターETF)。
ETF終値ベースの騰落率をベンチマーク(TOPIX / S&P500)相対で表示。祝日・休場日はデータなし(灰色)。
本レポートは情報提供のみを目的とし、投資勧誘を意図するものではありません。</p>
</body></html>"""
```

- [ ] **Step 6: テストが通ることを確認**

Run: `python -m pytest tests/test_sector_history_report.py -q`
Expected: PASS（6 tests）

- [ ] **Step 7: ライブHTMLをスモーク確認（Task3の実行後）**

Run: `python scripts/sector_history_report.py`
Expected: `reports/history_latest.html` が生成され、`grep -c "週次相対" reports/history_latest.html` が市場数（both なら 2）と一致。

---

### Task 5: sector_report.py — Markdown→HTML 変換

**Files:**
- Modify: `scripts/sector_report.py`
- Test: `tests/test_sector_report_analysis.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_sector_report_analysis.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_sector_report_analysis.py -q`
Expected: FAIL（`md_to_html` 未定義で ImportError）

- [ ] **Step 3: 変換関数を実装**

`scripts/sector_report.py` の import 群（14行目 `from datetime import datetime` の後）に追加:

```python
import html as _html
import re
import sys
```

`fmt` 関数の直後（44行目付近）に追加:

```python
def _inline(s: str) -> str:
    """エスケープ済み文字列に **太字** のインライン変換だけ施す。"""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def md_to_html(md: str) -> str:
    """見出し(#〜###)・箇条書き(-,*)・段落・**太字** だけを扱う軽量変換。"""
    out, para = [], []
    in_ul = False

    def flush_para():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw in (md or "").split("\n"):
        line = raw.strip()
        if not line:
            flush_para()
            close_ul()
            continue
        h = re.match(r"(#{1,3})\s+(.*)", line)
        if h:
            flush_para()
            close_ul()
            level = len(h.group(1)) + 2   # # -> h3, ## -> h4, ### -> h5
            out.append(f"<h{level}>{_inline(_html.escape(h.group(2)))}</h{level}>")
            continue
        if line.startswith(("- ", "* ")):
            flush_para()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(_html.escape(line[2:]))}</li>")
            continue
        para.append(_inline(_html.escape(line)))
    flush_para()
    close_ul()
    return "\n".join(out)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m pytest tests/test_sector_report_analysis.py -q`
Expected: PASS（5 tests）

---

### Task 6: sector_report.py — 背景分析セクションと --analysis

**Files:**
- Modify: `scripts/sector_report.py`
- Test: `tests/test_sector_report_analysis.py`（追記）

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_sector_report_analysis.py` の末尾に追加:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m pytest tests/test_sector_report_analysis.py -q`
Expected: FAIL（`analysis_section` 未定義、`build_html` が analysis 引数を取らない）

- [ ] **Step 3: analysis_section を実装**

`scripts/sector_report.py` の `md_to_html` の直後に追加:

```python
def analysis_section(analysis: dict) -> str:
    """背景分析 dict から HTMLセクションを生成。null/欠落ブロックは省略。"""
    labels = [("jp", "日本株の背景分析"),
              ("us", "米国株の背景分析"),
              ("strategist", "統合見解（ストラテジスト）")]
    blocks = []
    for key, title in labels:
        md = analysis.get(key)
        if not md:
            continue
        blocks.append(f'<div class="abox"><h3>{title}</h3>{md_to_html(md)}</div>')
    if not blocks:
        return ""
    return '<section class="bg"><h2>🔎 背景分析</h2>' + "".join(blocks) + "</section>"
```

- [ ] **Step 4: build_html に analysis を組み込む**

`build_html`（現 107行目付近）のシグネチャと本文を更新する。冒頭行を:

```python
def build_html(data: dict, analysis: dict = None) -> str:
    sections = "".join(market_section(data[k]) for k in ("jp", "us") if k in data)
    bg = analysis_section(analysis) if analysis else ""
```

に変更し、`<style>` 内（`.note {{ ... }}` の直前）に次を追加:

```python
  .bg {{ margin-top: 32px; }}
  .abox {{ background:#fff; border-radius:8px; padding:12px 16px; margin:12px 0;
           box-shadow:0 1px 3px rgba(0,0,0,.08); font-size:13px; line-height:1.7; }}
  .abox h3 {{ font-size:15px; margin:4px 0 8px; }}
```

さらに本文テンプレートの `{sections}` 行の直後に `{bg}` を挿入する:

```python
{sections}
{bg}
<p class="note">
```

- [ ] **Step 5: main に --analysis を追加**

`main()` の argparse に追加（`--outdir` の後）:

```python
    ap.add_argument("--analysis", default=None,
                    help="背景分析JSON (data/analysis_latest.json) のパス")
```

読み込みと build 呼び出しを次に更新する（`with open(args.input...)` ブロックの後）:

```python
    analysis = None
    if args.analysis:
        try:
            with open(args.analysis, encoding="utf-8") as f:
                analysis = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: analysis file を読めません {args.analysis}: {e}",
                  file=sys.stderr)
```

`build_html(data)` を呼んでいる2箇所（`out` と `latest` 書き込み）を `build_html(data, analysis)` に変更する。

- [ ] **Step 6: テストが通ることを確認**

Run: `python -m pytest tests/test_sector_report_analysis.py -q`
Expected: PASS（9 tests）

- [ ] **Step 7: 全テストと壊れJSONフォールバックを確認**

Run: `python -m pytest tests -q`
Expected: PASS（全 tests）

Run: `python scripts/sector_report.py --analysis data/does_not_exist.json`
Expected: stderr に warning が出るが正常終了し `reports/latest.html` が生成される（背景分析なし）。

---

### Task 7: SKILL.md を新ワークフローに更新

**Files:**
- Modify: `.claude/skills/sector-analysis/SKILL.md`

- [ ] **Step 1: ワークフロー節を書き換える**

`## ワークフロー` 見出しから `## 判定ロジック (要点)` の直前までを、次の内容に置き換える:

````markdown
## ワークフロー

### Step 1: データ取得と判定
```
python scripts/sector_data.py --market both
```
- 出力: `data/sector_YYYY-MM-DD.json` と `data/latest.json`
- 日本のみ/米国のみは `--market jp` / `--market us`

### Step 2: 時系列データ取得（相対ヒートマップ用）
```
python scripts/sector_history.py --market both
```
- 出力: `data/history_YYYY-MM-DD.json` と `data/history_latest.json`
- 直近30営業日の日次＋直近13週の週次、いずれも対ベンチマーク相対リターン

### Step 3: HTMLレポート生成
```
python scripts/sector_report.py
python scripts/sector_history_report.py
```
- `reports/latest.html`（判定＋4期間ヒートマップ）と
  `reports/history_latest.html`（日次・週次の相対ヒートマップ）を生成
- 生成後、両ファイルのパスをmarkdownリンクで提示する

### Step 4: チャットでのサマリー提示
`data/latest.json` を読み、強まった/弱まったセクター・総合判定の上位下位を簡潔にまとめ、
可能なら show_widget でヒートマップをインライン表示する。

### Step 5: 深掘りの要否を選択式で確認
Step 4 のサマリーを出した後、AskUserQuestion で「背景分析の深掘りをしますか？」を質問する。
選択肢:
- 日米＋統合で深掘り（推奨）／日本だけ深掘り／米国だけ深掘り／しない（サマリーのみで終了）

### Step 6: 深掘り実行（Step 5 で「しない」以外が選ばれた場合のみ）
1. スコープに応じてエージェントを起動:
   - 日米統合: `jp-sector-analyst` と `us-sector-analyst` を並列起動（Agentを同一メッセージで2回）→
     両者の結果を `sector-strategist` に渡し統合見解を得る
   - 日本のみ/米国のみ: 該当アナリスト1本のみ（統合はスキップ）
   - 各エージェントに `data/latest.json` のパスと担当市場の要約を渡す。出力はMarkdownで受け取る
2. 結果を `data/analysis_latest.json` に保存（Writeツール）:
   ```json
   {"as_of":"...","generated_at":"...","scope":"both|jp|us",
    "jp":"…md… or null","us":"…md… or null","strategist":"…md… or null"}
   ```
3. `python scripts/sector_report.py --analysis data/analysis_latest.json` で主レポート再生成
4. `reports/latest.html` と `reports/history_latest.html` のリンクを提示し、チャットにも深掘り要点を出す

### 後から深掘りだけ実行
「深掘りして」「背景分析して」「なぜ」「詳しく」等と言われたら、データ取得・ヒートマップ再生成は
せず、既存 `data/latest.json` を前提に Step 6 の共通手順だけ実行する（`data/latest.json` が
無ければ Step 1-3 を先に実行）。スコープが不明確なら AskUserQuestion で確認する。
````

- [ ] **Step 2: 記述の妥当性を目視確認**

Run: `python - <<'PY'
import pathlib, re
t = pathlib.Path(".claude/skills/sector-analysis/SKILL.md").read_text(encoding="utf-8")
for k in ["sector_history.py", "--analysis", "AskUserQuestion", "後から深掘り"]:
    assert k in t, k
print("SKILL.md OK")
PY`
Expected: `SKILL.md OK`

---

### Task 8: CLAUDE.md を更新

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 構成表に history スクリプトを追記**

`## 構成` の表の `sector_report.py` の行の直後に2行追加:

```markdown
| Script | `scripts/sector_history.py` | 日次30日・週次13週の対ベンチマーク相対リターン → JSON | — |
| Script | `scripts/sector_history_report.py` | 相対ヒートマップHTML（日次・週次） | — |
```

- [ ] **Step 2: データ仕様に相対時系列を追記**

`## データ仕様` の `出力:` 行の直後に追加:

```markdown
- 相対時系列: `data/history_YYYY-MM-DD.json`（日次30営業日・週次13週の対ベンチマーク相対リターン）→ `reports/history_latest.html`
- 深掘り: `data/analysis_latest.json`（jp/us/strategist の背景分析md）→ `sector_report.py --analysis` で `reports/latest.html` に「背景分析」セクション追記
```

- [ ] **Step 3: 「エージェントチームの使い分け」を更新**

`## エージェントチームの使い分け` の箇条書きを次に置き換える:

```markdown
- 通常の「セクター分析して」→ スキルのStep1-4（スクリプト実行＋サマリー）を実行し、Step5で深掘り要否を選択式で確認
- 深掘り選択時／後から「詳しく」「なぜ」→ jp/us-sector-analyst（スコープに応じて）→ sector-strategist で統合し、結果を `data/analysis_latest.json` 経由で `reports/latest.html` に反映
- 「データだけ更新して」→ sector-data-collector
```

- [ ] **Step 4: 目視確認**

Run: `python - <<'PY'
import pathlib
t = pathlib.Path("CLAUDE.md").read_text(encoding="utf-8")
for k in ["sector_history.py", "sector_history_report.py", "analysis_latest.json", "選択式"]:
    assert k in t, k
print("CLAUDE.md OK")
PY`
Expected: `CLAUDE.md OK`

---

### Task 9: 統合検証（エンドツーエンド・ネットワーク必要）

**Files:** なし（実行のみ）

- [ ] **Step 1: 全テスト**

Run: `python -m pytest tests -q`
Expected: PASS（全 tests）

- [ ] **Step 2: パイプライン一括実行**

Run:
```
python scripts/sector_data.py --market both
python scripts/sector_history.py --market both
python scripts/sector_report.py
python scripts/sector_history_report.py
```
Expected: 4スクリプトが正常終了。`reports/latest.html` と `reports/history_latest.html` が更新される。

- [ ] **Step 3: 相対ヒートマップHTMLの内容確認**

Run: `python - <<'PY'
import pathlib
h = pathlib.Path("reports/history_latest.html").read_text(encoding="utf-8")
assert h.count("週次相対") >= 2, h.count("週次相対")
assert "TOPIX" not in h and "SPY" not in h   # ベンチマーク行は非表示
assert "指数を上回る" in h
print("history html OK")
PY`
Expected: `history html OK`

- [ ] **Step 4: 背景分析ダミーで --analysis 経路を確認**

Run:
```
python - <<'PY'
import json
json.dump({"as_of":"2026-07-03","generated_at":"x","scope":"both",
           "jp":"# 日本\n\n- 銀行が **強い**","us":"# 米国\n\nヘルスケア主導","strategist":"金融ローテーション"},
          open("data/analysis_latest.json","w",encoding="utf-8"), ensure_ascii=False)
PY
python scripts/sector_report.py --analysis data/analysis_latest.json
python - <<'PY'
import pathlib
h = pathlib.Path("reports/latest.html").read_text(encoding="utf-8")
for k in ["背景分析","日本株の背景分析","米国株の背景分析","統合見解","<strong>強い</strong>"]:
    assert k in h, k
print("analysis html OK")
PY
```
Expected: `analysis html OK`

- [ ] **Step 5: 後方互換の最終確認**

Run: `python scripts/sector_report.py && python - <<'PY'
import pathlib
assert "背景分析" not in pathlib.Path("reports/latest.html").read_text(encoding="utf-8")
print("backcompat OK")
PY`
Expected: `backcompat OK`（--analysis なしでは背景分析セクションが出ない）

---

## Self-Review メモ

- 仕様カバレッジ: 拡張A（相対日次=Task2-4 / 週次=Task2-4）、拡張B（md変換=Task5 / --analysis=Task6 / SKILL=Task7 / CLAUDE=Task8）、後方互換（Task6 Step7, Task9 Step5）をカバー。
- プレースホルダなし: 各コード手順に完全なコードを記載。
- 型/名称整合: `build_market_history` / `weekly_returns` / `_rel_series` / `heatmap_table` /
  `color_scale(sections, key)` / `md_to_html` / `_inline` / `analysis_section` /
  `build_html(data, analysis=None)` はタスク間で一貫。
