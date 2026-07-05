import numpy as np
import pandas as pd

from sector_data import analyze_closes


def make_closes():
    """ベンチ + 成長率の異なる5セクター。強さの順序は全期間で一貫する。"""
    idx = pd.bdate_range("2026-01-01", periods=70)  # 3ヶ月(63営業日)より長く
    n = np.arange(len(idx))
    data = {"B": pd.Series(100.0 * (1.010 ** n), index=idx)}
    rates = {"S1": 1.015, "S2": 1.012, "S3": 1.010, "S4": 1.008, "S5": 1.005}
    for k, r in rates.items():
        data[k] = pd.Series(100.0 * (r ** n), index=idx)
    return pd.DataFrame(data)


SECTORS = {"S1": "最強", "S2": "強", "S3": "中", "S4": "弱", "S5": "最弱"}


def _by_name(result):
    return {s["name"]: s for s in result["sectors"]}


def test_verdict_by_horizon_has_all_buckets():
    m = analyze_closes(make_closes(), SECTORS, ("B", "Bench"), "L")
    for s in m["sectors"]:
        vbh = s["verdict_by_horizon"]
        assert set(vbh) == {"short", "mid", "long"}


def test_strongest_and_weakest_quintiles():
    m = analyze_closes(make_closes(), SECTORS, ("B", "Bench"), "L")
    rows = _by_name(m)
    # 成長率が一貫して最大/最小なので、全期間で五分位の両端になる
    for h in ("short", "mid", "long"):
        assert rows["最強"]["verdict_by_horizon"][h] == "強気"
        assert rows["最弱"]["verdict_by_horizon"][h] == "弱気"


def test_quintile_labels_are_valid():
    m = analyze_closes(make_closes(), SECTORS, ("B", "Bench"), "L")
    valid = {"強気", "やや強気", "中立", "やや弱気", "弱気", "データ不足"}
    for s in m["sectors"]:
        for v in s["verdict_by_horizon"].values():
            assert v in valid
