from unittest.mock import MagicMock, patch

from battery_calibrator.rate_control import ChargeRateControl


def test_available_with_path():
    ctrl = ChargeRateControl(sysfs_path="/fake/path")
    assert ctrl.available is True


def test_not_available_without_path():
    ctrl = ChargeRateControl(sysfs_path=None)
    assert ctrl.available is False


def test_get_rate_reads_file():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "1500000\n"
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.get_rate() == 1500000


def test_get_rate_returns_none_on_error():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = FileNotFoundError
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.get_rate() is None


def test_get_rate_none_when_unavailable():
    ctrl = ChargeRateControl(sysfs_path=None)
    assert ctrl.get_rate() is None


def test_set_rate_writes_file():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        result = ctrl.set_rate(2000000)
        assert result is True
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("2000000")


def test_set_rate_clamps_min():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        ctrl.set_rate(-100)
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("0")


def test_set_rate_clamps_max():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        ctrl.set_rate(9999999)
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("3000000")


def test_set_rate_returns_false_on_error():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = PermissionError
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.set_rate(1000000) is False


def test_set_rate_false_when_unavailable():
    ctrl = ChargeRateControl(sysfs_path=None)
    assert ctrl.set_rate(1000000) is False


def test_get_rate_amps():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "1500000\n"
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.get_rate_amps() == 1.5


def test_get_rate_amps_none():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = FileNotFoundError
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.get_rate_amps() is None


def test_set_rate_amps():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        result = ctrl.set_rate_amps(2.5)
        assert result is True
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("2500000")


def test_set_rate_amps_clamps():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        ctrl.set_rate_amps(10.0)
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("3000000")


def test_not_available_with_file_missing():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = FileNotFoundError
        ctrl = ChargeRateControl(sysfs_path="/fake/rate")
        assert ctrl.available is True
        assert ctrl.get_rate() is None
