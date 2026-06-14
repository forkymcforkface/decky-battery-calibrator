import time as _time

from battery_calibrator.battery import BatterySnapshot


class ThermalMonitor:
    """Heat protection: pauses charging when battery exceeds threshold.
    
    Design notes:
    - Threshold: 40°C (industry standard for Li-ion longevity)
    - Hysteresis: Resume at 38°C (2°C deadband prevents thrashing)
    - Cooldown: 5min after resume (prevents rapid on/off cycles)
    - Pause target: min(capacity, 30%) ensures EC stops charging
    
    TODO(v1.1): Add configurable hysteresis in settings UI
    TODO(v1.2): Support different thresholds per profile
    """
    
    def __init__(self, charge_control, settings, min_resume_interval: float = 300.0,
                 pause_limit: int = 30):
        self._charge = charge_control
        self._settings = settings
        self._throttled = False
        self._restore_limit: int | None = None
        self._last_resume_time: float | None = None
        self._min_resume_interval = min_resume_interval  # 5 minutes
        self._pause_limit = pause_limit

    @property
    def throttled(self) -> bool:
        return self._throttled

    @property
    def restore_limit(self) -> int | None:
        return self._restore_limit

    def handle_temperature(self, snap: BatterySnapshot) -> None:
        temp = snap.temp_celsius
        if temp is None:
            return
        if not self._settings.get("heat_protection_enabled", False):
            if self._throttled:
                self._unpause()
            return

        threshold = self._settings.get("heat_threshold_celsius", 40)
        cap = snap.capacity

        if self._throttled:
            # Resume when temp drops 2°C below threshold (hysteresis)
            if temp <= threshold - 2:
                self._unpause()
            return

        if temp > threshold and cap is not None:
            # Respect cooldown: don't re-pause within 5 minutes of last resume
            if (self._last_resume_time is not None
                    and _time.monotonic() - self._last_resume_time < self._min_resume_interval):
                return
            self._restore_limit = self._charge.get_limit()
            # Pause to min(current_capacity, 30%) to force EC to stop
            pause_target = cap if cap <= self._pause_limit else self._pause_limit
            self._charge.set_limit(pause_target)
            self._throttled = True

    def _unpause(self) -> None:
        if self._restore_limit is not None:
            self._charge.set_limit(self._restore_limit)
        self._throttled = False
        self._restore_limit = None
        self._last_resume_time = _time.monotonic()

    def reset(self) -> None:
        self._unpause()
