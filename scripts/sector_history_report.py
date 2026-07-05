# -*- coding: utf-8 -*-
"""セクター日次ヒートマップ HTMLレポート生成.

sector_history.py が出力した history_latest.json を読み込み、
日本株 / 米国株それぞれについて「セクター × 直近30営業日 (1日ごと)」の
リターンヒートマップを 1枚の自己完結HTML に出力する。

Usage:
    python scripts/sector_history_report.py [--input data/history_latest.json] [--outdir reports]
"""
import argparse
import json
import os
from datetime import datetime


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


def cell_color(v, cap):
    if v is None:
        return "#f3f4f6", "#9ca3af"
    ratio = max(-1.0, min(1.0, v / cap))
    alpha = abs(ratio) * 0.9
    rgb = "16,150,105" if ratio > 0 else "220,38,38"
    text = "#111827" if alpha < 0.55 else "#ffffff"
    return f"rgba({rgb},{alpha:.2f})", text


def short_date(iso):
    return iso[5:].replace("-", "/")


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
データソース: Yahoo Finance (日本=東証17業種 ETF 1617-1633 / 米国=SPDRセクターETF)。
ETF終値ベースの騰落率を各市場のベンチマーク相対で表示。祝日・休場日はデータなし(灰色)。
本レポートは情報提供のみを目的とし、投資勧誘を意図するものではありません。</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/history_latest.json")
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(args.outdir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    html = build_html(data)
    out = os.path.join(args.outdir, f"sector_history_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(args.outdir, "history_latest.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(out)


if __name__ == "__main__":
    main()
