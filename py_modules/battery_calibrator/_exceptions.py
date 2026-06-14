class BatteryCalibratorError(Exception):
    pass


class SysfsReadError(BatteryCalibratorError):
    def __init__(self, path: str, reason: str = ""):
        self.path = path
        super().__init__(f"Failed to read {path}: {reason}")


class ChargeControlError(BatteryCalibratorError):
    def __init__(self, method: str, reason: str = ""):
        self.method = method
        super().__init__(f"Charge control ({method}) failed: {reason}")


class CalibrationError(BatteryCalibratorError):
    pass


class SettingsError(BatteryCalibratorError):
    pass
