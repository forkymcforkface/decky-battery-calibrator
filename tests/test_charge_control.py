from unittest.mock import MagicMock, patch

from battery_calibrator.charge_control import (
    ChargeControl,
    DBusChargeControl,
    SysfsChargeControl,
    create_charge_control,
)


def test_charge_control_is_abstract():
    assert type(ChargeControl).__name__ == "ABCMeta"


def test_dbus_get_limit_returns_int_when_sysfs_works():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "80\n"
        ctrl = DBusChargeControl()
        assert ctrl.get_limit() == 80


def test_dbus_get_limit_returns_none_when_sysfs_missing():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = FileNotFoundError
        ctrl = DBusChargeControl()
        assert ctrl.get_limit() is None


def test_dbus_set_limit_calls_busctl():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ctrl = DBusChargeControl()
        result = ctrl.set_limit(80)
        assert result is True
        mock_run.assert_called_once()


def test_dbus_set_limit_clamps_min():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ctrl = DBusChargeControl()
        ctrl.set_limit(5)
        args = mock_run.call_args[0][0]
        assert "20" in args


def test_dbus_set_limit_clamps_max():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ctrl = DBusChargeControl()
        ctrl.set_limit(200)
        args = mock_run.call_args[0][0]
        assert "100" in args


def test_sysfs_get_limit_reads_file():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "75\n"
        ctrl = SysfsChargeControl()
        assert ctrl.get_limit() == 75


def test_sysfs_get_limit_returns_none_on_error():
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = PermissionError
        ctrl = SysfsChargeControl()
        assert ctrl.get_limit() is None


def test_sysfs_set_limit_writes_file():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = SysfsChargeControl()
        result = ctrl.set_limit(60)
        assert result is True
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("60")


def test_sysfs_set_limit_clamps():
    with patch("builtins.open", MagicMock()) as mock_open:
        ctrl = SysfsChargeControl()
        ctrl.set_limit(150)
        handle = mock_open.return_value.__enter__.return_value
        handle.write.assert_called_once_with("100")


def test_create_charge_control_returns_dbus_when_available():
    with patch("battery_calibrator.charge_control.DBusChargeControl.get_limit") as mock_get:
        mock_get.return_value = 80
        ctrl = create_charge_control()
        assert isinstance(ctrl, DBusChargeControl)


def test_create_charge_control_falls_back_to_sysfs():
    with patch("battery_calibrator.charge_control.DBusChargeControl.get_limit") as mock_get:
        mock_get.side_effect = FileNotFoundError
        with patch("battery_calibrator.charge_control.SysfsChargeControl"):
            ctrl = create_charge_control()
            assert not isinstance(ctrl, DBusChargeControl)
