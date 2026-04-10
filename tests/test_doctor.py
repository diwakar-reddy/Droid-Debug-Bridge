"""Tests for the doctor module — uses mocking, no real device needed."""

import os
import subprocess
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from ddb.utils.adb import Adb, AdbResult
from ddb.modules.doctor import (
    doctor,
    _check_adb_binary,
    _check_adb_server,
    _check_platform_tools_version,
    _check_devices,
    _check_java,
    _check_android_home,
    _check_project,
)


# ------------------------------------------------------------------
# ADB binary check
# ------------------------------------------------------------------

def test_check_adb_binary_found():
    adb = Adb(adb_path="/usr/local/bin/adb")
    with patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True):
        result = _check_adb_binary(adb)
        assert result["status"] == "ok"
        assert "/usr/local/bin/adb" in result["detail"]


def test_check_adb_binary_not_found():
    adb = Adb(adb_path="adb")
    with patch("shutil.which", return_value=None):
        result = _check_adb_binary(adb)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]
        assert "fix" in result


def test_check_adb_binary_not_executable():
    adb = Adb(adb_path="/usr/local/bin/adb")
    with patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=False):
        result = _check_adb_binary(adb)
        assert result["status"] == "fail"
        assert "not executable" in result["detail"]


# ------------------------------------------------------------------
# ADB server check
# ------------------------------------------------------------------

def test_check_adb_server_ok():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(
        success=True,
        stdout="Android Debug Bridge version 35.0.1\nInstalled as /usr/local/bin/adb",
    )
    with patch.object(adb, "run", return_value=mock_result):
        result = _check_adb_server(adb)
        assert result["status"] == "ok"


def test_check_adb_server_fail():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(success=False, stderr="cannot connect to daemon")
    with patch.object(adb, "run", return_value=mock_result):
        result = _check_adb_server(adb)
        assert result["status"] == "fail"
        assert "kill-server" in result["fix"]


# ------------------------------------------------------------------
# Platform-tools version
# ------------------------------------------------------------------

def test_check_platform_tools_modern():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(
        success=True,
        stdout="Android Debug Bridge version 35.0.1",
    )
    with patch.object(adb, "run", return_value=mock_result):
        result = _check_platform_tools_version(adb)
        assert result["status"] == "ok"
        assert "35.0.1" in result["detail"]


def test_check_platform_tools_old():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(
        success=True,
        stdout="Android Debug Bridge version 28.0.2",
    )
    with patch.object(adb, "run", return_value=mock_result):
        result = _check_platform_tools_version(adb)
        assert result["status"] == "warn"


# ------------------------------------------------------------------
# Device connectivity
# ------------------------------------------------------------------

def test_check_devices_one_online():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(
        success=True,
        stdout="List of devices attached\nemulator-5554    device product:sdk model:Pixel_6",
    )
    with patch.object(adb, "run", return_value=mock_result):
        main, details = _check_devices(adb)
        assert main["status"] == "ok"
        assert len(details) == 1
        assert details[0]["status"] == "ok"


def test_check_devices_unauthorized():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(
        success=True,
        stdout="List of devices attached\nHSR234567    unauthorized",
    )
    with patch.object(adb, "run", return_value=mock_result):
        main, details = _check_devices(adb)
        assert main["status"] == "fail"
        assert details[0]["status"] == "fail"
        assert "Allow USB debugging" in details[0]["fix"]


def test_check_devices_none():
    adb = Adb(adb_path="/usr/local/bin/adb")
    mock_result = AdbResult(success=True, stdout="List of devices attached\n")
    with patch.object(adb, "run", return_value=mock_result):
        main, details = _check_devices(adb)
        assert main["status"] == "fail"
        assert "No devices" in main["detail"]


# ------------------------------------------------------------------
# Java
# ------------------------------------------------------------------

def test_check_java_present():
    with patch("shutil.which", return_value="/usr/bin/java"):
        mock_proc = MagicMock()
        mock_proc.stderr = 'openjdk version "17.0.10" 2024-01-16'
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = _check_java()
            assert result["status"] == "ok"
            assert "17" in result["detail"]


def test_check_java_missing():
    with patch("shutil.which", return_value=None):
        result = _check_java()
        assert result["status"] == "warn"
        assert "not found" in result["detail"]


# ------------------------------------------------------------------
# ANDROID_HOME
# ------------------------------------------------------------------

def test_check_android_home_set():
    with patch.dict(os.environ, {"ANDROID_HOME": "/opt/android-sdk"}), \
         patch("os.path.isdir", return_value=True):
        result = _check_android_home()
        assert result["status"] == "ok"


def test_check_android_home_not_set():
    with patch.dict(os.environ, {}, clear=True), \
         patch("os.path.isdir", return_value=False):
        result = _check_android_home()
        assert result["status"] == "warn"


# ------------------------------------------------------------------
# Project checks
# ------------------------------------------------------------------

def test_check_project_good(tmp_path):
    # Create a minimal project structure
    gradlew = tmp_path / "gradlew"
    gradlew.touch()
    gradlew.chmod(0o755)
    (tmp_path / "build.gradle.kts").write_text('plugins { id("com.android.application") }')

    wrapper_dir = tmp_path / "gradle" / "wrapper"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://gradle-8.5-bin.zip"
    )

    checks = _check_project(str(tmp_path))
    statuses = {c["name"]: c["status"] for c in checks}
    assert statuses["Gradle wrapper"] == "ok"
    assert statuses["Build file"] == "ok"
    assert statuses["Gradle version"] == "ok"


def test_check_project_missing_gradlew(tmp_path):
    (tmp_path / "build.gradle").write_text("apply plugin: 'com.android.application'")
    checks = _check_project(str(tmp_path))
    gradlew_check = next(c for c in checks if c["name"] == "Gradle wrapper")
    assert gradlew_check["status"] == "fail"


# ------------------------------------------------------------------
# Full doctor
# ------------------------------------------------------------------

def test_doctor_full_pass(capsys):
    """Full doctor run with everything mocked as healthy."""
    adb = Adb(adb_path="/usr/local/bin/adb")

    version_result = AdbResult(
        success=True,
        stdout="Android Debug Bridge version 35.0.1",
    )
    devices_result = AdbResult(
        success=True,
        stdout="List of devices attached\nemulator-5554    device",
    )

    def mock_run(args, **kwargs):
        if args == ["version"]:
            return version_result
        if args == ["devices", "-l"]:
            return devices_result
        return AdbResult(success=True)

    with patch.object(adb, "run", side_effect=mock_run), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True), \
         patch("shutil.which", return_value="/usr/bin/java"), \
         patch("subprocess.run", return_value=MagicMock(stderr='openjdk version "17"', stdout="")), \
         patch.dict(os.environ, {"ANDROID_HOME": "/opt/sdk"}), \
         patch("os.path.isdir", return_value=True):

        result = doctor(adb)
        assert result["data"]["overall"] == "healthy"
        assert result["data"]["failures"] == 0
