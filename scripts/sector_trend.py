# -*- coding: utf-8 -*-
"""セクター3ヶ月騰落率(対ベンチマーク)ラインチャート HTML生成.

直近63営業日(≒3ヶ月)の各セクターETFとベンチマーク(日本=TOPIX / 米国=S&P500)の
累積騰落率(%)を起点0%にリベースした折れ線で描画する。
日本株と米国株を1枚のHTML(Chart.js CDN)にまとめ、ファイル名に YYYYMMDD を付けて出力する。

Usage:
    python scripts/sector_trend.py [--market jp|us|both] [--days 63] [--outdir reports]
"""
import argparse
import json
import os
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

from sector_data import JP_SECTORS, JP_BENCH, US_SECTORS, US_BENCH


def _cum(series: pd.Series) -> list:
    """終値系列を起点=0%にリベースした累積騰落率(%)配列にする。"""
    s = series.astype(float)
    valid = s.dropna()
    if valid.empty:
        return [None] * len(s)
    base = float(valid.iloc[0])
    if base == 0:
        return [None] * len(s)
    return [round((float(v) / base - 1) * 100, 2) if pd.notna(v) else None for v in s]


def _yf_closes(tickers: list) -> pd.DataFrame:
    raw = yf.download(tickers, period="6mo", interval="1d",
                      auto_adjust=True, progress=False)
    return raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]


def collect(closes: pd.DataFrame, sectors: dict, bench: tuple, label: str, days: int) -> dict:
    closes = closes.dropna(how="all").tail(days)
    dates = [d.strftime("%Y-%m-%d") for d in closes.index]

    series = [{"name": bench[1], "ticker": bench[0],
               "data": _cum(closes[bench[0]]), "bench": True}]
    secs = []
    for tkr, name in sectors.items():
        if tkr in closes.columns:
            secs.append({"name": name, "ticker": tkr,
                         "data": _cum(closes[tkr]), "bench": False})
    # 最終騰落率の降順に並べ替え(凡例を見やすく)
    secs.sort(key=lambda s: (s["data"][-1] is None, -(s["data"][-1] or 0)))
    series.extend(secs)
    return {"label": label, "bench_name": bench[1],
            "as_of": dates[-1] if dates else "", "dates": dates, "series": series}


def _chart_block(m: dict, idx: int) -> str:
    payload = json.dumps(m, ensure_ascii=False)
    cid = f"c{idx}"
    return f"""
<section class="mkt">
  <h2>{m['label']} <span class="light">— セクター3ヶ月騰落率 (対{m['bench_name']})</span></h2>
  <p class="sub">起点0%にそろえた累積騰落率。太点線が {m['bench_name']}。基準日: {m['as_of']}</p>
  <div class="card"><div class="wrap"><canvas id="{cid}"
    role="img" aria-label="{m['label']}の各セクターとベンチマークの3ヶ月累積騰落率の折れ線グラフ"></canvas></div></div>
</section>
<script>
(function(){{
  const M = {payload};
  function color(i, n) {{ return 'hsl(' + Math.round(360 * i / n) + ',65%,45%)'; }}
  const secCount = M.series.filter(s => !s.bench).length;
  let si = 0;
  const datasets = M.series.map(s => {{
    const isB = s.bench;
    const col = isB ? '#111827' : color(si++, secCount);
    return {{ label: s.name, data: s.data, borderColor: col, backgroundColor: col,
      borderWidth: isB ? 3 : 1.5, borderDash: isB ? [6, 3] : [],
      pointRadius: 0, pointHoverRadius: 3, tension: 0.15, order: isB ? 0 : 1 }};
  }});
  new Chart(document.getElementById('{cid}'), {{
    type: 'line', data: {{ labels: M.dates, datasets }},
    options: {{ responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }},
        tooltip: {{ callbacks: {{ label: c => c.dataset.label + ': ' + (c.parsed.y >= 0 ? '+' : '') + c.parsed.y + '%' }} }} }},
      scales: {{ x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 10 }} }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ callback: v => (v >= 0 ? '+' : '') + v + '%', font: {{ size: 10 }} }},
             title: {{ display: true, text: '累積騰落率' }} }} }} }},
  }});
}})();
</script>"""


def build_html(markets: list) -> str:
    gen = datetime.now().isoformat(timespec="seconds")
    ndays = len(markets[0]["dates"]) if markets else 0
    blocks = "".join(_chart_block(m, i) for i, m in enumerate(markets))
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>セクター3ヶ月騰落率 {gen[:10]}</title>
<style>
  body {{ font-family:"Segoe UI","Hiragino Sans","Meiryo",sans-serif; margin:0; padding:16px;
          color:#111827; background:#f9fafb; max-width:1100px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  h2 {{ font-size:16px; margin:28px 0 2px; }}
  .light {{ font-weight:normal; color:#6b7280; }}
  .gen {{ font-size:12px; color:#6b7280; margin:0 0 8px; }}
  .sub {{ font-size:12px; color:#6b7280; margin:0 0 10px; }}
  .card {{ background:#fff; border-radius:12px; padding:12px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  .wrap {{ position:relative; width:100%; height:62vh; min-height:340px; }}
  .note {{ font-size:11px; color:#6b7280; margin-top:16px; line-height:1.6; }}
</style></head><body>
<h1>📈 セクター3ヶ月騰落率（対ベンチマーク）</h1>
<p class="gen">生成: {gen}／各線は起点0%にそろえた累積騰落率。凡例をタップでセクター表示を切替できます。</p>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
{blocks}
<p class="note">データソース: Yahoo Finance。ETF終値ベースの累積騰落率(直近{ndays}営業日)。
本レポートは情報提供のみを目的とし、投資勧誘を意図するものではありません。</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["jp", "us", "both"], default="both")
    ap.add_argument("--days", type=int, default=63)
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    markets = []

    if args.market in ("jp", "both"):
        import jquants
        jq = jquants.jp_index_closes()
        if jq is not None:
            print("Fetching JP trend via J-Quants (TOPIX-17)...", file=sys.stderr)
            markets.append(collect(jq, jquants.JP_JQ_SECTORS, jquants.JP_JQ_BENCH,
                                   "日本株 (TOPIX-17)", args.days))
        else:
            print("Fetching JP trend via yfinance (TOPIX-17 ETF)...", file=sys.stderr)
            closes = _yf_closes(list(JP_SECTORS.keys()) + [JP_BENCH[0]])
            markets.append(collect(closes, JP_SECTORS, JP_BENCH,
                                   "日本株 (TOPIX-17)", args.days))

    if args.market in ("us", "both"):
        print("Fetching US trend via yfinance (SPDR)...", file=sys.stderr)
        closes = _yf_closes(list(US_SECTORS.keys()) + [US_BENCH[0]])
        markets.append(collect(closes, US_SECTORS, US_BENCH,
                               "米国株 (S&P500セクター)", args.days))

    ts = datetime.now().strftime("%Y%m%d")
    out = os.path.join(args.outdir, f"sector_trend_{ts}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_html(markets))
    print(out)


if __name__ == "__main__":
    main()
