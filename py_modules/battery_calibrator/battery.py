import os
from dataclasses import dataclass

from battery_calibrator._constants import (
    AC_SYSFS,
    BATTERY_SYSFS,
    PD_CURRENT_SYSFS,
    PD_VOLTAGE_SYSFS,
    BatteryStatus,
)


@dataclass
class BatterySnapshot:
    capacity: int | None
    status: str
    ac_connected: bool
    health_pct: float | None
    cycle_count: int | None
    power_watts: float | None
    voltage_now: float | None
    current_now: float | None
    charge_full: int | None
    charge_full_design: int | None
    charge_now: int | None
    temp_celsius: float | None
    pd_current_ma: int | None
    pd_voltage_mv: int | None
    pd_watts: float | None


class BatteryReader:
    def __init__(self):
        self._base = BATTERY_SYSFS
        self._ac = AC_SYSFS
        self._pd_current_path = PD_CURRENT_SYSFS
        self._pd_voltage_path = PD_VOLTAGE_SYSFS

    def _read(self, filename: str) -> str | None:
        path = os.path.join(self._base, filename)
        try:
            with open(path) as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def _read_int(self, filename: str) -> int | None:
        val = self._read(filename)
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _read_path_int(self, path: str | None) -> int | None:
        if not path:
            return None
        try:
            with open(path) as f:
                return int(f.read().strip())
        except (FileNotFoundError, PermissionError, ValueError, OSError):
            return None

    def snapshot(self) -> BatterySnapshot:
        status = self._read("status") or BatteryStatus.UNKNOWN.value
        capacity = self._read_int("capacity")
        charge_now = self._read_int("charge_now")
        charge_full = self._read_int("charge_full")
        charge_full_design = self._read_int("charge_full_design")
        cycle_count = self._read_int("cycle_count")
        current_now = self._read_int("current_now")
        voltage_now = self._read_int("voltage_now")
        temp_raw = self._read_int("temp")
        pd_voltage_mv = self._read_path_int(self._pd_voltage_path)
        pd_current_ma = self._read_path_int(self._pd_current_path)

        health_pct: float | None = None
        if charge_full and charge_full_design and charge_full_design > 0:
            health_pct = round(charge_full / charge_full_design * 100, 1)

        power_watts: float | None = None
        if current_now and voltage_now:
            power_watts = abs(current_now * voltage_now) / 1e12
        pd_watts: float | None = None
        if pd_voltage_mv and pd_current_ma:
            pd_watts = round(pd_voltage_mv * pd_current_ma / 1_000_000, 1)

        ac_raw = self._read(self._ac)
        ac_connected = ac_raw == "1"

        temp_celsius: float | None = None
        if temp_raw is not None:
            temp_celsius = round(temp_raw / 10, 1)

        return BatterySnapshot(
            capacity=capacity,
            status=status,
            ac_connected=ac_connected,
            health_pct=health_pct,
            cycle_count=cycle_count,
            power_watts=power_watts,
            voltage_now=voltage_now,
            current_now=current_now,
            charge_full=charge_full,
            charge_full_design=charge_full_design,
            charge_now=charge_now,
            temp_celsius=temp_celsius,
            pd_current_ma=pd_current_ma,
            pd_voltage_mv=pd_voltage_mv,
            pd_watts=pd_watts,
        )

    def manufacturer(self) -> str | None:
        return self._read("manufacturer")

    def model_name(self) -> str | None:
        return self._read("model_name")

    def serial_number(self) -> str | None:
        return self._read("serial_number")

    def technology(self) -> str | None:
        return self._read("technology")
