# -*- coding: utf-8 -*-
"""GitHub Pages 配信用サイトを組み立てる.

reports/ にある最新のHTMLを site/ にコピーし、ランディング index.html を生成する。
GitHub Actions からも、ローカルからも実行できる（存在するレポートだけを載せる）。

Usage:
    python scripts/build_site.py [--reports reports] [--outdir site]
"""
import argparse
import glob
import json
import os
import shutil
from datetime import datetime


def _latest(reports: str, pattern: str):
    files = sorted(glob.glob(os.path.join(reports, pattern)))
    return files[-1] if files else None


def build_mobile(latest_json: str):
    """data/latest.json から iPhone/Claude 向けの軽量JSONを作る。

    各セクターを 短期/中期/長期 の5段階と総合判定・勢いだけに絞る。
    """
    if not (latest_json and os.path.exists(latest_json)):
        return None
    with open(latest_json, encoding="utf-8") as f:
        d = json.load(f)
    out = {"generated_at": d.get("generated_at"), "markets": {}}
    for mk in ("jp", "us"):
        m = d.get(mk)
        if not m:
            continue
        out["markets"][mk] = {
            "label": m.get("label"),
            "as_of": m.get("as_of"),
            "benchmark": m.get("benchmark", {}).get("name"),
            "sectors": [
                {
                    "name": s.get("name"),
                    "short": s.get("verdict_by_horizon", {}).get("short"),
                    "mid": s.get("verdict_by_horizon", {}).get("mid"),
                    "long": s.get("verdict_by_horizon", {}).get("long"),
                    "overall": s.get("verdict"),
                    "momentum": s.get("momentum"),
                }
                for s in m.get("sectors", [])
            ],
        }
    return out


def build_index(items: list, gen: str) -> str:
    if items:
        cards = "\n".join(
            f'''    <a class="card" href="{dest}">
      <div class="ttl">{label}</div>
      <div class="desc">{desc}</div>
      <div class="go">開く →</div>
    </a>''' for dest, label, desc in items)
    else:
        cards = '<p>レポートがまだ生成されていません。</p>'
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>セクター強弱ダッシュボード</title>
<style>
  body {{ font-family:"Segoe UI","Hiragino Sans","Meiryo",sans-serif; margin:0;
          padding:20px 16px 40px; color:#111827; background:#f9fafb;
          max-width:720px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .gen {{ font-size:12px; color:#6b7280; margin:0 0 20px; }}
  .card {{ display:block; text-decoration:none; color:inherit; background:#fff;
           border-radius:12px; padding:16px 18px; margin:0 0 12px;
           box-shadow:0 1px 3px rgba(0,0,0,.08); border:1px solid #eef0f3; }}
  .card:active {{ background:#f3f4f6; }}
  .ttl {{ font-size:16px; font-weight:600; }}
  .desc {{ font-size:13px; color:#6b7280; margin-top:2px; }}
  .go {{ font-size:13px; color:#2563eb; margin-top:8px; }}
  .note {{ font-size:11px; color:#9ca3af; margin-top:24px; line-height:1.6; }}
</style></head><body>
<h1>📊 セクター強弱ダッシュボード</h1>
<p class="gen">最終更新: {gen}</p>
{cards}
<p class="note">データソース: Yahoo Finance。ETF終値ベース。情報提供のみを目的とし、投資勧誘を意図するものではありません。</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--outdir", default="site")
    ap.add_argument("--data", default="data")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    items = []

    # iPhone/Claude が fetch する公開データ (フル + 軽量版)
    latest_json = os.path.join(args.data, "latest.json")
    if os.path.exists(latest_json):
        shutil.copyfile(latest_json, os.path.join(args.outdir, "latest.json"))
    mobile = build_mobile(latest_json)
    if mobile is not None:
        with open(os.path.join(args.outdir, "mobile.json"), "w", encoding="utf-8") as f:
            json.dump(mobile, f, ensure_ascii=False, indent=2)

    def add(src, dest, label, desc):
        if src and os.path.exists(src):
            shutil.copyfile(src, os.path.join(args.outdir, dest))
            items.append((dest, label, desc))

    add(_latest(args.reports, "sector_trend_*.html"), "trend.html",
        "3ヶ月騰落率チャート", "各セクターの対ベンチマーク3ヶ月累積騰落率（日本・米国）")
    add(os.path.join(args.reports, "latest.html"), "heatmap.html",
        "セクター強弱ヒートマップ", "1日/1週/1ヶ月/3ヶ月の強弱判定")
    add(os.path.join(args.reports, "history_latest.html"), "history.html",
        "日次ヒートマップ", "直近営業日ごとのリターン推移")

    gen = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(args.outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(items, gen))
    print(os.path.join(args.outdir, "index.html"))


if __name__ == "__main__":
    main()
