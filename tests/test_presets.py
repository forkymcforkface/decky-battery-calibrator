import pytest
from battery_calibrator.presets import BUILTIN_PRESETS, PresetManager


class DictSettings:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def get_all(self):
        return dict(self._data)

    def set_many(self, updates):
        self._data.update(updates)


@pytest.fixture
def settings():
    return DictSettings()


@pytest.fixture
def pm(settings):
    return PresetManager(settings)


def test_builtin_presets_loaded(pm):
    all_ = pm.get_all()
    assert all_["Storage"] == 60
    assert all_["Normal"] == 80
    assert all_["Full"] == 100
    assert all_["Travel"] == 95


def test_builtin_count():
    assert len(BUILTIN_PRESETS) == 4


def test_get_limit_builtin(pm):
    assert pm.get_limit("Normal") == 80
    assert pm.get_limit("Full") == 100


def test_get_limit_unknown(pm):
    assert pm.get_limit("NonExistent") is None


def test_add_custom_preset(pm):
    pm.add("BatterySaver", 50)
    assert pm.get_limit("BatterySaver") == 50


def test_add_overwrites_existing(pm):
    pm.add("MyPreset", 70)
    pm.add("MyPreset", 75)
    assert pm.get_limit("MyPreset") == 75


def test_add_overwrites_builtin(pm):
    pm.add("Normal", 50)
    assert pm.get_limit("Normal") == 50


def test_add_clamps_min(pm):
    pm.add("Low", 5)
    assert pm.get_limit("Low") == 20


def test_add_clamps_max(pm):
    pm.add("High", 150)
    assert pm.get_limit("High") == 100


def test_remove_custom(pm):
    pm.add("Temp", 55)
    pm.remove("Temp")
    assert pm.get_limit("Temp") is None


def test_cannot_remove_builtin(pm):
    assert pm.is_builtin("Normal")
    pm.remove("Normal")
    assert pm.get_limit("Normal") == 80


def test_custom_overrides_builtin_in_get_all(pm):
    pm.add("Storage", 55)
    all_ = pm.get_all()
    assert all_["Storage"] == 55


def test_is_builtin_true(pm):
    assert pm.is_builtin("Full") is True
    assert pm.is_builtin("Storage") is True


def test_is_builtin_false(pm):
    assert pm.is_builtin("CustomThing") is False


def test_multiple_custom_presets(pm):
    pm.add("GameMode", 85)
    pm.add("MovieMode", 70)
    assert pm.get_limit("GameMode") == 85
    assert pm.get_limit("MovieMode") == 70
    assert len(pm.get_all()) == 6


def test_remove_nonexistent(pm):
    pm.remove("NothingHere")
    assert len(pm.get_all()) == 4


def test_persists_across_instances():
    s = DictSettings()
    pm1 = PresetManager(s)
    pm1.add("Custom1", 65)

    pm2 = PresetManager(s)
    assert pm2.get_limit("Custom1") == 65


def test_empty_custom_presets_returns_only_builtin(pm):
    all_ = pm.get_all()
    assert len(all_) == 4
    assert all_["Normal"] == 80
