import os
import sqlite3
import threading
from datetime import datetime, timezone

from battery_calibrator._constants import HISTORY_FILENAME


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


class HistoryDatabase:
    def __init__(self, runtime_dir: str):
        self._path = os.path.join(runtime_dir, HISTORY_FILENAME)
        self._lock = threading.Lock()
        self._conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS battery_snapshots (
                recorded_at TIMESTAMP NOT NULL,
                capacity INTEGER,
                status TEXT,
                health_pct REAL,
                cycle_count INTEGER,
                power_watts REAL,
                ac_connected INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS calibration_log (
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                result TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_time
            ON battery_snapshots(recorded_at)
        """)
        try:
            cur.execute("ALTER TABLE battery_snapshots ADD COLUMN temp_celsius REAL")
        except sqlite3.OperationalError:
            pass
        conn.commit()

    def record_snapshot(
        self,
        capacity: int | None,
        status: str | None,
        health_pct: float | None,
        cycle_count: int | None,
        power_watts: float | None,
        ac_connected: bool,
        temp_celsius: float | None = None,
    ) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO battery_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (_ts(), capacity, status, health_pct, cycle_count, power_watts, int(ac_connected), temp_celsius),
            )
            self._conn.commit()

    def log_calibration_start(self) -> str:
        ts = _ts()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("INSERT INTO calibration_log (started_at) VALUES (?)", (ts,))
            self._conn.commit()
        return ts

    def log_calibration_end(self, started_at: str, result: str) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "UPDATE calibration_log SET completed_at = ?, result = ? WHERE started_at = ?",
                (_ts(), result, started_at),
            )
            self._conn.commit()

    def get_recent_snapshots(self, limit: int = 100) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM battery_snapshots ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_calibration_history(self, limit: int = 20) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM calibration_log ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def prune_snapshots(self, days: int = 90) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM battery_snapshots WHERE recorded_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            deleted = cur.rowcount
            self._conn.commit()
        return deleted
