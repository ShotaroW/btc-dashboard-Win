"""database.py のテスト（インメモリSQLiteを使用）"""

import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def in_memory_db(tmp_path):
    """テスト用の一時DBパスを返す"""
    return str(tmp_path / "test_btc.db")


def make_db_module(db_path: str):
    """DB_NAMEを差し替えたdatabaseモジュールの関数を返す"""
    import importlib
    import src.database as db_mod

    with patch.object(db_mod, "DB_NAME", db_path):
        yield db_mod


@pytest.fixture
def db(in_memory_db):
    import src.database as db_mod
    with patch.object(db_mod, "DB_NAME", in_memory_db):
        db_mod.ensure_table_exists()
        yield db_mod


def test_ensure_table_exists(db):
    """テーブルが作成されること"""
    with sqlite3.connect(db.DB_NAME) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='btc_price'"
        )
        assert cursor.fetchone() is not None


def test_save_and_load_price(db):
    """1件保存して読み込めること"""
    db.save_price("2024-01-01 12:00:00", 5000000.0)
    df = db.load_data()

    assert len(df) == 1
    assert df.iloc[0]["price_jpy"] == pytest.approx(5000000.0)


def test_save_duplicate_is_ignored(db):
    """同じタイムスタンプは重複して保存されないこと"""
    db.save_price("2024-01-01 12:00:00", 5000000.0)
    db.save_price("2024-01-01 12:00:00", 9999999.0)
    df = db.load_data()

    assert len(df) == 1


def test_save_bulk_data(db):
    """複数件まとめて保存できること"""
    records = [
        ("2024-01-01 10:00:00", 4800000.0),
        ("2024-01-01 11:00:00", 4900000.0),
        ("2024-01-01 12:00:00", 5000000.0),
    ]
    db.save_bulk_data(records)
    df = db.load_data()

    assert len(df) == 3


def test_load_data_returns_datetime(db):
    """timestamp列がdatetime型で返ること"""
    db.save_price("2024-01-01 12:00:00", 5000000.0)
    df = db.load_data()

    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])


def test_load_empty_returns_empty_dataframe(db):
    """データなしのとき空DataFrameが返ること"""
    df = db.load_data()
    assert df.empty
