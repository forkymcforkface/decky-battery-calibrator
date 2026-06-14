from battery_calibrator.settings import SettingsManager

BUILTIN_PRESETS: dict[str, int] = {
    "Storage": 60,
    "Normal": 80,
    "Full": 100,
    "Travel": 95,
}


class PresetManager:
    def __init__(self, settings: SettingsManager):
        self._settings = settings

    def get_all(self) -> dict[str, int]:
        custom = self._settings.get("custom_presets", {})
        return {**BUILTIN_PRESETS, **custom}

    def get_limit(self, name: str) -> int | None:
        return self.get_all().get(name)

    def add(self, name: str, limit: int) -> None:
        limit = max(20, min(100, limit))
        custom = dict(self._settings.get("custom_presets", {}))
        custom[name] = limit
        self._settings.set("custom_presets", custom)

    def remove(self, name: str) -> None:
        if name in BUILTIN_PRESETS:
            return
        custom = dict(self._settings.get("custom_presets", {}))
        custom.pop(name, None)
        self._settings.set("custom_presets", custom)

    def is_builtin(self, name: str) -> bool:
        return name in BUILTIN_PRESETS
