import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from battery_calibrator.scheduler import CalibrationScheduler


class DictSettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def set_many(self, updates):
        self._data.update(updates)

    def get_all(self):
        return dict(self._data)


@pytest.fixture
def settings():
    return DictSettings({
        "last_calibration": None,
        "calibration_interval_days": 14,
    })


@pytest.fixture
def scheduler(settings):
    return CalibrationScheduler(settings)


def test_next_due_returns_now_when_no_history(scheduler):
    due = scheduler.next_due()
    assert due is not None


def test_next_due_with_last_calibration():
    settings = DictSettings({
        "last_calibration": "2026-06-01T00:00:00",
        "calibration_interval_days": 14,
    })
    s = CalibrationScheduler(settings)
    due = s.next_due()
    assert due == "2026-06-15T00:00:00"


def test_snooze():
    now = datetime(2026, 6, 14, 12, 0, 0)
    settings = DictSettings()
    with patch("battery_calibrator.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        s = CalibrationScheduler(settings)
        s.snooze(3)
        assert settings.get("last_calibration") == "2026-06-17T12:00:00"


@pytest.mark.asyncio
async def test_start_stop(scheduler):
    await scheduler.start()
    assert scheduler._running is True
    assert scheduler._task is not None

    await scheduler.stop()
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_start_idempotent(scheduler):
    await scheduler.start()
    t1 = scheduler._task
    await scheduler.start()
    assert scheduler._task is t1
    await scheduler.stop()


@pytest.mark.asyncio
async def test_start_triggers_when_due():
    settings = DictSettings({
        "last_calibration": "2020-01-01T00:00:00",
        "calibration_interval_days": 14,
    })
    cb = MagicMock()
    s = CalibrationScheduler(settings)
    s.on_calibration_due(cb)
    await s.start()
    await asyncio.sleep(0.05)
    await s.stop()
    cb.assert_called_once()


@pytest.mark.asyncio
async def test_no_trigger_when_not_due():
    future = (datetime.now() + timedelta(days=13)).isoformat()
    settings = DictSettings({
        "last_calibration": future,
        "calibration_interval_days": 14,
    })
    cb = MagicMock()
    s = CalibrationScheduler(settings)
    await s.start()
    await asyncio.sleep(0.05)
    await s.stop()
    cb.assert_not_called()
