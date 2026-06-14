import logging

from battery_calibrator._constants import CHARGE_RATE_SYSFS

logger = logging.getLogger("BatteryCalibrator.RateControl")


class ChargeRateControl:
    MIN_RATE = 0
    MAX_RATE = 3000000

    def __init__(self, sysfs_path: str | None = CHARGE_RATE_SYSFS):
        self._path = sysfs_path

    @property
    def available(self) -> bool:
        return self._path is not None

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
        microamps = max(self.MIN_RATE, min(self.MAX_RATE, microamps))
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
