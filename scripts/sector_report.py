# -*- coding: utf-8 -*-
"""セクター強弱 HTMLヒートマップレポート生成.

sector_data.py が出力した JSON を読み込み、
セクター × 期間 (1日/1週間/1ヶ月/3ヶ月) のヒートマップと
強まった/弱まったセクターのサマリーを 1枚の自己完結HTML に出力する。

Usage:
    python scripts/sector_report.py [--input data/latest.json] [--outdir reports]
"""
import argparse
import json
import os
from datetime import datetime
import html as _html
import re
import sys

HORIZON_LABELS = {"1d": "1日", "1w": "1週間", "1m": "1ヶ月", "3m": "3ヶ月"}

VERDICT_COLORS = {
    "強気": "#059669", "やや強気": "#34d399", "中立": "#9ca3af",
    "やや弱気": "#f87171", "弱気": "#dc2626",
}
MOMENTUM_ICONS = {
    "強まっている": ("▲", "#059669"), "弱まっている": ("▼", "#dc2626"),
    "横ばい": ("→", "#9ca3af"), "データ不足": ("?", "#9ca3af"),
}


def cell_color(value, max_abs):
    """リターン値を赤(負)〜白(0)〜緑(正)の背景色に変換."""
    if value is None or max_abs == 0:
        return "#ffffff", "#6b7280"
    ratio = max(-1.0, min(1.0, value / max_abs))
    alpha = abs(ratio) * 0.85
    rgb = "16,150,105" if ratio > 0 else "220,38,38"
    text = "#111827" if alpha < 0.55 else "#ffffff"
    return f"rgba({rgb},{alpha:.2f})", text


def fmt(v, sign=True):
    if v is None:
        return "—"
    s = f"{v:+.2f}%" if sign else f"{v:.2f}%"
    return s


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


def market_section(m: dict) -> str:
    sectors = m["sectors"]
    # 期間ごとの色スケール (絶対リターンの最大絶対値)
    max_abs = {}
    for h in HORIZON_LABELS:
        vals = [abs(s["ret"][h]) for s in sectors if s["ret"][h] is not None]
        bench_v = m["benchmark"]["ret"].get(h)
        if bench_v is not None:
            vals.append(abs(bench_v))
        max_abs[h] = max(vals) if vals else 0

    rows_html = []
    # ベンチマーク行
    bench_cells = ""
    for h in HORIZON_LABELS:
        v = m["benchmark"]["ret"].get(h)
        bg, tc = cell_color(v, max_abs[h])
        bench_cells += f'<td class="num" style="background:{bg};color:{tc}">{fmt(v)}</td>'
    rows_html.append(
        f'<tr class="bench"><td>{m["benchmark"]["name"]}<span class="tkr">'
        f'{m["benchmark"]["ticker"]}</span></td><td>—</td><td>—</td>{bench_cells}</tr>')

    for s in sectors:
        icon, icolor = MOMENTUM_ICONS.get(s["momentum"], ("?", "#9ca3af"))
        vcolor = VERDICT_COLORS.get(s["verdict"], "#9ca3af")
        cells = ""
        for h in HORIZON_LABELS:
            v = s["ret"][h]
            bg, tc = cell_color(v, max_abs[h])
            rel = s["rel"][h]
            rel_s = f'<span class="rel">vs指数 {fmt(rel)}</span>' if rel is not None else ""
            cells += (f'<td class="num" style="background:{bg};color:{tc}">'
                      f'{fmt(v)}{rel_s}</td>')
        rows_html.append(
            f'<tr><td>{s["name"]}<span class="tkr">{s["ticker"]}</span></td>'
            f'<td><span class="badge" style="background:{vcolor}">{s["verdict"]}</span></td>'
            f'<td style="color:{icolor};font-weight:700">{icon} {s["momentum"]}</td>'
            f'{cells}</tr>')

    improving = [s for s in sectors if s["momentum"] == "強まっている"]
    weakening = [s for s in sectors if s["momentum"] == "弱まっている"]
    imp_s = "、".join(s["name"] for s in improving) or "なし"
    weak_s = "、".join(s["name"] for s in weakening) or "なし"

    return f"""
  <section>
    <h2>{m["label"]} <span class="asof">基準日: {m["as_of"]}</span></h2>
    <div class="summary">
      <div class="sumbox up"><strong>▲ 勢いが強まっているセクター</strong><p>{imp_s}</p></div>
      <div class="sumbox down"><strong>▼ 勢いが弱まっているセクター</strong><p>{weak_s}</p></div>
    </div>
    <table>
      <thead><tr>
        <th>セクター</th><th>判定</th><th>勢い</th>
        <th>1日</th><th>1週間</th><th>1ヶ月</th><th>3ヶ月</th>
      </tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
  </section>"""


def build_html(data: dict, analysis: dict = None) -> str:
    sections = "".join(market_section(data[k]) for k in ("jp", "us") if k in data)
    bg = analysis_section(analysis) if analysis else ""
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>セクター強弱レポート {data.get('generated_at', '')[:10]}</title>
<style>
  body {{ font-family: "Segoe UI", "Hiragino Sans", "Meiryo", sans-serif;
         margin: 24px auto; max-width: 1100px; color: #111827; background: #f9fafb; }}
  h1 {{ font-size: 22px; }}
  h2 {{ font-size: 18px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; margin-top: 36px; }}
  .asof {{ font-size: 12px; color: #6b7280; font-weight: normal; margin-left: 10px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); font-size: 13px; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }}
  th {{ background: #1f2937; color: #fff; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; min-width: 90px; }}
  .rel {{ display: block; font-size: 10px; opacity: .85; }}
  .tkr {{ display: block; font-size: 10px; color: #9ca3af; }}
  .bench td {{ background: #f3f4f6; font-weight: 600; }}
  .badge {{ color: #fff; border-radius: 10px; padding: 2px 8px; font-size: 11px;
            white-space: nowrap; }}
  .summary {{ display: flex; gap: 12px; margin: 12px 0; flex-wrap: wrap; }}
  .sumbox {{ flex: 1; min-width: 260px; background: #fff; border-radius: 8px;
             padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
             border-left: 4px solid #9ca3af; font-size: 13px; }}
  .sumbox.up {{ border-left-color: #059669; }}
  .sumbox.down {{ border-left-color: #dc2626; }}
  .sumbox p {{ margin: 4px 0 0; }}
  .bg {{ margin-top: 32px; }}
  .abox {{ background:#fff; border-radius:8px; padding:12px 16px; margin:12px 0;
           box-shadow:0 1px 3px rgba(0,0,0,.08); font-size:13px; line-height:1.7; }}
  .abox h3 {{ font-size:15px; margin:4px 0 8px; }}
  .note {{ font-size: 11px; color: #6b7280; margin-top: 24px; line-height: 1.6; }}
</style></head><body>
<h1>📊 セクター強弱レポート <span class="asof">生成: {data.get('generated_at', '')}</span></h1>
<p style="font-size:13px;color:#374151">
判定は各期間のベンチマーク相対リターンの加重スコア (3ヶ月を最重視)。
「勢い」は短期 (1日・1週間) と中長期 (1ヶ月・3ヶ月) の相対強度ランクの変化で、
セクターローテーションの方向を示します。セルの色は絶対リターン (緑=上昇 / 赤=下落)。</p>
{sections}
{bg}
<p class="note">
データソース: Yahoo Finance (日本=TOPIX-17 ETF 1617-1633 / 米国=SPDRセクターETF)。
ETFの終値ベースのため、分配金・売買代金の薄い銘柄では指数と乖離する場合があります。
本レポートは情報提供のみを目的とし、投資勧誘を意図するものではありません。</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/latest.json")
    ap.add_argument("--outdir", default="reports")
    ap.add_argument("--analysis", default=None,
                    help="背景分析JSON (data/analysis_latest.json) のパス")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    analysis = None
    if args.analysis:
        try:
            with open(args.analysis, encoding="utf-8") as f:
                analysis = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: analysis file を読めません {args.analysis}: {e}",
                  file=sys.stderr)

    os.makedirs(args.outdir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out = os.path.join(args.outdir, f"sector_report_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_html(data, analysis))
    latest = os.path.join(args.outdir, "latest.html")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(build_html(data, analysis))
    print(out)


if __name__ == "__main__":
    main()
