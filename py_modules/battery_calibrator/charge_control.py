import abc
import subprocess

from battery_calibrator._constants import CHARGE_LIMIT_SYSFS, DBUS_IFACE, DBUS_PATH, DBUS_SERVICE
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


def create_charge_control() -> ChargeControl:
    try:
        ctrl = DBusChargeControl()
        test = ctrl.get_limit()
        if test is not None:
            return ctrl
    except Exception:
        pass
    return SysfsChargeControl()
