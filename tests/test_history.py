import sqlite3
import tempfile
from pathlib import Path

import pytest
from battery_calibrator.history import HistoryDatabase


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as d:
        yield HistoryDatabase(d)


def test_connect_creates_db_file(db):
    assert Path(db._path).exists()


def test_record_snapshot(db):
    db.record_snapshot(85, "Charging", 95.0, 42, 4.2, True, 32.5)
    rows = db.get_recent_snapshots(10)
    assert len(rows) == 1
    assert rows[0]["capacity"] == 85
    assert rows[0]["status"] == "Charging"
    assert rows[0]["health_pct"] == 95.0
    assert rows[0]["cycle_count"] == 42
    assert rows[0]["power_watts"] == 4.2
    assert rows[0]["ac_connected"] == 1
    assert rows[0]["temp_celsius"] == 32.5


def test_record_snapshot_with_nulls(db):
    db.record_snapshot(None, "Unknown", None, None, None, False, None)
    rows = db.get_recent_snapshots(10)
    assert len(rows) == 1
    assert rows[0]["capacity"] is None
    assert rows[0]["ac_connected"] == 0
    assert rows[0]["temp_celsius"] is None


def test_record_snapshot_default_temp(db):
    db.record_snapshot(85, "Charging", 95.0, 42, 4.2, True)
    rows = db.get_recent_snapshots(10)
    assert rows[0]["temp_celsius"] is None


def test_log_calibration_start(db):
    ts = db.log_calibration_start()
    assert ts is not None
    assert len(ts) > 0


def test_log_calibration_end(db):
    ts = db.log_calibration_start()
    db.log_calibration_end(ts, "complete")
    rows = db.get_calibration_history(10)
    assert len(rows) == 1
    assert rows[0]["result"] == "complete"


def test_log_calibration_end_without_start(db):
    db.log_calibration_end("nonexistent_ts", "complete")
    rows = db.get_calibration_history(10)
    assert len(rows) == 0


def test_get_recent_snapshots_limit(db):
    for i in range(20):
        db.record_snapshot(i, "Charging", 95.0, 42, 4.2, True)
    rows = db.get_recent_snapshots(5)
    assert len(rows) == 5


def test_get_recent_snapshots_ordered_desc(db):
    db.record_snapshot(50, "Discharging", 95.0, 42, 4.2, False)
    db.record_snapshot(60, "Charging", 95.0, 42, 4.2, True)
    rows = db.get_recent_snapshots(10)
    assert rows[0]["capacity"] == 60
    assert rows[1]["capacity"] == 50


def test_get_calibration_history_limit(db):
    for _ in range(10):
        db.log_calibration_start()
    rows = db.get_calibration_history(3)
    assert len(rows) == 3


def test_multiple_calibrations(db):
    ts1 = db.log_calibration_start()
    ts2 = db.log_calibration_start()
    db.log_calibration_end(ts1, "complete")
    db.log_calibration_end(ts2, "timed_out")
    rows = db.get_calibration_history(10)
    assert len(rows) == 2
    results = {r["result"] for r in rows}
    assert results == {"complete", "timed_out"}


def test_close(db):
    db.close()
    with pytest.raises(sqlite3.ProgrammingError):
        db.record_snapshot(85, "Charging", 95.0, 42, 4.2, True)
