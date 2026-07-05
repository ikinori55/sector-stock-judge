import pandas as pd

import jquants


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_jq_index_closes_builds_dataframe(monkeypatch):
    # コードごとに2日分の終値を返す(pagination なし)。エンベロープキー名に依存しないことも確認。
    pages = {
        "0000": {"indices": [
            {"Date": "2026-07-01", "Code": "0000", "C": 2800.0},
            {"Date": "2026-07-02", "Code": "0000", "C": 2820.0}]},
        "008E": {"data": [
            {"Date": "2026-07-01", "Code": "008E", "C": 400.0},
            {"Date": "2026-07-02", "Code": "008E", "C": 410.0}]},
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        assert headers["x-api-key"] == "KEY"
        return _FakeResp(pages[params["code"]])

    monkeypatch.setattr(jquants.requests, "get", fake_get)

    df = jquants.jq_index_closes(["0000", "008E"], "2026-07-01", "2026-07-02", "KEY")
    assert list(df.columns) == ["0000", "008E"]
    assert len(df) == 2
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.loc["2026-07-02", "008E"] == 410.0


def test_jq_index_closes_follows_pagination(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        if "pagination_key" not in params:
            calls["n"] += 1
            return _FakeResp({"indices": [{"Date": "2026-07-01", "C": 100.0}],
                              "pagination_key": "next"})
        return _FakeResp({"indices": [{"Date": "2026-07-02", "C": 105.0}]})

    monkeypatch.setattr(jquants.requests, "get", fake_get)
    df = jquants.jq_index_closes(["0000"], "2026-07-01", "2026-07-02", "KEY")
    assert len(df) == 2
    assert df.loc["2026-07-02", "0000"] == 105.0


def test_jq_index_closes_raises_when_empty(monkeypatch):
    monkeypatch.setattr(jquants.requests, "get",
                        lambda *a, **k: _FakeResp({"indices": []}))
    try:
        jquants.jq_index_closes(["0000"], "2026-07-01", "2026-07-02", "KEY")
        assert False, "should raise"
    except RuntimeError:
        pass


def test_jp_index_closes_none_without_key(monkeypatch):
    monkeypatch.delenv("JQUANTS_API_KEY", raising=False)
    assert jquants.jp_index_closes() is None
