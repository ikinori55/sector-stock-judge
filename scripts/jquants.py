# -*- coding: utf-8 -*-
"""J-Quants (JPX) API V2 クライアント — TOPIX-17 セクター指数の日次終値取得.

V2 は APIキー方式。ダッシュボードで発行したキーを環境変数 JQUANTS_API_KEY に入れ、
`x-api-key` ヘッダーで送る。指数日次は GET /v2/indices/bars/daily。

TOPIX-17 セクター指数(0080-0090) と TOPIX(0000) の終値を取得し、
列=指数コード / index=日付 の pandas.DataFrame(=既存スクリプトの"closes"互換) にして返す。
"""
import datetime as _dt
import os

import pandas as pd
import requests

API_BASE = "https://api.jquants.com/v2"

# TOPIX-17 セクター指数コード → 表示名(既存 sector_data.JP_SECTORS と同じ名称)
JP_JQ_SECTORS = {
    "0080": "食品",
    "0081": "エネルギー資源",
    "0082": "建設・資材",
    "0083": "素材・化学",
    "0084": "医薬品",
    "0085": "自動車・輸送機",
    "0086": "鉄鋼・非鉄",
    "0087": "機械",
    "0088": "電機・精密",
    "0089": "情報通信・サービス",
    "008A": "電力・ガス",
    "008B": "運輸・物流",
    "008C": "商社・卸売",
    "008D": "小売",
    "008E": "銀行",
    "008F": "金融（除く銀行）",
    "0090": "不動産",
}
JP_JQ_BENCH = ("0000", "TOPIX")


def get_api_key():
    """環境変数から APIキーを取得。未設定なら None。"""
    return os.environ.get("JQUANTS_API_KEY") or None


def _rows(payload: dict) -> list:
    """レスポンスJSONから明細リストを取り出す(エンベロープのキー名に依存しない)。"""
    for v in payload.values():
        if isinstance(v, list):
            return v
    return []


def _fetch_one(code: str, start: str, end: str, api_key: str) -> dict:
    """1指数の日次終値を {date: close} で返す(pagination対応)。"""
    headers = {"x-api-key": api_key}
    params = {"code": code, "from": start, "to": end}
    url = f"{API_BASE}/indices/bars/daily"
    out = {}
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        for row in _rows(js):
            c = row.get("C")
            d = row.get("Date")
            if c is not None and d is not None:
                out[d] = float(c)
        pk = js.get("pagination_key")
        if not pk:
            break
        params["pagination_key"] = pk
    return out


def jq_index_closes(codes, start: str, end: str, api_key: str) -> pd.DataFrame:
    """指数コード群の日次終値を 列=コード / index=日付 の DataFrame で返す。"""
    frames = {}
    for code in codes:
        s = _fetch_one(code, start, end, api_key)
        if s:
            frames[code] = pd.Series(s)
    if not frames:
        raise RuntimeError(
            "J-Quants: 指数データを取得できませんでした。"
            "APIキー・プラン権限(TOPIX-17はPremium)・指数コードを確認してください。")
    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def jp_index_closes(days_back: int = 220) -> pd.DataFrame:
    """JP TOPIX-17 + TOPIX の終値DataFrame。APIキー未設定なら None を返す。"""
    key = get_api_key()
    if not key:
        return None
    end = _dt.date.today().isoformat()
    start = (_dt.date.today() - _dt.timedelta(days=days_back)).isoformat()
    codes = list(JP_JQ_SECTORS) + [JP_JQ_BENCH[0]]
    return jq_index_closes(codes, start, end, key)
