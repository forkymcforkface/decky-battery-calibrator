import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from battery_calibrator.settings import SettingsManager

logger = logging.getLogger("BatteryCalibrator.Scheduler")


class CalibrationScheduler:
    def __init__(self, settings: SettingsManager):
        self._settings = settings
        self._task: asyncio.Task | None = None
        self._on_calibration_due: Callable | None = None
        self._running = False

    def on_calibration_due(self, callback: Callable) -> None:
        self._on_calibration_due = callback

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self) -> None:
        while self._running:
            due = self._calculate_due()
            now = datetime.now()
            if due and now >= due:
                self._notify_due()
                self._settings.set("last_calibration", now.isoformat())
                due = self._calculate_due()
            wait = min((due - datetime.now()).total_seconds(), 86400) if due else 86400
            if wait > 0:
                await asyncio.sleep(wait)

    def _notify_due(self) -> None:
        if self._on_calibration_due:
            logger.info("Calibration is due, triggering")
            self._on_calibration_due()

    def _calculate_due(self) -> datetime | None:
        last_raw = self._settings.get("last_calibration")
        interval_days = self._settings.get("calibration_interval_days", 14)
        if last_raw:
            return datetime.fromisoformat(last_raw) + timedelta(days=interval_days)
        return datetime.now()

    def next_due(self) -> str | None:
        due = self._calculate_due()
        return due.isoformat() if due else None

    def snooze(self, days: int = 1) -> None:
        self._settings.set("last_calibration", (datetime.now() + timedelta(days=days)).isoformat())
