"""Tests for the Adb wrapper — uses mocking, no real device needed."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from ddb.utils.adb import Adb, AdbResult, AdbError


def test_adb_find_fallback():
    """When adb is nowhere, falls back to 'adb' string."""
    with patch("shutil.which", return_value=None), \
         patch("os.environ.get", return_value=None), \
         patch("os.path.isfile", return_value=False):
        adb = Adb()
        assert adb.adb_path == "adb"


def test_adb_run_success():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "List of devices attached\nemulator-5554\tdevice\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        adb = Adb(adb_path="/usr/bin/adb")
        result = adb.run(["devices"])
        assert result.success is True
        assert "emulator-5554" in result.stdout


def test_adb_run_failure():
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_proc.stderr = "error: no devices"

    with patch("subprocess.run", return_value=mock_proc):
        adb = Adb(adb_path="/usr/bin/adb")
        result = adb.run(["devices"])
        assert result.success is False


def test_adb_run_check_raises():
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_proc.stderr = "error: device offline"

    with patch("subprocess.run", return_value=mock_proc):
        adb = Adb(adb_path="/usr/bin/adb")
        with pytest.raises(AdbError):
            adb.run(["devices"], check=True)


def test_adb_run_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 10)):
        adb = Adb(adb_path="/usr/bin/adb")
        result = adb.run(["shell", "sleep 100"], timeout=10)
        assert result.success is False
        assert "timed out" in result.stderr


def test_adb_serial_in_command():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = ""
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        adb = Adb(serial="emulator-5554", adb_path="/usr/bin/adb")
        adb.run(["devices"])
        cmd = mock_run.call_args[0][0]
        assert cmd == ["/usr/bin/adb", "-s", "emulator-5554", "devices"]


def test_adb_shell_shortcut():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "hello"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        adb = Adb(adb_path="/usr/bin/adb")
        result = adb.shell("echo hello")
        cmd = mock_run.call_args[0][0]
        assert "shell" in cmd
        assert result.stdout == "hello"
