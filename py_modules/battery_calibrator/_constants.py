import enum
import os
from pathlib import Path

BATTERY_SYSFS = "/sys/class/power_supply/BAT1"
AC_SYSFS = "/sys/class/power_supply/ACAD/online"

HWMON_BASE = "/sys/devices/pci0000:00/0000:00:14.3/PNP0C09:00/VLV0100:00/steamdeck-hwmon/hwmon"
CHARGE_LIMIT_SYSFS = None
CHARGE_RATE_SYSFS = None
PD_CURRENT_SYSFS = None
PD_VOLTAGE_SYSFS = None

try:
    for entry in os.listdir(HWMON_BASE):
        path = os.path.join(HWMON_BASE, entry, "name")
        if os.path.isfile(path):
            with open(path) as f:
                if f.read().strip() == "steamdeck_hwmon":
                    hwmon_dir = os.path.join(HWMON_BASE, entry)
                    CHARGE_LIMIT_SYSFS = os.path.join(hwmon_dir, "max_battery_charge_level")
                    CHARGE_RATE_SYSFS = os.path.join(hwmon_dir, "max_battery_charge_rate")
                    PD_CURRENT_SYSFS = os.path.join(hwmon_dir, "curr1_input")
                    PD_VOLTAGE_SYSFS = os.path.join(hwmon_dir, "in0_input")
                    break
except (FileNotFoundError, PermissionError, OSError):
    pass

POWER_SUPPLIES = Path("/sys/class/power_supply")
ARMDECK_BATTERY = next(POWER_SUPPLIES.glob("bq27411-*"), None)
ARMDECK_CHARGER = POWER_SUPPLIES / "pm8150b-charger"
ARMDECK_POWER_ROLES = Path("/sys/class/typec")
ARMDECK_AC_SUPPLY = None

if ARMDECK_BATTERY is not None:
    BATTERY_SYSFS = str(ARMDECK_BATTERY)
    ARMDECK_AC_SUPPLY = next(POWER_SUPPLIES.glob("tcpm-source-psy-*"), None)
    AC_SYSFS = str(ARMDECK_AC_SUPPLY / "online") if ARMDECK_AC_SUPPLY else None
    if ARMDECK_AC_SUPPLY:
        PD_CURRENT_SYSFS = str(ARMDECK_AC_SUPPLY / "current_now")
        PD_VOLTAGE_SYSFS = str(ARMDECK_AC_SUPPLY / "voltage_now")
    CHARGE_RATE_SYSFS = str(ARMDECK_CHARGER / "constant_charge_current")

DBUS_SERVICE = "com.steampowered.SteamOSManager1"
DBUS_PATH = "/com/steampowered/SteamOSManager1"
DBUS_IFACE = "com.steampowered.SteamOSManager1.RootManager"

CALIBRATION_TIMEOUT_HOURS = 48
CALIBRATION_DRAIN_THRESHOLD = 30
SETTINGS_FILENAME = "battery_calibrator.json"
HISTORY_FILENAME = "battery_history.db"


class CalibrationState(enum.Enum):
    IDLE = "idle"
    WAITING_DRAIN = "waiting_drain"
    WAITING_CHARGE = "waiting_charge"
    COMPLETE = "complete"
    TIMED_OUT = "timed_out"


class BatteryStatus(enum.Enum):
    CHARGING = "Charging"
    DISCHARGING = "Discharging"
    FULL = "Full"
    NOT_CHARGING = "Not charging"
    UNKNOWN = "Unknown"


DEFAULT_SETTINGS = {
    "charge_limit": 80,
    "calibration_interval_days": 14,
    "last_calibration": None,
    "calibration_drain_threshold": 30,
    "charge_limit_min": 50,
    "charge_limit_max": 100,
    "notifications_enabled": True,
    "heat_protection_enabled": False,
    "heat_threshold_celsius": 40,
    "sailing_mode_enabled": False,
    "sailing_range_low": 70,
    "sailing_range_high": 80,
    "smart_charge_enabled": False,
    "smart_charge_min": 30,
    "smart_charge_max": 80,
}
