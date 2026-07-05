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
