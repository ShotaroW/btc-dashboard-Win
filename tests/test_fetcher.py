"""fetcher.py のテスト（外部APIはモック）"""

from unittest.mock import MagicMock, patch

import pytest

from src.fetcher import fetch_btc_price, fetch_historical_data


def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@patch("src.fetcher.requests.get")
def test_fetch_btc_price_success(mock_get):
    """正常系: BTC価格と為替レートが取得できること"""
    mock_get.side_effect = [
        _make_response({"price": "75000.0"}),           # Binance
        _make_response({"result": 150.0}),              # exchangerate.host
    ]

    timestamp, price = fetch_btc_price()

    assert isinstance(timestamp, str)
    assert price == pytest.approx(75000.0 * 150.0)


@patch("src.fetcher.requests.get")
def test_fetch_btc_price_fallback_fx(mock_get):
    """為替プライマリAPI失敗時にフォールバックAPIを使うこと"""
    import requests

    primary_error = requests.exceptions.ConnectionError("primary failed")
    mock_get.side_effect = [
        _make_response({"price": "75000.0"}),           # Binance
        MagicMock(side_effect=primary_error),           # exchangerate.host 失敗
        _make_response({"result": "success", "rates": {"JPY": 148.0}}),  # fallback
    ]

    timestamp, price = fetch_btc_price()

    assert price == pytest.approx(75000.0 * 148.0)


@patch("src.fetcher.requests.get")
def test_fetch_btc_price_raises_when_all_fx_fail(mock_get):
    """全ての為替APIが失敗したとき RuntimeError を送出すること"""
    import requests

    error = requests.exceptions.ConnectionError("failed")
    mock_get.side_effect = [
        _make_response({"price": "75000.0"}),
        MagicMock(side_effect=error),
        MagicMock(side_effect=error),
    ]

    with pytest.raises(RuntimeError, match="USD/JPY"):
        fetch_btc_price()


@patch("src.fetcher.requests.get")
def test_fetch_historical_data_success(mock_get):
    """正常系: 履歴データがリストで返ること"""
    prices = [[1704067200000, 6000000.0], [1704070800000, 6100000.0]]
    mock_get.return_value = _make_response({"prices": prices})

    records = fetch_historical_data(days=1)

    assert len(records) == 2
    assert records[0][1] == pytest.approx(6000000.0)


@patch("src.fetcher.requests.get")
def test_fetch_historical_data_rate_limit_returns_empty(mock_get):
    """429レート制限のとき空リストを返すこと"""
    import requests

    resp = MagicMock()
    resp.status_code = 429
    http_error = requests.exceptions.HTTPError(response=resp)
    resp.raise_for_status.side_effect = http_error
    mock_get.return_value = resp

    records = fetch_historical_data(days=7)

    assert records == []
