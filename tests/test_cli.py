"""Tests for the CLI argument parsing and dispatch."""

from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# Device commands
# ---------------------------------------------------------------------------


def test_devices_dispatch(capsys):
    """Verify 'ddb devices' routes to device.devices()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockCliAdb, patch(
        "ddb.modules.device.devices"
    ) as mock_devices:
        mock_adb = MagicMock()
        MockCliAdb.return_value = mock_adb
        mock_devices.return_value = {"success": True}
        main(["devices"])
        mock_devices.assert_called_once()


def test_info_dispatch():
    """Verify 'ddb info' routes to device.info()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb"), patch(
        "ddb.modules.device.info"
    ) as mock_info:
        mock_info.return_value = {"success": True}
        main(["info"])
        mock_info.assert_called_once()


def test_connect_dispatch():
    """Verify 'ddb connect <serial>' routes to device.connect()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb"), patch(
        "ddb.modules.device.connect"
    ) as mock_connect:
        mock_connect.return_value = {"success": True}
        main(["connect", "emulator-5554"])
        mock_connect.assert_called_once_with("emulator-5554")


# ---------------------------------------------------------------------------
# Build commands
# ---------------------------------------------------------------------------


def test_detect_dispatch():
    """Verify 'ddb detect' routes to build.detect() (offline, no preflight)."""
    with patch("ddb.cli.Adb"), patch("ddb.modules.build.detect") as mock_detect:
        mock_detect.return_value = {"success": True}
        main(["detect", "--project", "/tmp/proj"])
        mock_detect.assert_called_once_with("/tmp/proj")


def test_build_dispatch():
    """Verify 'ddb build' routes to build.build() (offline, no preflight)."""
    with patch("ddb.cli.Adb"), patch("ddb.modules.build.build") as mock_build:
        mock_build.return_value = {"success": True}
        main(["build", "--project", "/tmp/proj", "--variant", "release", "--module", "app"])
        mock_build.assert_called_once_with("/tmp/proj", variant="release", module="app")


def test_install_dispatch():
    """Verify 'ddb install <apk>' routes to build.install()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.install"
    ) as mock_install:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_install.return_value = {"success": True}
        main(["install", "app.apk"])
        mock_install.assert_called_once_with(mock_adb, "app.apk", reinstall=True)


def test_uninstall_dispatch():
    """Verify 'ddb uninstall <package>' routes to build.uninstall()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.uninstall"
    ) as mock_uninstall:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_uninstall.return_value = {"success": True}
        main(["uninstall", "com.example.app"])
        mock_uninstall.assert_called_once_with(mock_adb, "com.example.app")


def test_launch_dispatch():
    """Verify 'ddb launch <package> [activity]' routes to build.launch()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.launch"
    ) as mock_launch:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_launch.return_value = {"success": True}
        main(["launch", "com.example.app", ".MainActivity"])
        mock_launch.assert_called_once_with(mock_adb, "com.example.app", ".MainActivity")


def test_stop_dispatch():
    """Verify 'ddb stop <package>' routes to build.stop()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.stop"
    ) as mock_stop:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_stop.return_value = {"success": True}
        main(["stop", "com.example.app"])
        mock_stop.assert_called_once_with(mock_adb, "com.example.app")


def test_clear_dispatch():
    """Verify 'ddb clear <package>' routes to build.clear_data()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.clear_data"
    ) as mock_clear:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_clear.return_value = {"success": True}
        main(["clear", "com.example.app"])
        mock_clear.assert_called_once_with(mock_adb, "com.example.app")


# ---------------------------------------------------------------------------
# UI commands
# ---------------------------------------------------------------------------


def test_screenshot_dispatch():
    """Verify 'ddb screenshot [path]' routes to ui.screenshot()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.screenshot"
    ) as mock_screenshot:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_screenshot.return_value = {"success": True}
        main(["screenshot", "out.png"])
        mock_screenshot.assert_called_once_with(mock_adb, "out.png")


def test_uidump_dispatch():
    """Verify 'ddb uidump' routes to ui.uidump()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.uidump"
    ) as mock_uidump:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_uidump.return_value = {"success": True}
        main(["uidump", "--mode", "compose"])
        mock_uidump.assert_called_once_with(mock_adb, simplify=True, mode="compose")


def test_compose_tree_dispatch():
    """Verify 'ddb compose-tree' routes to ui.compose_tree()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.compose_tree"
    ) as mock_ct:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_ct.return_value = {"success": True}
        main(["compose-tree", "--package", "com.example.app"])
        mock_ct.assert_called_once_with(mock_adb, package="com.example.app")


def test_find_dispatch():
    """Verify 'ddb find --tag btn' routes to ui.find_view()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.find_view"
    ) as mock_find:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_find.return_value = {"success": True}
        main(["find", "--tag", "btn_login", "--role", "Button"])
        mock_find.assert_called_once_with(
            mock_adb,
            text=None,
            resource_id=None,
            class_name=None,
            content_desc=None,
            test_tag="btn_login",
            role="Button",
            mode="auto",
        )


def test_tap_dispatch():
    """Verify 'ddb tap 100 200' routes correctly."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.tap"
    ) as mock_tap:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_tap.return_value = {"success": True}
        main(["tap", "100", "200"])
        mock_tap.assert_called_once()
        args = mock_tap.call_args
        assert args[0][1] == 100  # x
        assert args[0][2] == 200  # y


def test_tap_view_dispatch():
    """Verify 'ddb tap-view --tag btn' routes to ui.tap_view()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.tap_view"
    ) as mock_tap_view:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_tap_view.return_value = {"success": True}
        main(["tap-view", "--tag", "btn_submit"])
        mock_tap_view.assert_called_once_with(
            mock_adb,
            text=None,
            resource_id=None,
            content_desc=None,
            test_tag="btn_submit",
            role=None,
        )


def test_swipe_dispatch():
    """Verify 'ddb swipe x1 y1 x2 y2' routes to ui.swipe()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.swipe"
    ) as mock_swipe:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_swipe.return_value = {"success": True}
        main(["swipe", "100", "200", "300", "400", "--duration", "500"])
        mock_swipe.assert_called_once_with(mock_adb, 100, 200, 300, 400, 500)


def test_text_dispatch():
    """Verify 'ddb text "hello"' routes to ui.input_text()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.input_text"
    ) as mock_text:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_text.return_value = {"success": True}
        main(["text", "hello world"])
        mock_text.assert_called_once_with(mock_adb, "hello world")


def test_key_dispatch():
    """Verify 'ddb key ENTER' routes to ui.keyevent()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.keyevent"
    ) as mock_key:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_key.return_value = {"success": True}
        main(["key", "ENTER"])
        mock_key.assert_called_once_with(mock_adb, "ENTER")


def test_longpress_dispatch():
    """Verify 'ddb longpress x y' routes to ui.long_press()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.long_press"
    ) as mock_lp:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_lp.return_value = {"success": True}
        main(["longpress", "540", "1200", "--duration", "2000"])
        mock_lp.assert_called_once_with(mock_adb, 540, 1200, 2000)


def test_scroll_down_dispatch():
    """Verify 'ddb scroll-down' routes to ui.scroll_down()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.scroll_down"
    ) as mock_sd:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_sd.return_value = {"success": True}
        main(["scroll-down"])
        mock_sd.assert_called_once_with(mock_adb)


def test_scroll_up_dispatch():
    """Verify 'ddb scroll-up' routes to ui.scroll_up()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.scroll_up"
    ) as mock_su:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_su.return_value = {"success": True}
        main(["scroll-up"])
        mock_su.assert_called_once_with(mock_adb)


def test_wait_for_dispatch():
    """Verify 'ddb wait-for --tag screen' routes to ui.wait_for_view()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.wait_for_view"
    ) as mock_wf:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_wf.return_value = {"success": True}
        main(["wait-for", "--tag", "home_screen", "--timeout", "5"])
        mock_wf.assert_called_once_with(
            mock_adb,
            text=None,
            resource_id=None,
            test_tag="home_screen",
            content_desc=None,
            timeout_sec=5,
            poll_interval=1.0,
        )


# ---------------------------------------------------------------------------
# Logs commands
# ---------------------------------------------------------------------------


def test_logs_dispatch():
    """Verify 'ddb logs --tag X --level E' routes to logs.logs()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.logs.logs"
    ) as mock_logs:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_logs.return_value = {"success": True}
        main(["logs", "--tag", "MyApp", "--level", "E", "--lines", "30"])
        mock_logs.assert_called_once_with(
            mock_adb,
            tag="MyApp",
            level="E",
            package=None,
            lines=30,
            grep=None,
        )


def test_logs_clear_dispatch():
    """Verify 'ddb logs-clear' routes to logs.logs_clear()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.logs.logs_clear"
    ) as mock_lc:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_lc.return_value = {"success": True}
        main(["logs-clear"])
        mock_lc.assert_called_once_with(mock_adb)


def test_crash_dispatch():
    """Verify 'ddb crash <package>' routes to logs.crash_log()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.logs.crash_log"
    ) as mock_crash:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_crash.return_value = {"success": True}
        main(["crash", "com.example.app"])
        mock_crash.assert_called_once_with(mock_adb, "com.example.app")


# ---------------------------------------------------------------------------
# Debug commands
# ---------------------------------------------------------------------------


def test_shell_dispatch():
    """Verify 'ddb shell "ls"' routes to debug.shell()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.shell"
    ) as mock_shell:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_shell.return_value = {"success": True}
        main(["shell", "ls /sdcard"])
        mock_shell.assert_called_once_with(mock_adb, "ls /sdcard", timeout=60)


def test_pull_dispatch():
    """Verify 'ddb pull <device> <local>' routes to debug.pull_file()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.pull_file"
    ) as mock_pull:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_pull.return_value = {"success": True}
        main(["pull", "/sdcard/file.txt", "./file.txt"])
        mock_pull.assert_called_once_with(mock_adb, "/sdcard/file.txt", "./file.txt")


def test_push_dispatch():
    """Verify 'ddb push <local> <device>' routes to debug.push_file()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.push_file"
    ) as mock_push:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_push.return_value = {"success": True}
        main(["push", "./file.txt", "/sdcard/file.txt"])
        mock_push.assert_called_once_with(mock_adb, "./file.txt", "/sdcard/file.txt")


def test_perms_dispatch():
    """Verify 'ddb perms <package>' routes to debug.permissions()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.permissions"
    ) as mock_perms:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_perms.return_value = {"success": True}
        main(["perms", "com.example.app"])
        mock_perms.assert_called_once_with(mock_adb, "com.example.app")


def test_grant_dispatch():
    """Verify 'ddb grant <package> <perm>' routes to debug.grant_permission()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.grant_permission"
    ) as mock_grant:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_grant.return_value = {"success": True}
        main(["grant", "com.example.app", "CAMERA"])
        mock_grant.assert_called_once_with(mock_adb, "com.example.app", "CAMERA")


def test_revoke_dispatch():
    """Verify 'ddb revoke <package> <perm>' routes to debug.revoke_permission()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.revoke_permission"
    ) as mock_revoke:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_revoke.return_value = {"success": True}
        main(["revoke", "com.example.app", "LOCATION"])
        mock_revoke.assert_called_once_with(mock_adb, "com.example.app", "LOCATION")


def test_prefs_dispatch():
    """Verify 'ddb prefs <package> [name]' routes to debug.shared_prefs()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.shared_prefs"
    ) as mock_prefs:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_prefs.return_value = {"success": True}
        main(["prefs", "com.example.app", "my_prefs"])
        mock_prefs.assert_called_once_with(mock_adb, "com.example.app", "my_prefs")


def test_db_dispatch():
    """Verify 'ddb db <pkg> <db> <query>' routes to debug.query_db()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.debug.query_db"
    ) as mock_db:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_db.return_value = {"success": True}
        main(["db", "com.example.app", "app.db", "SELECT * FROM users"])
        mock_db.assert_called_once_with(
            mock_adb,
            "com.example.app",
            "app.db",
            "SELECT * FROM users",
        )


# ---------------------------------------------------------------------------
# Workflow commands
# ---------------------------------------------------------------------------


def test_run_dispatch():
    """Verify 'ddb run' routes to workflow.run()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.workflow.run"
    ) as mock_run:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_run.return_value = {"success": True}
        main(["run", "--project", ".", "--package", "com.example.app"])
        mock_run.assert_called_once_with(
            mock_adb,
            project_dir=".",
            package="com.example.app",
            variant="debug",
            module=None,
            activity=None,
            clear_logs=True,
        )


def test_validate_dispatch():
    """Verify 'ddb validate steps.json' routes to workflow.validate()."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.workflow.validate"
    ) as mock_validate:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_validate.return_value = {"success": True}
        main(["validate", "steps.json"])
        mock_validate.assert_called_once_with(mock_adb, "steps.json")


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------


def test_init_dispatch():
    """Verify 'ddb init' routes to init.init() (offline, no preflight)."""
    with patch("ddb.cli.Adb"), patch("ddb.modules.init.init") as mock_init:
        mock_init.return_value = {"success": True}
        main(["init", "--project", "/tmp/proj", "--force"])
        mock_init.assert_called_once_with("/tmp/proj", force=True)


# ---------------------------------------------------------------------------
# Doctor command
# ---------------------------------------------------------------------------


def test_doctor_dispatch(capsys):
    """Verify 'ddb doctor' routes to doctor.doctor()."""
    with patch("ddb.cli.Adb"), patch("ddb.modules.doctor.doctor") as mock_doctor:
        mock_doctor.return_value = {"success": True, "data": {"overall": "healthy"}}
        main(["doctor"])
        mock_doctor.assert_called_once()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_serial_flag_passed_to_adb():
    """Verify '-s emulator-5554' is forwarded to the Adb constructor."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.device.devices"
    ) as mock_devices:
        mock_devices.return_value = {"success": True}
        main(["-s", "emulator-5554", "devices"])
        MockAdb.assert_called_once_with(serial="emulator-5554")


def test_screenshot_default_path():
    """Verify screenshot uses 'screenshot.png' when no path is given."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.ui.screenshot"
    ) as mock_screenshot:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_screenshot.return_value = {"success": True}
        main(["screenshot"])
        mock_screenshot.assert_called_once_with(mock_adb, "screenshot.png")


def test_build_defaults():
    """Verify build uses defaults when no flags are given."""
    with patch("ddb.cli.Adb"), patch("ddb.modules.build.build") as mock_build:
        mock_build.return_value = {"success": True}
        main(["build"])
        mock_build.assert_called_once_with(".", variant="debug", module=None)


def test_launch_without_activity():
    """Verify launch works with just package name (no activity)."""
    with _mock_preflight_pass(), patch("ddb.cli.Adb") as MockAdb, patch(
        "ddb.modules.build.launch"
    ) as mock_launch:
        mock_adb = MagicMock()
        MockAdb.return_value = mock_adb
        mock_launch.return_value = {"success": True}
        main(["launch", "com.example.app"])
        mock_launch.assert_called_once_with(mock_adb, "com.example.app", None)
