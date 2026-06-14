import os
import tempfile
from pathlib import Path

import pytest
from battery_calibrator.battery import BatteryReader, BatterySnapshot


@pytest.fixture
def fake_sysfs():
    with tempfile.TemporaryDirectory() as d:
        bat = Path(d) / "BAT1"
        ac = Path(d) / "ACAD"
        bat.mkdir()
        ac.mkdir()
        (bat / "status").write_text("Charging\n")
        (bat / "capacity").write_text("85\n")
        (bat / "charge_now").write_text("4000000\n")
        (bat / "charge_full").write_text("4800000\n")
        (bat / "charge_full_design").write_text("5000000\n")
        (bat / "cycle_count").write_text("42\n")
        (bat / "current_now").write_text("1000000\n")
        (bat / "voltage_now").write_text("4150000\n")
        (bat / "manufacturer").write_text("TestCorp\n")
        (bat / "model_name").write_text("BAT-9000\n")
        (bat / "serial_number").write_text("SN12345\n")
        (bat / "technology").write_text("Li-ion\n")
        (ac / "online").write_text("1\n")
        yield str(bat), str(ac)


@pytest.fixture
def reader(fake_sysfs):
    bat_path, ac_path = fake_sysfs
    r = BatteryReader()
    r._base = bat_path
    r._ac = os.path.join(os.path.dirname(ac_path), "ACAD", "online")
    return r


def test_snapshot_returns_all_fields(reader):
    snap = reader.snapshot()
    assert isinstance(snap, BatterySnapshot)
    assert snap.capacity == 85
    assert snap.status == "Charging"
    assert snap.ac_connected is True
    assert snap.cycle_count == 42
    assert snap.charge_full == 4800000
    assert snap.charge_full_design == 5000000
    assert snap.charge_now == 4000000
    assert snap.voltage_now == 4150000
    assert snap.current_now == 1000000


def test_health_calculation(reader):
    snap = reader.snapshot()
    assert snap.health_pct == 96.0


def test_power_calculation(reader):
    snap = reader.snapshot()
    assert snap.power_watts is not None
    assert snap.power_watts > 0


def test_ac_disconnected(reader):
    ac_path = os.path.join(os.path.dirname(reader._ac), "online")
    with open(ac_path, "w") as f:
        f.write("0\n")
    snap = reader.snapshot()
    assert snap.ac_connected is False


def test_missing_file_returns_none(reader):
    os.remove(os.path.join(reader._base, "cycle_count"))
    snap = reader.snapshot()
    assert snap.cycle_count is None


def test_manufacturer(reader):
    assert reader.manufacturer() == "TestCorp"


def test_model_name(reader):
    assert reader.model_name() == "BAT-9000"


def test_serial_number(reader):
    assert reader.serial_number() == "SN12345"


def test_technology(reader):
    assert reader.technology() == "Li-ion"


def test_health_none_when_charge_full_missing(reader):
    os.remove(os.path.join(reader._base, "charge_full"))
    snap = reader.snapshot()
    assert snap.health_pct is None


def test_health_none_when_design_zero():
    with tempfile.TemporaryDirectory() as d:
        bat = Path(d) / "BAT1"
        ac = Path(d) / "ACAD"
        bat.mkdir()
        ac.mkdir()
        (bat / "status").write_text("Discharging\n")
        (bat / "capacity").write_text("50\n")
        (bat / "charge_full").write_text("4800000\n")
        (bat / "charge_full_design").write_text("0\n")
        (bat / "charge_now").write_text("2400000\n")
        (ac / "online").write_text("0\n")
        r = BatteryReader()
        r._base = str(bat)
        r._ac = os.path.join(str(ac), "online")
        snap = r.snapshot()
        assert snap.health_pct is None


def test_power_none_when_current_missing(reader):
    os.remove(os.path.join(reader._base, "current_now"))
    snap = reader.snapshot()
    assert snap.power_watts is None
