import asyncio
import logging
from collections.abc import Callable
from enum import Enum

from battery_calibrator._constants import CALIBRATION_DRAIN_THRESHOLD, CALIBRATION_TIMEOUT_HOURS
from battery_calibrator.battery import BatteryReader, BatterySnapshot
from battery_calibrator.charge_control import ChargeControl

logger = logging.getLogger("BatteryCalibrator.Calibration")


class CalibrationPhase(Enum):
    IDLE = "idle"
    UNPLUG_AND_DRAIN = "unplug_and_drain"
    PLUG_IN_AND_CHARGE = "plug_in_and_charge"
    COMPLETE = "complete"
    TIMED_OUT = "timed_out"


class CalibrationEngine:
    def __init__(
        self,
        charge_control: ChargeControl,
        battery_reader: BatteryReader,
    ):
        self._charge = charge_control
        self._battery = battery_reader
        self._phase = CalibrationPhase.IDLE
        self._start_time: float | None = None
        self._timeout_task: asyncio.Task | None = None
        self._on_progress: Callable | None = None
        self._on_done: Callable | None = None
        self._restore_limit: int = 80

    @property
    def phase(self) -> CalibrationPhase:
        return self._phase

    @property
    def is_active(self) -> bool:
        return self._phase not in (CalibrationPhase.IDLE, CalibrationPhase.COMPLETE, CalibrationPhase.TIMED_OUT)

    @property
    def restore_limit(self) -> int:
        return self._restore_limit

    def on_progress(self, callback: Callable) -> None:
        self._on_progress = callback

    def on_done(self, callback: Callable) -> None:
        self._on_done = callback

    async def start(self, restore_limit: int, drain_threshold: int = CALIBRATION_DRAIN_THRESHOLD) -> bool:
        if self.is_active:
            return False

        self._restore_limit = restore_limit
        self._drain_threshold = drain_threshold
        self._charge.set_limit(100)
        self._phase = CalibrationPhase.UNPLUG_AND_DRAIN
        self._start_time = asyncio.get_event_loop().time()
        self._timeout_task = asyncio.create_task(self._timeout_watchdog())

        if self._on_progress:
            self._on_progress("unplug_and_drain", None)

        snap = self._battery.snapshot()
        await self._evaluate(snap)
        return True

    def cancel(self) -> None:
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            self._timeout_task = None
        self._charge.set_limit(self._restore_limit)
        self._phase = CalibrationPhase.IDLE

    async def handle_battery_update(self, snap: BatterySnapshot) -> None:
        if self.is_active:
            await self._evaluate(snap)

    async def _evaluate(self, snap: BatterySnapshot) -> None:
        cap = snap.capacity
        ac = snap.ac_connected

        if self._phase == CalibrationPhase.UNPLUG_AND_DRAIN:
            if cap is not None and cap <= self._drain_threshold and not ac:
                self._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
                if self._on_progress:
                    self._on_progress("plug_in_and_charge", cap)
                await self._evaluate(snap)
            elif cap is not None and not ac:
                if self._on_progress:
                    self._on_progress("draining", cap)

        elif self._phase == CalibrationPhase.PLUG_IN_AND_CHARGE:
            if ac and cap is not None and cap >= 100:
                self._charge.set_limit(self._restore_limit)
                self._phase = CalibrationPhase.COMPLETE
                if self._timeout_task and not self._timeout_task.done():
                    self._timeout_task.cancel()
                if self._on_done:
                    self._on_done("complete", None)
            elif self._on_progress:
                self._on_progress("charging", cap)

    async def _timeout_watchdog(self) -> None:
        try:
            await asyncio.sleep(CALIBRATION_TIMEOUT_HOURS * 3600)
            self._phase = CalibrationPhase.TIMED_OUT
            self._charge.set_limit(self._restore_limit)
            if self._on_done:
                self._on_done("timed_out", None)
        except asyncio.CancelledError:
            pass
