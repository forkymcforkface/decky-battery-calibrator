import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "py_modules"))

import asyncio

from battery_calibrator import (
    BatteryReader,
    CalibrationEngine,
    CalibrationScheduler,
    ChargeRateControl,
    HistoryDatabase,
    PresetManager,
    SettingsManager,
    ThermalMonitor,
    create_charge_control,
)

import decky

READLINE_TIMEOUT = 30
EVENT_DEBOUNCE_S = 1
HISTORY_RETENTION_DAYS = 90
UDEV_RESTART_DELAY = 2
UDEV_MAX_RETRIES = 5
POLL_INTERVAL_S = 5


class Plugin:
    async def _main(self):
        self.loop = asyncio.get_event_loop()

        self.settings = SettingsManager(decky.DECKY_PLUGIN_SETTINGS_DIR)
        self.battery = BatteryReader()
        self.charge = create_charge_control()
        self.history = HistoryDatabase(decky.DECKY_PLUGIN_RUNTIME_DIR)

        self.calibration = CalibrationEngine(self.charge, self.battery)
        self.calibration.on_progress(self._on_cal_progress)
        self.calibration.on_done(self._on_cal_done)

        self.scheduler = CalibrationScheduler(self.settings)
        self.scheduler.on_calibration_due(self._on_scheduler_due)

        self.presets = PresetManager(self.settings)
        self.rate_ctrl = ChargeRateControl()
        self.thermal = ThermalMonitor(self.charge, self.settings)
        self._quiet_rate = 500000

        self._apply_sailing_mode()
        self._apply_quiet_charging()

        self._recover_calibration()

        self._last_battery: dict | None = None
        self._last_recorded: tuple | None = None
        self._last_event_time: float = 0
        self._top_up_restore: int | None = None
        self._monitor_task = asyncio.create_task(self._battery_monitor())

        self.history.prune_snapshots(HISTORY_RETENTION_DAYS)
        await self.scheduler.start()
        decky.logger.info("Battery Calibrator loaded")

    async def _unload(self):
        self.calibration.cancel()
        self._top_up_restore = None
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        await self.scheduler.stop()
        self.history.close()
        decky.logger.info("Battery Calibrator unloaded")

    async def _battery_monitor(self) -> None:
        proc: asyncio.subprocess.Process | None = None
        udev_retries = 0
        using_polling = False

        async def process_snapshot(snap) -> None:
            await self.calibration.handle_battery_update(snap)
            if self._top_up_restore is not None and snap.capacity is not None and snap.capacity >= 100:
                self.charge.set_limit(self._top_up_restore)
                self._top_up_restore = None
                self._emit("top_up_done")
            self.thermal.handle_temperature(snap)
            if not self.calibration.is_active and self._top_up_restore is None:
                self._apply_smart_charge(snap)
            self._record_snapshot(snap)
            d = self._snap_to_dict(snap)
            if d != self._last_battery:
                self._last_battery = d
                self._emit("battery_update", d)

        async def poll_loop():
            nonlocal using_polling
            using_polling = True
            decky.logger.info("falling back to sysfs polling (5s interval)")
            while True:
                await asyncio.sleep(POLL_INTERVAL_S)
                snap = self.battery.snapshot()
                d = self._snap_to_dict(snap)
                now = asyncio.get_event_loop().time()
                if now - self._last_event_time >= EVENT_DEBOUNCE_S:
                    self._last_event_time = now
                    await process_snapshot(snap)
                elif d != self._last_battery:
                    self._last_battery = d
                    self._emit("battery_update", d)

        while True:
            if udev_retries >= UDEV_MAX_RETRIES:
                await poll_loop()
                return

            try:
                proc = await asyncio.create_subprocess_exec(
                    "udevadm", "monitor", "--kernel", "--subsystem-match=power_supply",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            except FileNotFoundError:
                decky.logger.warning("udevadm not found, falling back to polling")
                await poll_loop()
                return
            except Exception:
                decky.logger.exception("Failed to start udevadm monitor")
                udev_retries += 1
                delay = UDEV_RESTART_DELAY * (2 ** (udev_retries - 1))
                await asyncio.sleep(delay)
                continue

            try:
                assert proc.stdout is not None
                while True:
                    try:
                        line = await asyncio.wait_for(
                            proc.stdout.readline(), timeout=READLINE_TIMEOUT
                        )
                    except TimeoutError:
                        continue

                    if not line:
                        decky.logger.warning("udevadm monitor exited, restarting")
                        udev_retries += 1
                        break

                    if b"BAT1" in line and b"change" in line:
                        now = asyncio.get_event_loop().time()
                        if now - self._last_event_time < EVENT_DEBOUNCE_S:
                            continue
                        self._last_event_time = now
                        snap = self.battery.snapshot()
                        await process_snapshot(snap)
            except asyncio.CancelledError:
                raise
            except Exception:
                decky.logger.exception("battery_monitor error, restarting udevadm")
                udev_retries += 1
            finally:
                if proc:
                    try:
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=2)
                    except (TimeoutError, ProcessLookupError):
                        try:
                            proc.kill()
                            await proc.wait()
                        except (ProcessLookupError, Exception):
                            pass

            udev_retries = min(udev_retries, UDEV_MAX_RETRIES)
            delay = UDEV_RESTART_DELAY * (2 ** (udev_retries - 1))
            await asyncio.sleep(delay)

    def _record_snapshot(self, snap) -> None:
        key = (snap.capacity, snap.status, snap.ac_connected, snap.power_watts, snap.temp_celsius)
        if key != self._last_recorded:
            self._last_recorded = key
            self.history.record_snapshot(
                capacity=snap.capacity,
                status=snap.status,
                health_pct=snap.health_pct,
                cycle_count=snap.cycle_count,
                power_watts=snap.power_watts,
                ac_connected=snap.ac_connected,
                temp_celsius=snap.temp_celsius,
            )

    def _snap_to_dict(self, snap) -> dict:
        limit = self.charge.get_limit()
        return {
            "capacity": snap.capacity,
            "status": snap.status,
            "ac_connected": snap.ac_connected,
            "charge_limit": limit,
            "health": snap.health_pct,
            "cycle_count": snap.cycle_count,
            "power_watts": round(snap.power_watts, 1) if snap.power_watts is not None else None,
            "voltage": snap.voltage_now,
            "current": snap.current_now,
            "charge_full": snap.charge_full,
            "charge_full_design": snap.charge_full_design,
            "charge_rate_available": self.rate_ctrl.available,
            "charge_rate_amps": self.rate_ctrl.get_rate_amps(),
            "temp_celsius": snap.temp_celsius,
            "thermal_throttled": self.thermal.throttled,
            "pd_current_ma": snap.pd_current_ma,
            "pd_voltage_mv": snap.pd_voltage_mv,
            "pd_watts": snap.pd_watts,
        }

    async def _uninstall(self):
        pass

    async def _migration(self):
        decky.migrate_settings(
            os.path.join(decky.DECKY_HOME, "settings", "battery_calibrator.json"),
            os.path.join(decky.DECKY_USER_HOME, ".config", "battery-calibrator"),
        )

    async def get_battery_status(self) -> dict:
        return self._snap_to_dict(self.battery.snapshot())

    async def set_charge_limit(self, percent: int) -> bool:
        if not isinstance(percent, int) or percent < 0 or percent > 100:
            decky.logger.warning(f"Invalid charge limit: {percent}")
            return False
        try:
            ok = self.charge.set_limit(percent)
            if ok:
                self.settings.set("charge_limit", percent)
            return ok
        except Exception as e:
            decky.logger.error(f"set_charge_limit failed: {e}")
            return False

    async def get_next_calibration(self) -> dict:
        return {
            "next_calibration": self.scheduler.next_due(),
            "interval_days": self.settings.get("calibration_interval_days", 14),
            "last_calibration": self.settings.get("last_calibration"),
        }

    def _recover_calibration(self) -> None:
        if not self.settings.get("calibration_in_progress", False):
            return
        saved_limit = self.settings.get("charge_limit", 80)
        live_limit = self.charge.get_limit()
        if live_limit is not None and live_limit == 100 and saved_limit < 100:
            self.charge.set_limit(saved_limit)
            decky.logger.warning(
                f"Recovered from crashed calibration: restored limit from 100% to {saved_limit}%"
            )
        self.settings.set("calibration_in_progress", False)
        self.settings.set("calibration_restore_limit", 80)

    async def start_calibration(self) -> bool:
        if self.calibration.is_active:
            return False
        limit = self.settings.get("charge_limit", 80)
        threshold = self.settings.get("calibration_drain_threshold", 30)
        self.settings.set("calibration_restore_limit", limit)
        self.settings.set("calibration_in_progress", True)
        ok = await self.calibration.start(restore_limit=limit, drain_threshold=threshold)
        if ok:
            ts = self.history.log_calibration_start()
            self._current_cal_start = ts
        else:
            self.settings.set("calibration_in_progress", False)
        return ok

    async def snooze_calibration(self, days: int = 1) -> None:
        if not isinstance(days, int) or days < 1 or days > 365:
            days = 1
        self.scheduler.snooze(days)

    async def cancel_calibration(self) -> None:
        self.calibration.cancel()
        self.settings.set("calibration_in_progress", False)
        if self._top_up_restore is not None:
            self.charge.set_limit(self._top_up_restore)
            self._top_up_restore = None

    async def get_calibration_state(self) -> dict:
        return {
            "phase": self.calibration.phase.value,
            "active": self.calibration.is_active,
        }

    async def get_history(self) -> dict:
        return {
            "snapshots": self.history.get_recent_snapshots(50),
            "calibrations": self.history.get_calibration_history(10),
        }

    async def get_device_info(self) -> dict:
        return {
            "manufacturer": self.battery.manufacturer(),
            "model": self.battery.model_name(),
            "serial": self.battery.serial_number(),
            "technology": self.battery.technology(),
        }

    async def get_presets(self) -> dict:
        return self.presets.get_all()

    async def apply_preset(self, name: str) -> bool:
        limit = self.presets.get_limit(name)
        if limit is None:
            return False
        return await self.set_charge_limit(limit)

    async def add_preset(self, name: str, limit: int) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        if not isinstance(limit, int) or limit < 20 or limit > 100:
            return
        self.presets.add(name.strip(), limit)

    async def remove_preset(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        self.presets.remove(name.strip())

    async def pause_charging(self) -> bool:
        snap = self.battery.snapshot()
        if snap.capacity is None:
            return False
        return await self.set_charge_limit(snap.capacity)

    async def top_up(self) -> bool:
        restore = self.charge.get_limit()
        self.charge.set_limit(100)
        self._top_up_restore = restore
        return True

    async def get_charge_rate(self) -> dict:
        return {
            "available": self.rate_ctrl.available,
            "microamps": self.rate_ctrl.get_rate(),
            "amps": self.rate_ctrl.get_rate_amps(),
        }

    async def set_charge_rate(self, microamps: int) -> bool:
        if not isinstance(microamps, int) or microamps < 0 or microamps > 3000000:
            decky.logger.warning(f"Invalid charge rate: {microamps}")
            return False
        return self.rate_ctrl.set_rate(microamps)

    async def get_sailing_mode(self) -> dict:
        enabled = self.settings.get("sailing_mode_enabled", False)
        return {
            "enabled": enabled,
            "low": self.settings.get("sailing_range_low", 70),
            "high": self.settings.get("sailing_range_high", 80),
        }

    async def get_settings(self) -> dict:
        return self.settings.get_all()

    def _apply_sailing_mode(self) -> None:
        if self.settings.get("sailing_mode_enabled", False):
            low = self.settings.get("sailing_range_low", 70)
            self.charge.set_limit(low)
            self.settings.set("charge_limit", low)
            self.settings.set("calibration_interval_days", 0)

    def _apply_quiet_charging(self) -> None:
        if self.settings.get("quiet_charging_enabled", False):
            self.rate_ctrl.set_rate(self._quiet_rate)

    async def set_quiet_charging(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            decky.logger.warning(f"Invalid quiet_charging value: {enabled}")
            return
        self.settings.set("quiet_charging_enabled", enabled)
        if enabled:
            saved = self.rate_ctrl.get_rate()
            if saved is not None:
                self.settings.set("charge_rate_microamps", saved)
            self.rate_ctrl.set_rate(self._quiet_rate)
        else:
            saved = self.settings.get("charge_rate_microamps")
            if saved is not None:
                self.rate_ctrl.set_rate(saved)

    def _apply_smart_charge(self, snap) -> None:
        if not self.settings.get("smart_charge_enabled", False):
            return
        cap = snap.capacity
        if cap is None:
            return
        smart_min = self.settings.get("smart_charge_min", 30)
        smart_max = self.settings.get("smart_charge_max", 80)
        current_limit = self.charge.get_limit()

        if cap <= smart_min and current_limit != smart_max:
            self.charge.set_limit(smart_max)
            self.settings.set("charge_limit", smart_max)
        elif cap >= smart_max and current_limit != smart_min:
            self.charge.set_limit(smart_min)
            self.settings.set("charge_limit", smart_min)

    async def update_settings(self, updates: dict) -> None:
        if not isinstance(updates, dict):
            decky.logger.warning(f"update_settings received non-dict: {updates}")
            return
        for special_key in ("sailing_mode_enabled", "smart_charge_enabled", "quiet_charging_enabled"):
            if special_key in updates:
                val = updates[special_key]
                if not isinstance(val, bool):
                    decky.logger.warning(f"Invalid value for {special_key}: {val}")
                    del updates[special_key]
                    continue
                self.settings.set(special_key, val)
                if special_key == "sailing_mode_enabled":
                    self._apply_sailing_mode()
                elif special_key == "quiet_charging_enabled":
                    await self.set_quiet_charging(val)
                del updates[special_key]
        if updates:
            self.settings.set_many(updates)

    async def save_profile(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        profiles = self.settings.get("profiles", {})
        profile = {
            "charge_limit": self.settings.get("charge_limit", 80),
            "extended_range_enabled": self.settings.get("extended_range_enabled", False),
            "smart_charge_enabled": self.settings.get("smart_charge_enabled", False),
            "smart_charge_min": self.settings.get("smart_charge_min", 30),
            "smart_charge_max": self.settings.get("smart_charge_max", 80),
            "heat_protection_enabled": self.settings.get("heat_protection_enabled", False),
            "heat_threshold_celsius": self.settings.get("heat_threshold_celsius", 40),
            "charge_rate_microamps": self.rate_ctrl.get_rate(),
            "calibration_interval_days": self.settings.get("calibration_interval_days", 14),
            "quiet_charging_enabled": self.settings.get("quiet_charging_enabled", False),
        }
        profiles[name] = profile
        self.settings.set("profiles", profiles)

    async def load_profile(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            return False
        profiles = self.settings.get("profiles", {})
        profile = profiles.get(name)
        if profile is None:
            return False
        for key, value in profile.items():
            if key == "charge_rate_microamps":
                self.rate_ctrl.set_rate(value)
            elif key == "quiet_charging_enabled":
                self.settings.set(key, value)
                if value:
                    self.rate_ctrl.set_rate(self._quiet_rate)
            else:
                self.settings.set(key, value)
        limit = profile.get("charge_limit", 80)
        self.charge.set_limit(limit)
        return True

    async def delete_profile(self, name: str) -> None:
        profiles = self.settings.get("profiles", {})
        profiles.pop(name, None)
        self.settings.set("profiles", profiles)

    async def get_profiles(self) -> dict:
        return self.settings.get("profiles", {})

    def _emit(self, event: str, *args: object) -> None:
        try:
            asyncio.create_task(decky.emit(event, *args))
        except Exception as e:
            decky.logger.debug(f"emit({event}) failed: {e}")

    def _on_cal_progress(self, stage: str, cap: int | None) -> None:
        self._emit("calibration_progress", stage, cap)

    def _on_cal_done(self, result: str, _: object) -> None:
        self.settings.set("calibration_in_progress", False)
        self._emit("calibration_done", result)
        if hasattr(self, "_current_cal_start") and self._current_cal_start:
            self.history.log_calibration_end(self._current_cal_start, result)
            self._current_cal_start = None

    def _on_scheduler_due(self) -> None:
        self._emit("calibration_due")
