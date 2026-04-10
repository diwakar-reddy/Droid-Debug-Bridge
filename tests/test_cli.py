"""Tests for the CLI argument parsing and dispatch."""

import json
from unittest.mock import patch, MagicMock

import pytest

from ddb.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "ddb" in captured.out


def test_no_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 1


def _mock_preflight_pass():
    """Patch the auto-preflight adb binary check to always pass."""
    return patch(
        "ddb.modules.doctor._check_adb_binary",
        return_value={"name": "ADB binary", "status": "ok", "detail": "mocked"},
    )


def test_devices_dispatch(capsys):
    """Verify 'cab devices' routes to device.devices()."""
    with _mock_preflight_pass(), \
         patch("ddb.cli.Adb") as MockCliAdb, \
         patch("ddb.modules.device.devices") as mock_devices:
        mock_adb = MagicMock()
        MockCliAdb.return_value = mock_adb
        mock_devices.return_value = {"success": True}
        main(["devices"])
        mock_devices.assert_called_once()


def test_tap_dispatch():
    """Verify 'cab tap 100 200' routes correctly."""
    with _mock_preflight_pass(), \
         patch("ddb.cli.Adb") as MockAdb, \
         patch("ddb.modules.ui.tap") as mock_tap:
        mock_tap.return_value = {"success": True}
        main(["tap", "100", "200"])
        mock_tap.assert_called_once()
        args = mock_tap.call_args
        assert args[0][1] == 100  # x
        assert args[0][2] == 200  # y


def test_doctor_dispatch(capsys):
    """Verify 'cab doctor' routes to doctor.doctor()."""
    with patch("ddb.cli.Adb") as MockAdb, \
         patch("ddb.modules.doctor.doctor") as mock_doctor:
        mock_doctor.return_value = {"success": True, "data": {"overall": "healthy"}}
        main(["doctor"])
        mock_doctor.assert_called_once()
