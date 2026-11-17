import logging
import os

from battery_calibrator._constants import ARMDECK_BATTERY, ARMDECK_CHARGER, CHARGE_RATE_SYSFS

logger = logging.getLogger("BatteryCalibrator.RateControl")


class ChargeRateControl:
    MIN_RATE = 0
    MAX_RATE = 3000000

    def __init__(self, sysfs_path: str | None = CHARGE_RATE_SYSFS):
        self._path = sysfs_path
        self._armdeck = ARMDECK_BATTERY is not None and sysfs_path == CHARGE_RATE_SYSFS

    @property
    def max_rate(self) -> int:
        if self._armdeck:
            try:
                return int((ARMDECK_CHARGER / "constant_charge_current_max").read_text())
            except (OSError, ValueError):
                return 0
        return self.MAX_RATE

    @property
    def available(self) -> bool:
        return self._path is not None and (
            not self._armdeck or self.max_rate > 0 and os.access(self._path, os.W_OK)
        )

    def get_rate(self) -> int | None:
        if not self._path:
            return None
        try:
            with open(self._path) as f:
                return int(f.read().strip())
        except (FileNotFoundError, PermissionError, ValueError, OSError):
            return None

    def set_rate(self, microamps: int) -> bool:
        if not self._path:
            return False
        if self._armdeck and (not self.available or microamps <= 0):
            return False
        microamps = max(self.MIN_RATE, min(self.max_rate, microamps))
        try:
            with open(self._path, "w") as f:
                f.write(str(microamps))
            return True
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Failed to set charge rate: {e}")
            return False

    def get_rate_amps(self) -> float | None:
        rate = self.get_rate()
        if rate is not None:
            return round(rate / 1_000_000, 2)
        return None

    def set_rate_amps(self, amps: float) -> bool:
        return self.set_rate(int(amps * 1_000_000))
