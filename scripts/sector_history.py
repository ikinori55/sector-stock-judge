# -*- coding: utf-8 -*-
"""セクター日次ヒートマップ用データ収集スクリプト.

直近 N 営業日 (デフォルト30) の「1日ごと」のセクター別リターン(%)を
日本株 (TOPIX-17 ETF) / 米国株 (SPDRセクターETF) について収集し JSON に出力する。
sector_data.py がセクター定義を持つので import して再利用する。

Usage:
    python scripts/sector_history.py [--market jp|us|both] [--days 30] [--outdir data]
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

from sector_data import JP_SECTORS, JP_BENCH, US_SECTORS, US_BENCH


def daily_returns(closes: pd.Series):
    """終値系列から日次リターン(%)系列を返す (index=日付)。"""
    s = closes.dropna()
    ret = s.pct_change() * 100
    return ret.dropna()


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


def collect_market(sectors: dict, bench: tuple, label: str,
                   days: int, weeks: int) -> dict:
    tickers = list(sectors.keys()) + [bench[0]]
    raw = yf.download(tickers, period="6mo", interval="1d",
                      auto_adjust=True, progress=False)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    return build_market_history(closes, sectors, bench, label, days, weeks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["jp", "us", "both"], default="both")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--weeks", type=int, default=13)
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()

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

    os.makedirs(args.outdir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    for path in (os.path.join(args.outdir, f"history_{today}.json"),
                 os.path.join(args.outdir, "history_latest.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(os.path.join(args.outdir, "history_latest.json"))


if __name__ == "__main__":
    main()
