import asyncio
from unittest.mock import MagicMock

import pytest
from battery_calibrator.battery import BatterySnapshot
from battery_calibrator.calibration import CalibrationEngine, CalibrationPhase


def make_snap(capacity=80, status="Discharging", ac_connected=False):
    return BatterySnapshot(
        capacity=capacity,
        status=status,
        ac_connected=ac_connected,
        health_pct=95.0,
        cycle_count=42,
        power_watts=4.2,
        voltage_now=4150000,
        current_now=1000000,
        charge_full=4800000,
        charge_full_design=5000000,
        charge_now=4000000,
        temp_celsius=None,
        pd_current_ma=None, pd_voltage_mv=None, pd_watts=None,
    )


@pytest.fixture
def engine():
    charge = MagicMock()
    charge.set_limit.return_value = True
    charge.get_limit.return_value = 80
    battery = MagicMock()
    battery.snapshot.return_value = make_snap(capacity=80, ac_connected=False)
    engine = CalibrationEngine(charge, battery)
    return engine


@pytest.mark.asyncio
async def test_start_returns_true(engine):
    ok = await engine.start(restore_limit=80)
    assert ok is True
    assert engine.is_active is True
    assert engine.phase == CalibrationPhase.UNPLUG_AND_DRAIN


@pytest.mark.asyncio
async def test_start_when_active_returns_false(engine):
    await engine.start(restore_limit=80)
    ok = await engine.start(restore_limit=80)
    assert ok is False


def test_is_active_idle(engine):
    assert engine.is_active is False


def test_is_active_complete(engine):
    engine._phase = CalibrationPhase.COMPLETE
    assert engine.is_active is False


def test_is_active_timed_out(engine):
    engine._phase = CalibrationPhase.TIMED_OUT
    assert engine.is_active is False


def test_is_active_unplug(engine):
    engine._phase = CalibrationPhase.UNPLUG_AND_DRAIN
    assert engine.is_active is True


def test_is_active_charging(engine):
    engine._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
    assert engine.is_active is True


@pytest.mark.asyncio
async def test_cancel_restores_limit(engine):
    await engine.start(restore_limit=80)
    engine.cancel()
    engine._charge.set_limit.assert_called_with(80)
    assert engine.phase == CalibrationPhase.IDLE


@pytest.mark.asyncio
async def test_drain_transition(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=25, ac_connected=False)
    await engine.start(restore_limit=80)
    snap = make_snap(capacity=25, ac_connected=False)
    await engine.handle_battery_update(snap)
    assert engine.phase == CalibrationPhase.PLUG_IN_AND_CHARGE


@pytest.mark.asyncio
async def test_no_transition_when_plugged_and_above_threshold(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=50, ac_connected=True)
    await engine.start(restore_limit=80)
    snap = make_snap(capacity=50, ac_connected=True)
    await engine.handle_battery_update(snap)
    assert engine.phase == CalibrationPhase.UNPLUG_AND_DRAIN


@pytest.mark.asyncio
async def test_charge_completion(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=25, ac_connected=False)
    await engine.start(restore_limit=80)

    engine._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
    snap = make_snap(capacity=100, ac_connected=True)
    await engine.handle_battery_update(snap)
    assert engine.phase == CalibrationPhase.COMPLETE


@pytest.mark.asyncio
async def test_charge_not_complete_below_100(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=25, ac_connected=False)
    await engine.start(restore_limit=80)

    engine._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
    snap = make_snap(capacity=99, ac_connected=True)
    await engine.handle_battery_update(snap)
    assert engine.phase == CalibrationPhase.PLUG_IN_AND_CHARGE


@pytest.mark.asyncio
async def test_complete_restores_limit(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=25, ac_connected=False)
    await engine.start(restore_limit=70)

    engine._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
    snap = make_snap(capacity=100, ac_connected=True)
    await engine.handle_battery_update(snap)
    engine._charge.set_limit.assert_called_with(70)


@pytest.mark.asyncio
async def test_progress_callback_during_drain(engine):
    progress = MagicMock()
    engine.on_progress(progress)
    engine._battery.snapshot.return_value = make_snap(capacity=80, ac_connected=False)
    await engine.start(restore_limit=80)

    snap = make_snap(capacity=60, ac_connected=False)
    await engine.handle_battery_update(snap)
    progress.assert_any_call("draining", 60)


@pytest.mark.asyncio
async def test_done_callback_on_complete(engine):
    done = MagicMock()
    engine.on_done(done)
    engine._battery.snapshot.return_value = make_snap(capacity=25, ac_connected=False)
    await engine.start(restore_limit=80)

    engine._phase = CalibrationPhase.PLUG_IN_AND_CHARGE
    snap = make_snap(capacity=100, ac_connected=True)
    await engine.handle_battery_update(snap)
    done.assert_called_once_with("complete", None)


@pytest.mark.asyncio
async def test_timeout_triggers_done(engine, monkeypatch):
    monkeypatch.setattr("battery_calibrator.calibration.CALIBRATION_TIMEOUT_HOURS", 0.000001)
    done = MagicMock()
    engine.on_done(done)
    engine._battery.snapshot.return_value = make_snap(capacity=50, ac_connected=False)
    await engine.start(restore_limit=80, drain_threshold=30)

    await asyncio.sleep(0.05)

    assert engine.phase == CalibrationPhase.TIMED_OUT
    done.assert_called_once()
    assert done.call_args[0][0] == "timed_out"


@pytest.mark.asyncio
async def test_timeout_restores_limit(engine, monkeypatch):
    monkeypatch.setattr("battery_calibrator.calibration.CALIBRATION_TIMEOUT_HOURS", 0.000001)
    engine._battery.snapshot.return_value = make_snap(capacity=50, ac_connected=False)
    await engine.start(restore_limit=90)

    await asyncio.sleep(0.05)

    engine._charge.set_limit.assert_called_with(90)


@pytest.mark.asyncio
async def test_immediate_evaluation_on_start_above_threshold(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=20, ac_connected=False)
    await engine.start(restore_limit=80, drain_threshold=30)
    assert engine.phase == CalibrationPhase.PLUG_IN_AND_CHARGE


@pytest.mark.asyncio
async def test_immediate_evaluation_stays_in_drain_above_threshold(engine):
    engine._battery.snapshot.return_value = make_snap(capacity=50, ac_connected=False)
    await engine.start(restore_limit=80, drain_threshold=30)
    assert engine.phase == CalibrationPhase.UNPLUG_AND_DRAIN
