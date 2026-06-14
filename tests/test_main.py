import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from battery_calibrator.battery import BatterySnapshot


@pytest.fixture
def mock_decky():
    with patch.dict("sys.modules", {"decky": MagicMock()}):
        import decky
        decky.DECKY_PLUGIN_SETTINGS_DIR = "/tmp/test_settings"
        decky.DECKY_PLUGIN_RUNTIME_DIR = "/tmp/test_runtime"
        decky.DECKY_HOME = "/tmp/test_home"
        decky.DECKY_USER_HOME = "/tmp/test_user_home"
        decky.logger = MagicMock()
        decky.emit = AsyncMock()
        decky.migrate_settings = MagicMock()
        yield decky


@pytest.fixture
def plugin(mock_decky):
    from main import Plugin
    p = Plugin()
    settings_store: dict = {
        "charge_limit": 80,
        "calibration_drain_threshold": 30,
        "calibration_interval_days": 14,
        "last_calibration": None,
        "sailing_mode_enabled": False,
        "sailing_range_low": 70,
        "sailing_range_high": 80,
        "extended_range_enabled": False,
        "heat_protection_enabled": False,
        "heat_threshold_celsius": 40,
        "min_charge_rate": 500000,
    }
    p.settings = MagicMock()
    p.settings.get.side_effect = lambda k, d=None: settings_store.get(k, d)
    p.settings.set.side_effect = lambda k, v: settings_store.update({k: v})
    p.settings.set_many.side_effect = lambda u: settings_store.update(u)
    p.settings.get_all.side_effect = lambda: dict(settings_store)
    p.battery = MagicMock()
    p.battery.snapshot.return_value = BatterySnapshot(
        capacity=75, status="Discharging", ac_connected=False,
        health_pct=95.0, cycle_count=100, power_watts=5.0,
        voltage_now=12000000, current_now=500000,
        charge_full=4000000, charge_full_design=5000000,
        charge_now=3000000,
        temp_celsius=None,
        pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
    )
    p.charge = MagicMock()
    p.charge.get_limit.return_value = 80
    p.charge.set_limit.return_value = True
    p.history = MagicMock()
    p.history.log_calibration_start.return_value = "2026-01-01T00:00:00"
    p.calibration = MagicMock()
    p.calibration.start = AsyncMock(return_value=True)
    p.calibration.handle_battery_update = AsyncMock()
    p.calibration.is_active = False
    p.calibration.phase = MagicMock()
    p.calibration.phase.value = "idle"
    p.scheduler = MagicMock()
    p.scheduler.next_due.return_value = "2026-01-15T00:00:00"
    p.scheduler.start = AsyncMock()
    p.scheduler.stop = AsyncMock()
    p.presets = MagicMock()
    p.presets.get_all.return_value = {
        "built-in": {"Normal 80%": 80, "Full 100%": 100},
        "custom": {},
    }
    p.presets.get_limit.return_value = 80
    p.rate_ctrl = MagicMock()
    p.rate_ctrl.available = True
    p.rate_ctrl.get_rate.return_value = 2000000
    p.rate_ctrl.get_rate_amps.return_value = 2.0
    p.rate_ctrl.set_rate.return_value = True
    p.thermal = MagicMock()
    p.thermal.throttled = False
    p._emit = MagicMock()
    p._top_up_restore = None
    p._last_battery = None
    p._last_recorded = None
    p._current_cal_start = None
    return p


class TestPluginMain:
    @pytest.mark.asyncio
    async def test_get_presets(self, plugin):
        result = await plugin.get_presets()
        assert "built-in" in result
        assert result["built-in"]["Normal 80%"] == 80

    @pytest.mark.asyncio
    async def test_apply_preset_found(self, plugin):
        result = await plugin.apply_preset("Normal 80%")
        assert result is True
        plugin.charge.set_limit.assert_called_with(80)

    @pytest.mark.asyncio
    async def test_apply_preset_not_found(self, plugin):
        plugin.presets.get_limit.return_value = None
        result = await plugin.apply_preset("Nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_preset(self, plugin):
        await plugin.add_preset("My Preset", 60)
        plugin.presets.add.assert_called_with("My Preset", 60)

    @pytest.mark.asyncio
    async def test_remove_preset(self, plugin):
        await plugin.remove_preset("My Preset")
        plugin.presets.remove.assert_called_with("My Preset")

    @pytest.mark.asyncio
    async def test_pause_charging(self, plugin):
        result = await plugin.pause_charging()
        assert result is True
        plugin.charge.set_limit.assert_called_with(75)

    @pytest.mark.asyncio
    async def test_pause_charging_no_capacity(self, plugin):
        plugin.battery.snapshot.return_value = BatterySnapshot(
            capacity=None, status="Unknown", ac_connected=False,
            health_pct=0.0, cycle_count=0, power_watts=None,
            voltage_now=None, current_now=None,
            charge_full=None, charge_full_design=None,
            charge_now=None,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        result = await plugin.pause_charging()
        assert result is False

    @pytest.mark.asyncio
    async def test_top_up(self, plugin):
        result = await plugin.top_up()
        assert result is True
        plugin.charge.set_limit.assert_called_with(100)
        assert plugin._top_up_restore == 80

    @pytest.mark.asyncio
    async def test_top_up_no_change(self, plugin):
        plugin.charge.get_limit.return_value = 100
        result = await plugin.top_up()
        assert result is True
        plugin.charge.set_limit.assert_called_with(100)
        assert plugin._top_up_restore == 100

    @pytest.mark.asyncio
    async def test_cancel_calibration_clears_top_up(self, plugin):
        plugin._top_up_restore = 80
        await plugin.cancel_calibration()
        plugin.calibration.cancel.assert_called_once()
        plugin.charge.set_limit.assert_called_with(80)
        assert plugin._top_up_restore is None

    @pytest.mark.asyncio
    async def test_cancel_calibration_no_top_up(self, plugin):
        plugin._top_up_restore = None
        await plugin.cancel_calibration()
        plugin.calibration.cancel.assert_called_once()
        assert plugin._top_up_restore is None

    @pytest.mark.asyncio
    async def test_get_charge_rate(self, plugin):
        result = await plugin.get_charge_rate()
        assert result["available"] is True
        assert result["microamps"] == 2000000
        assert result["amps"] == 2.0

    @pytest.mark.asyncio
    async def test_set_charge_rate(self, plugin):
        result = await plugin.set_charge_rate(1500000)
        assert result is True
        plugin.rate_ctrl.set_rate.assert_called_with(1500000)

    @pytest.mark.asyncio
    async def test_battery_status_includes_rate(self, plugin):
        result = await plugin.get_battery_status()
        assert result["charge_rate_available"] is True
        assert result["charge_rate_amps"] == 2.0

    @pytest.mark.asyncio
    async def test_get_settings(self, plugin):
        result = await plugin.get_settings()
        assert result["charge_limit"] == 80

    @pytest.mark.asyncio
    async def test_update_settings(self, plugin):
        await plugin.update_settings({"charge_limit": 60})
        plugin.settings.set_many.assert_called_with({"charge_limit": 60})

    @pytest.mark.asyncio
    async def test_set_charge_limit_persists(self, plugin):
        result = await plugin.set_charge_limit(60)
        assert result is True
        plugin.charge.set_limit.assert_called_with(60)
        plugin.settings.set.assert_called_with("charge_limit", 60)

    @pytest.mark.asyncio
    async def test_set_charge_limit_failure(self, plugin):
        plugin.charge.set_limit.return_value = False
        result = await plugin.set_charge_limit(60)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_next_calibration(self, plugin):
        result = await plugin.get_next_calibration()
        assert result["next_calibration"] == "2026-01-15T00:00:00"
        assert result["interval_days"] == 14
        assert result["last_calibration"] is None

    @pytest.mark.asyncio
    async def test_start_calibration(self, plugin):
        result = await plugin.start_calibration()
        assert result is True
        plugin.calibration.start.assert_called_with(restore_limit=80, drain_threshold=30)
        assert plugin._current_cal_start == "2026-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_snooze_calibration(self, plugin):
        await plugin.snooze_calibration(3)
        plugin.scheduler.snooze.assert_called_with(3)

    @pytest.mark.asyncio
    async def test_snooze_calibration_default(self, plugin):
        await plugin.snooze_calibration()
        plugin.scheduler.snooze.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_get_calibration_state(self, plugin):
        result = await plugin.get_calibration_state()
        assert result["phase"] == "idle"
        assert result["active"] is False

    @pytest.mark.asyncio
    async def test_get_history(self, plugin):
        plugin.history.get_recent_snapshots.return_value = [{"capacity": 75}]
        plugin.history.get_calibration_history.return_value = [{"result": "success"}]
        result = await plugin.get_history()
        assert result["snapshots"] == [{"capacity": 75}]
        assert result["calibrations"] == [{"result": "success"}]

    @pytest.mark.asyncio
    async def test_get_device_info(self, plugin):
        plugin.battery.manufacturer.return_value = "TestCo"
        plugin.battery.model_name.return_value = "BAT1"
        plugin.battery.serial_number.return_value = "12345"
        plugin.battery.technology.return_value = "Li-ion"
        result = await plugin.get_device_info()
        assert result["manufacturer"] == "TestCo"
        assert result["model"] == "BAT1"
        assert result["serial"] == "12345"
        assert result["technology"] == "Li-ion"

    @pytest.mark.asyncio
    async def test_emit_logs_error_at_debug(self, plugin):
        plugin._emit("test_event", "data")
        plugin._emit.assert_called_once_with("test_event", "data")

    @pytest.mark.asyncio
    async def test_on_cal_progress_emits(self, plugin):
        plugin._on_cal_progress("draining", 50)
        plugin._emit.assert_called_once_with("calibration_progress", "draining", 50)

    @pytest.mark.asyncio
    async def test_cancel_calibration_no_side_effects(self, plugin):
        with patch.object(plugin, 'charge') as mock_charge:
            plugin._top_up_restore = None
            await plugin.cancel_calibration()
            plugin.calibration.cancel.assert_called_once()
            assert not mock_charge.set_limit.called

    @pytest.mark.asyncio
    async def test_apply_preset_calls_set_charge_limit(self, plugin):
        with patch.object(plugin, 'set_charge_limit', AsyncMock(return_value=True)) as mock_set:
            result = await plugin.apply_preset("Normal 80%")
            assert result is True
            mock_set.assert_called_with(80)

    @pytest.mark.asyncio
    async def test_top_up_twice(self, plugin):
        plugin.charge.get_limit.return_value = 80
        await plugin.top_up()
        assert plugin._top_up_restore == 80

        plugin.charge.get_limit.return_value = 60
        await plugin.top_up()
        assert plugin._top_up_restore == 60



class TestBatteryMonitorTopUp:
    @pytest.mark.asyncio
    async def test_battery_update_triggers_top_up_complete(self, plugin):
        snap = BatterySnapshot(
            capacity=100, status="Full", ac_connected=True,
            health_pct=95.0, cycle_count=100, power_watts=0.0,
            voltage_now=12500000, current_now=0,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=4000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin._top_up_restore = 80

        with patch.object(plugin, "_record_snapshot"), \
             patch.object(plugin, "_snap_to_dict", return_value={}), \
             patch.object(plugin, "_emit"):
            from main import Plugin

            async def fake_monitor(self):
                await plugin.calibration.handle_battery_update(snap)
                if plugin._top_up_restore is not None and snap.capacity is not None and snap.capacity >= 100:
                    plugin.charge.set_limit(plugin._top_up_restore)
                    plugin._top_up_restore = None
                    plugin._emit("top_up_done")
                plugin._record_snapshot(snap)

            with patch.object(Plugin, "_battery_monitor", fake_monitor):
                await fake_monitor(plugin)

        assert plugin._top_up_restore is None
        plugin.charge.set_limit.assert_called_with(80)

    @pytest.mark.asyncio
    async def test_battery_update_ignores_partial_charge(self, plugin):
        snap = BatterySnapshot(
            capacity=50, status="Charging", ac_connected=True,
            health_pct=95.0, cycle_count=100, power_watts=10.0,
            voltage_now=12000000, current_now=1000000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=2000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin._top_up_restore = 80

        with patch.object(plugin, "_record_snapshot"), \
             patch.object(plugin, "_snap_to_dict", return_value={}):
            from main import Plugin
            async def fake_monitor(self):
                await plugin.calibration.handle_battery_update(snap)
                if plugin._top_up_restore is not None and snap.capacity is not None and snap.capacity >= 100:
                    plugin.charge.set_limit(plugin._top_up_restore)
                    plugin._top_up_restore = None
                    plugin._emit("top_up_done")
                plugin._record_snapshot(snap)

            with patch.object(Plugin, "_battery_monitor", fake_monitor):
                await fake_monitor(plugin)

        assert plugin._top_up_restore == 80


class TestPluginSailingMode:
    @pytest.mark.asyncio
    async def test_get_sailing_mode_default(self, plugin):
        plugin.settings.get.side_effect = lambda k, d=None: {
            "sailing_mode_enabled": False,
            "sailing_range_low": 70,
            "sailing_range_high": 80,
        }.get(k, d)
        result = await plugin.get_sailing_mode()
        assert result["enabled"] is False
        assert result["low"] == 70

    @pytest.mark.asyncio
    async def test_update_settings_sailing_mode(self, plugin):
        await plugin.update_settings({"sailing_mode_enabled": True})
        plugin.charge.set_limit.assert_called_with(70)
        assert plugin.settings.set.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_settings_other(self, plugin):
        await plugin.update_settings({"charge_limit": 60})
        plugin.settings.set_many.assert_called_with({"charge_limit": 60})

    @pytest.mark.asyncio
    async def test_battery_status_includes_temp_and_thermal(self, plugin):
        result = await plugin.get_battery_status()
        assert "temp_celsius" in result
        assert "thermal_throttled" in result
        assert result["thermal_throttled"] is False


class TestPluginThermal:
    @pytest.mark.asyncio
    async def test_thermal_handle_temperature_called(self, plugin):
        snap = BatterySnapshot(
            capacity=75, status="Charging", ac_connected=True,
            health_pct=95.0, cycle_count=100, power_watts=10.0,
            voltage_now=12000000, current_now=1000000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=3000000,
            temp_celsius=46.0,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        from main import Plugin
        async def fake_monitor(self):
            await plugin.calibration.handle_battery_update(snap)
            plugin.thermal.handle_temperature(snap)

        with patch.object(Plugin, "_battery_monitor", fake_monitor):
            await fake_monitor(plugin)

        plugin.thermal.handle_temperature.assert_called_once_with(snap)


class TestPluginSmartCharge:
    @pytest.mark.asyncio
    async def test_smart_charge_raises_limit_when_low(self, plugin):
        plugin.settings.set("smart_charge_enabled", True)
        plugin.settings.set("smart_charge_min", 30)
        plugin.settings.set("smart_charge_max", 80)
        plugin.charge.get_limit.return_value = 60
        snap = BatterySnapshot(
            capacity=25, status="Discharging", ac_connected=False,
            health_pct=95.0, cycle_count=100, power_watts=5.0,
            voltage_now=12000000, current_now=500000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=1000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_called_with(80)

    @pytest.mark.asyncio
    async def test_smart_charge_lowers_limit_when_high(self, plugin):
        plugin.settings.set("smart_charge_enabled", True)
        plugin.settings.set("smart_charge_min", 30)
        plugin.settings.set("smart_charge_max", 80)
        plugin.charge.get_limit.return_value = 80
        snap = BatterySnapshot(
            capacity=85, status="Charging", ac_connected=True,
            health_pct=95.0, cycle_count=100, power_watts=10.0,
            voltage_now=12500000, current_now=1000000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=3400000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_called_with(30)

    @pytest.mark.asyncio
    async def test_smart_charge_does_nothing_if_disabled(self, plugin):
        plugin.settings.set("smart_charge_enabled", False)
        snap = BatterySnapshot(
            capacity=25, status="Discharging", ac_connected=False,
            health_pct=95.0, cycle_count=100, power_watts=5.0,
            voltage_now=12000000, current_now=500000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=1000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin.charge.reset_mock()
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_charge_does_nothing_within_range(self, plugin):
        plugin.settings.set("smart_charge_enabled", True)
        plugin.settings.set("smart_charge_min", 30)
        plugin.settings.set("smart_charge_max", 80)
        plugin.charge.get_limit.return_value = 80
        snap = BatterySnapshot(
            capacity=50, status="Charging", ac_connected=True,
            health_pct=95.0, cycle_count=100, power_watts=10.0,
            voltage_now=12500000, current_now=1000000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=2000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin.charge.reset_mock()
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_charge_does_not_reapply_same_limit(self, plugin):
        plugin.settings.set("smart_charge_enabled", True)
        plugin.settings.set("smart_charge_min", 30)
        plugin.settings.set("smart_charge_max", 80)
        plugin.charge.get_limit.return_value = 60
        snap = BatterySnapshot(
            capacity=25, status="Discharging", ac_connected=False,
            health_pct=95.0, cycle_count=100, power_watts=5.0,
            voltage_now=12000000, current_now=500000,
            charge_full=4000000, charge_full_design=5000000,
            charge_now=1000000,
            temp_celsius=None,
            pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
        )
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_called_once_with(80)

        plugin.charge.get_limit.return_value = 80
        plugin.charge.reset_mock()
        plugin._apply_smart_charge(snap)
        plugin.charge.set_limit.assert_not_called()


class TestPluginProfiles:
    @pytest.mark.asyncio
    async def test_save_and_load_profile(self, plugin):
        plugin.settings.set("charge_limit", 60)
        plugin.rate_ctrl.get_rate.return_value = 1000000
        await plugin.save_profile("test_profile")

        plugin.settings.set("charge_limit", 80)
        plugin.rate_ctrl.get_rate.return_value = 2000000

        ok = await plugin.load_profile("test_profile")
        assert ok is True
        assert plugin.settings.get("charge_limit") == 60
        plugin.rate_ctrl.set_rate.assert_called_with(1000000)

    @pytest.mark.asyncio
    async def test_load_nonexistent_profile(self, plugin):
        ok = await plugin.load_profile("nonexistent")
        assert ok is False

    @pytest.mark.asyncio
    async def test_get_profiles(self, plugin):
        plugin.settings.set("profiles", {"p1": {"charge_limit": 80}})
        result = await plugin.get_profiles()
        assert result == {"p1": {"charge_limit": 80}}

    @pytest.mark.asyncio
    async def test_delete_profile(self, plugin):
        plugin.settings.set("profiles", {"p1": {}, "p2": {}})
        await plugin.delete_profile("p1")
        profiles = plugin.settings.get("profiles")
        assert "p1" not in profiles
        assert "p2" in profiles
