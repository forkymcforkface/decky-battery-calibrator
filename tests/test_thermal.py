from unittest.mock import MagicMock

from battery_calibrator.battery import BatterySnapshot
from battery_calibrator.thermal import ThermalMonitor

DEFAULTS = {
    "heat_protection_enabled": True,
    "heat_threshold_celsius": 40,
}


def make_settings(**overrides):
    s = MagicMock()
    s.get.side_effect = lambda k, d=None: overrides.get(k, DEFAULTS.get(k, d))
    return s


def snap(temp: float | None = 25.0, cap: int | None = 75):
    return BatterySnapshot(
        capacity=cap, status="Charging", ac_connected=True,
        health_pct=95.0, cycle_count=100, power_watts=10.0,
        voltage_now=12000000, current_now=1000000,
        charge_full=4000000, charge_full_design=5000000,
        charge_now=3000000,
        temp_celsius=temp,
        pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
    )


class TestThermalMonitor:
    def test_init_not_throttled(self):
        charge = MagicMock()
        tm = ThermalMonitor(charge, make_settings())
        assert not tm.throttled
        assert tm.restore_limit is None

    def test_ignores_when_disabled(self):
        charge = MagicMock()
        tm = ThermalMonitor(charge, make_settings(heat_protection_enabled=False))
        tm.handle_temperature(snap(temp=50.0))
        assert not tm.throttled
        charge.set_limit.assert_not_called()

    def test_ignores_none_temp(self):
        charge = MagicMock()
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=None))
        assert not tm.throttled
        charge.set_limit.assert_not_called()

    def test_pauses_at_threshold(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled
        assert tm.restore_limit == 80
        charge.set_limit.assert_called_once_with(30)

    def test_pauses_at_cap_when_below_30(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=25))
        assert tm.throttled
        charge.set_limit.assert_called_once_with(25)

    def test_does_not_pause_below_threshold(self):
        charge = MagicMock()
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=38.0))
        assert not tm.throttled
        charge.set_limit.assert_not_called()

    def test_unpauses_when_cool(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled
        charge.reset_mock()

        tm.handle_temperature(snap(temp=37.0, cap=75))
        assert not tm.throttled
        assert tm.restore_limit is None
        charge.set_limit.assert_called_once_with(80)

    def test_does_not_restore_just_below_threshold(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        charge.reset_mock()

        tm.handle_temperature(snap(temp=39.0, cap=75))
        assert tm.throttled
        charge.set_limit.assert_not_called()

    def test_double_no_op(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        charge.reset_mock()

        tm.handle_temperature(snap(temp=50.0, cap=75))
        charge.set_limit.assert_not_called()
        assert tm.throttled

    def test_unpause_on_reset(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled

        tm.reset()
        assert not tm.throttled
        charge.set_limit.assert_called_with(80)

    def test_handles_none_capacity(self):
        charge = MagicMock()
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=None))
        assert not tm.throttled
        charge.set_limit.assert_not_called()

    def test_uses_custom_pause_limit(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings(), pause_limit=50)
        tm.handle_temperature(snap(temp=41.0, cap=75))
        charge.set_limit.assert_called_once_with(50)

    def test_cool_down_prevents_rapid_repause(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings(), min_resume_interval=300.0)
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled
        tm._unpause()
        assert not tm.throttled
        charge.reset_mock()

        tm.handle_temperature(snap(temp=41.0, cap=70))
        assert not tm.throttled, "should not re-pause within cooldown"
        charge.set_limit.assert_not_called()

    def test_cool_down_expires(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings(), min_resume_interval=0)
        tm.handle_temperature(snap(temp=41.0, cap=75))
        tm._unpause()

        tm.handle_temperature(snap(temp=41.0, cap=70))
        assert tm.throttled

    def test_cool_down_first_pause_no_block(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        tm = ThermalMonitor(charge, make_settings())
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled
        charge.set_limit.assert_called_once_with(30)

    def test_restores_when_disabled_during_throttle(self):
        charge = MagicMock()
        charge.get_limit.return_value = 80
        settings = make_settings(heat_protection_enabled=True)
        tm = ThermalMonitor(charge, settings)
        tm.handle_temperature(snap(temp=41.0, cap=75))
        assert tm.throttled
        charge.reset_mock()

        settings.get.side_effect = lambda k, d=None: {"heat_protection_enabled": False}.get(k, DEFAULTS.get(k, d))
        tm.handle_temperature(snap(temp=50.0, cap=75))
        assert not tm.throttled
        charge.set_limit.assert_called_once_with(80)

