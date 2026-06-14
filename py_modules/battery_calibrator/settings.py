import json
import os
import threading
from typing import Any

from battery_calibrator._constants import DEFAULT_SETTINGS, SETTINGS_FILENAME
from battery_calibrator._exceptions import SettingsError


class SettingsManager:
    def __init__(self, settings_dir: str):
        self._path = os.path.join(settings_dir, SETTINGS_FILENAME)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                stored = json.load(f)
                self._data = {**DEFAULT_SETTINGS, **stored}
        except FileNotFoundError:
            self._data = dict(DEFAULT_SETTINGS)
        except (json.JSONDecodeError, PermissionError):
            self._data = dict(DEFAULT_SETTINGS)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except (OSError, PermissionError) as e:
            raise SettingsError(f"Cannot save settings to {self._path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def set_many(self, updates: dict[str, Any]) -> None:
        with self._lock:
            self._data.update(updates)
            self._save()

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def reset(self) -> None:
        with self._lock:
            self._data = dict(DEFAULT_SETTINGS)
            self._save()
