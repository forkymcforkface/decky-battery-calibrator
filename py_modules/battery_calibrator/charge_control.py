import abc
import os
import subprocess
from pathlib import Path

from battery_calibrator._constants import (
    ARMDECK_BATTERY, ARMDECK_CHARGER, CHARGE_LIMIT_SYSFS, DBUS_IFACE, DBUS_PATH, DBUS_SERVICE,
)
from battery_calibrator.battery import BatteryReader, BatterySnapshot
from battery_calibrator._exceptions import ChargeControlError


class ChargeControl(abc.ABC):
    MIN_LIMIT = 20
    MAX_LIMIT = 100

    @abc.abstractmethod
    def get_limit(self) -> int | None:
        pass

    @abc.abstractmethod
    def set_limit(self, percent: int) -> bool:
        pass


class DBusChargeControl(ChargeControl):
    def get_limit(self) -> int | None:
        raw = self._read_sysfs()
        if raw is not None:
            return raw
        return None

    def set_limit(self, percent: int) -> bool:
        percent = max(self.MIN_LIMIT, min(self.MAX_LIMIT, percent))
        try:
            subprocess.run(
                ["busctl", "--system", "call",
                 DBUS_SERVICE, DBUS_PATH, DBUS_IFACE,
                 "SetMaxChargeLevel", "i", str(percent)],
                capture_output=True, check=True, timeout=5)
            return True
        except subprocess.CalledProcessError as e:
            raise ChargeControlError("DBus SetMaxChargeLevel", str(e))
        except FileNotFoundError:
            raise ChargeControlError("DBus SetMaxChargeLevel", "busctl not found")

    def _read_sysfs(self) -> int | None:
        try:
            with open(CHARGE_LIMIT_SYSFS) as f:
                return int(f.read().strip())
        except (FileNotFoundError, PermissionError, ValueError, TypeError):
            return None


class SysfsChargeControl(ChargeControl):
    def get_limit(self) -> int | None:
        try:
            with open(CHARGE_LIMIT_SYSFS) as f:
                return int(f.read().strip())
        except (FileNotFoundError, PermissionError, ValueError, TypeError):
            return None

    def set_limit(self, percent: int) -> bool:
        percent = max(self.MIN_LIMIT, min(self.MAX_LIMIT, percent))
        try:
            with open(CHARGE_LIMIT_SYSFS, "w") as f:
                f.write(str(percent))
            return True
        except (FileNotFoundError, PermissionError) as e:
            raise ChargeControlError("Sysfs write", str(e))


class PM8150BChargeControl(ChargeControl):
    def __init__(self, battery: BatteryReader, behaviour: Path):
        self._battery = battery
        self._behaviour = behaviour
        self._limit = self.MAX_LIMIT
        self._holding = False

    def get_limit(self) -> int | None:
        return self._limit if os.access(self._behaviour, os.W_OK) else None

    def set_limit(self, percent: int) -> bool:
        if self.get_limit() is None:
            raise ChargeControlError("PM8150B charge limit", "charge behaviour is not writable")
        previous = self._limit
        self._limit = max(self.MIN_LIMIT, min(self.MAX_LIMIT, percent))
        try:
            self.refresh(self._battery.snapshot())
        except ChargeControlError:
            self._limit = previous
            raise
        return True

    def refresh(self, snapshot: BatterySnapshot) -> None:
        if not os.access(self._behaviour, os.W_OK):
            return
        capacity = snapshot.capacity
        if not snapshot.ac_connected or capacity is None or self._limit == self.MAX_LIMIT:
            self.release()
            return

        # Leave a two-point gap before topping up again.
        if self._holding and capacity <= self._limit - 2:
            self.release()
        elif not self._holding and capacity >= self._limit:
            self._change_mode("auto", "inhibit-charge")

    def _change_mode(self, previous: str, desired: str) -> None:
        try:
            current = self._behaviour.read_text().strip().split()
            if f"[{previous}]" in current:
                self._behaviour.write_text(desired + "\n")
                self._holding = desired == "inhibit-charge"
        except OSError as error:
            raise ChargeControlError("PM8150B charge behaviour", str(error)) from error

    def release(self) -> None:
        if self._holding:
            self._change_mode("inhibit-charge", "auto")
            self._holding = False


def create_charge_control(battery: BatteryReader | None = None) -> ChargeControl:
    if ARMDECK_BATTERY is not None:
        return PM8150BChargeControl(battery or BatteryReader(), ARMDECK_CHARGER / "charge_behaviour")
    try:
        ctrl = DBusChargeControl()
        test = ctrl.get_limit()
        if test is not None:
            return ctrl
    except Exception:
        pass
    return SysfsChargeControl()
