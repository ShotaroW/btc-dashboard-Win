import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def in_memory_db(tmp_path):
    return str(tmp_path / "test_btc.db")


@pytest.fixture
def db(in_memory_db):
    import src.database as db_mod

    with patch.object(db_mod, "DB_NAME", in_memory_db):
        db_mod.ensure_table_exists()
        yield db_mod


def make_timestamp(days_ago: int = 0, hours_ago: int = 0) -> str:
    return (
        pd.Timestamp.now().floor("s")
        - pd.Timedelta(days=days_ago, hours=hours_ago)
    ).strftime("%Y-%m-%d %H:%M:%S")


def test_ensure_table_exists(db):
    with sqlite3.connect(db.DB_NAME) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='btc_price'"
        )
        assert cursor.fetchone() is not None


def test_save_and_load_price(db):
    db.save_price(make_timestamp(days_ago=1), 5000000.0)
    df = db.load_data()

    assert len(df) == 1
    assert df.iloc[0]["price_jpy"] == pytest.approx(5000000.0)


def test_save_duplicate_is_ignored(db):
    timestamp = make_timestamp(days_ago=1)
    db.save_price(timestamp, 5000000.0)
    db.save_price(timestamp, 9999999.0)
    df = db.load_data()

    assert len(df) == 1


def test_save_bulk_data(db):
    records = [
        (make_timestamp(days_ago=3), 4800000.0),
        (make_timestamp(days_ago=2), 4900000.0),
        (make_timestamp(days_ago=1), 5000000.0),
    ]
    db.save_bulk_data(records)
    df = db.load_data()

    assert len(df) == 3


def test_prune_old_data_removes_entries(db):
    with sqlite3.connect(db.DB_NAME) as conn:
        conn.executemany(
            "INSERT INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
            [
                ("2023-12-31 23:59:59", 1.0),
                ("2024-01-01 00:00:00", 2.0),
                ("2024-01-02 00:00:00", 3.0),
            ],
        )

    db.prune_old_data(reference_time="2024-01-08 00:00:00", retention_days=7)
    df = db.load_data()

    assert len(df) == 2
    assert "2023-12-31 23:59:59" not in df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()


def test_load_data_returns_datetime(db):
    db.save_price(make_timestamp(days_ago=1), 5000000.0)
    df = db.load_data()

    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])


def test_load_empty_returns_empty_dataframe(db):
    df = db.load_data()
    assert df.empty
