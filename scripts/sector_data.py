# -*- coding: utf-8 -*-
"""セクター強弱データ収集スクリプト.

日本株 (TOPIX-17 ETF) と米国株 (SPDRセクターETF) の
1日 / 1週間 / 1ヶ月 / 3ヶ月 リターンを計算し、
ベンチマーク (TOPIX / S&P500) に対する相対強度から
強気・弱気を判定して JSON に出力する。

Usage:
    python scripts/sector_data.py [--market jp|us|both] [--outdir data]
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

# TOPIX-17シリーズ ETF (NEXT FUNDS)
JP_SECTORS = {
    "1617.T": "食品",
    "1618.T": "エネルギー資源",
    "1619.T": "建設・資材",
    "1620.T": "素材・化学",
    "1621.T": "医薬品",
    "1622.T": "自動車・輸送機",
    "1623.T": "鉄鋼・非鉄",
    "1624.T": "機械",
    "1625.T": "電機・精密",
    "1626.T": "情報通信・サービス",
    "1627.T": "電力・ガス",
    "1628.T": "運輸・物流",
    "1629.T": "商社・卸売",
    "1630.T": "小売",
    "1631.T": "銀行",
    "1632.T": "金融（除く銀行）",
    "1633.T": "不動産",
}
JP_BENCH = ("1306.T", "TOPIX")

# SPDR Select Sector ETF (米国11セクター)
US_SECTORS = {
    "XLK": "情報技術",
    "XLC": "コミュニケーション",
    "XLY": "一般消費財",
    "XLP": "生活必需品",
    "XLV": "ヘルスケア",
    "XLF": "金融",
    "XLI": "資本財",
    "XLB": "素材",
    "XLE": "エネルギー",
    "XLU": "公益事業",
    "XLRE": "不動産",
}
US_BENCH = ("SPY", "S&P500")

# 営業日ベースの期間定義
HORIZONS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63}
# 判定スコアの期間ウェイト (長期ほど重い)
WEIGHTS = {"1d": 1, "1w": 2, "1m": 3, "3m": 4}


def pct_return(closes: pd.Series, n: int):
    """n営業日前比のリターン(%)。データ不足時は None。"""
    s = closes.dropna()
    if len(s) <= n:
        return None
    prev = float(s.iloc[-(n + 1)])
    last = float(s.iloc[-1])
    if prev == 0 or math.isnan(prev) or math.isnan(last):
        return None
    return round((last / prev - 1) * 100, 2)


def verdict_from_score(score: int) -> str:
    if score >= 6:
        return "強気"
    if score >= 2:
        return "やや強気"
    if score > -2:
        return "中立"
    if score > -6:
        return "やや弱気"
    return "弱気"


# 期間別5段階を出すときの五分位ラベル (強い順)
_QUINTILE = ["強気", "やや強気", "中立", "やや弱気", "弱気"]


def _assign_quintile(rows: list, keyfunc, field: str):
    """keyfunc(row) の昇順(小さい=強い)で並べ、五分位で5段階を row[...][field] に格納。

    keyfunc が None を返す行は「データ不足」とする。
    """
    ranked = [r for r in rows if keyfunc(r) is not None]
    ranked.sort(key=keyfunc)
    n = len(ranked)
    for i, r in enumerate(ranked):
        idx = min(int((i / n) * 5), 4) if n else 2
        r.setdefault("verdict_by_horizon", {})[field] = _QUINTILE[idx]
    for r in rows:
        if keyfunc(r) is None:
            r.setdefault("verdict_by_horizon", {})[field] = "データ不足"


def _yf_closes(tickers: list) -> pd.DataFrame:
    raw = yf.download(tickers, period="9mo", interval="1d",
                      auto_adjust=True, progress=False)
    return raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]


def analyze_market(sectors: dict, bench: tuple, label: str) -> dict:
    return analyze_closes(_yf_closes(list(sectors.keys()) + [bench[0]]),
                          sectors, bench, label)


def analyze_closes(closes: pd.DataFrame, sectors: dict, bench: tuple, label: str) -> dict:
    bench_close = closes[bench[0]]
    bench_ret = {h: pct_return(bench_close, n) for h, n in HORIZONS.items()}

    rows = []
    for tkr, name in sectors.items():
        if tkr not in closes.columns:
            continue
        ret = {h: pct_return(closes[tkr], n) for h, n in HORIZONS.items()}
        rel = {}
        for h in HORIZONS:
            if ret[h] is None or bench_ret[h] is None:
                rel[h] = None
            else:
                rel[h] = round(ret[h] - bench_ret[h], 2)
        # スコア: 相対リターンの符号 × 期間ウェイト (レンジ -10〜+10)
        score = 0
        for h, w in WEIGHTS.items():
            if rel[h] is not None:
                score += w if rel[h] > 0 else -w
        rows.append({
            "ticker": tkr, "name": name,
            "ret": ret, "rel": rel,
            "score": score, "verdict": verdict_from_score(score),
        })

    # 期間ごとの相対強度ランク (1=最強)
    for h in HORIZONS:
        order = sorted(
            [r for r in rows if r["rel"][h] is not None],
            key=lambda r: r["rel"][h], reverse=True)
        for i, r in enumerate(order, 1):
            r.setdefault("rank", {})[h] = i

    # 期間別5段階 (iPhone簡易表示用): 短期=1d+1w / 中期=1m / 長期=3m のランク五分位
    def _rk(r, h):
        return r.get("rank", {}).get(h)

    def _short_key(r):
        a, b = _rk(r, "1d"), _rk(r, "1w")
        return (a + b) if (a is not None and b is not None) else None

    _assign_quintile(rows, _short_key, "short")
    _assign_quintile(rows, lambda r: _rk(r, "1m"), "mid")
    _assign_quintile(rows, lambda r: _rk(r, "3m"), "long")

    # 勢い: 短期ランク(1d,1w平均) − 長期ランク(1m,3m平均)。負なら強まっている
    n_sec = len(rows)
    for r in rows:
        rk = r.get("rank", {})
        if all(h in rk for h in HORIZONS):
            shift = (rk["1d"] + rk["1w"]) / 2 - (rk["1m"] + rk["3m"]) / 2
            r["rank_shift"] = round(shift, 1)
            thresh = max(1.5, n_sec * 0.12)
            if shift <= -thresh:
                r["momentum"] = "強まっている"
            elif shift >= thresh:
                r["momentum"] = "弱まっている"
            else:
                r["momentum"] = "横ばい"
        else:
            r["rank_shift"] = None
            r["momentum"] = "データ不足"

    rows.sort(key=lambda r: (-r["score"], r.get("rank_shift") or 0))
    last_date = closes.dropna(how="all").index[-1].strftime("%Y-%m-%d")
    return {
        "label": label,
        "benchmark": {"ticker": bench[0], "name": bench[1], "ret": bench_ret},
        "as_of": last_date,
        "sectors": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["jp", "us", "both"], default="both")
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()

    result = {"generated_at": datetime.now().isoformat(timespec="seconds")}
    if args.market in ("jp", "both"):
        import jquants
        jq = jquants.jp_index_closes()
        if jq is not None:
            print("Fetching JP sectors via J-Quants (TOPIX-17)...", file=sys.stderr)
            result["jp"] = analyze_closes(jq, jquants.JP_JQ_SECTORS,
                                          jquants.JP_JQ_BENCH, "日本株 (TOPIX-17)")
        else:
            print("Fetching JP sectors via yfinance (TOPIX-17 ETF)...", file=sys.stderr)
            result["jp"] = analyze_market(JP_SECTORS, JP_BENCH, "日本株 (TOPIX-17)")
    if args.market in ("us", "both"):
        print("Fetching US sectors (SPDR)...", file=sys.stderr)
        result["us"] = analyze_market(US_SECTORS, US_BENCH, "米国株 (S&P500セクター)")

    os.makedirs(args.outdir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    for path in (os.path.join(args.outdir, f"sector_{today}.json"),
                 os.path.join(args.outdir, "latest.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
