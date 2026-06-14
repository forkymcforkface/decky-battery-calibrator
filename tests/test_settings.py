import json
import os
import tempfile

import pytest
from battery_calibrator.settings import SettingsManager


@pytest.fixture
def settings_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_get_default(settings_dir):
    s = SettingsManager(settings_dir)
    assert s.get("charge_limit") == 80
    assert s.get("calibration_interval_days") == 14
    assert s.get("nonexistent") is None


def test_get_custom_default(settings_dir):
    s = SettingsManager(settings_dir)
    assert s.get("missing_key", "fallback") == "fallback"


def test_set_and_get(settings_dir):
    s = SettingsManager(settings_dir)
    s.set("charge_limit", 90)
    assert s.get("charge_limit") == 90


def test_set_many(settings_dir):
    s = SettingsManager(settings_dir)
    s.set_many({"charge_limit": 70, "calibration_interval_days": 21})
    assert s.get("charge_limit") == 70
    assert s.get("calibration_interval_days") == 21


def test_persists_to_disk(settings_dir):
    s1 = SettingsManager(settings_dir)
    s1.set("charge_limit", 60)
    s1.set("calibration_interval_days", 7)
    del s1

    s2 = SettingsManager(settings_dir)
    assert s2.get("charge_limit") == 60
    assert s2.get("calibration_interval_days") == 7


def test_reset(settings_dir):
    s = SettingsManager(settings_dir)
    s.set("charge_limit", 50)
    s.reset()
    assert s.get("charge_limit") == 80


def test_get_all(settings_dir):
    s = SettingsManager(settings_dir)
    s.set("charge_limit", 95)
    all_ = s.get_all()
    assert all_["charge_limit"] == 95
    assert "calibration_interval_days" in all_


def test_invalid_json_fallback(settings_dir):
    path = os.path.join(settings_dir, "battery_calibrator.json")
    with open(path, "w") as f:
        f.write("corrupt{json")
    s = SettingsManager(settings_dir)
    assert s.get("charge_limit") == 80


def test_empty_json_fallback(settings_dir):
    path = os.path.join(settings_dir, "battery_calibrator.json")
    with open(path, "w") as f:
        f.write("")
    s = SettingsManager(settings_dir)
    assert s.get("charge_limit") == 80


def test_partial_file_merged(settings_dir):
    path = os.path.join(settings_dir, "battery_calibrator.json")
    with open(path, "w") as f:
        json.dump({"charge_limit": 55}, f)
    s = SettingsManager(settings_dir)
    assert s.get("charge_limit") == 55
    assert s.get("calibration_interval_days") == 14
