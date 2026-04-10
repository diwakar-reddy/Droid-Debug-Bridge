"""ddb — Droid Debug Bridge CLI.

Usage:
    ddb doctor [--project .]        Validate dependencies (adb, Java, SDK, device)
    ddb devices                     List connected devices
    ddb info                        Device details (model, screen, battery)
    ddb connect <serial>            Set active device

    ddb detect [--project .]        Auto-detect project type (standard/compose/kmp/cmp)
    ddb build [--variant debug]     Build the Android project
    ddb install <apk>               Install APK on device
    ddb uninstall <package>         Uninstall an app
    ddb launch <package> [activity] Launch an app
    ddb stop <package>              Force-stop an app
    ddb clear <package>             Clear app data

    ddb screenshot [path]           Capture screenshot
    ddb uidump [--mode auto]        Dump UI hierarchy as JSON
    ddb compose-tree [--package X]  Dump Compose semantics tree
    ddb find --text "Login"         Find views by text/id/desc/testTag/role
    ddb tap <x> <y>                 Tap coordinates
    ddb tap-view --text "Login"     Find and tap a view
    ddb tap-view --tag "btn_login"  Find by Compose testTag and tap
    ddb swipe <x1> <y1> <x2> <y2>  Swipe gesture
    ddb text "hello"                Type text
    ddb key BACK                    Send key event
    ddb longpress <x> <y>           Long press
    ddb scroll-down                 Scroll down one page
    ddb scroll-up                   Scroll up one page
    ddb wait-for --text "Welcome"   Wait for a view to appear

    ddb logs [--tag X] [--level E]  Filtered logcat
    ddb logs-clear                  Clear logcat
    ddb crash <package>             Get crash logs

    ddb shell "ls /sdcard"          Run adb shell command
    ddb pull <device> <local>       Pull file from device
    ddb push <local> <device>       Push file to device
    ddb perms <package>             List permissions
    ddb grant <package> <perm>      Grant permission
    ddb revoke <package> <perm>     Revoke permission
    ddb prefs <package> [name]      Dump SharedPreferences
    ddb db <pkg> <db> "SELECT ..."  Query SQLite database

    ddb run --project . --package com.example.app   Build+install+launch
    ddb validate steps.json         Run UI test sequence
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from ddb import __version__
from ddb.utils.adb import Adb
from ddb.utils.output import err
from ddb.modules import build, debug, device, doctor, init as init_mod, logs, ui, workflow


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ddb",
        description="Droid Debug Bridge — CLI toolkit for AI-assisted Android development",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"ddb {__version__}"
    )
    parser.add_argument(
        "-s", "--serial", default=None,
        help="Device serial (or set DDB_DEVICE_SERIAL env var)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ---- Doctor / preflight ----
    p = sub.add_parser("doctor", help="Check that all dependencies are met")
    p.add_argument("--project", "-p", default=None, help="Also check project setup")
    p.add_argument("--verbose", action="store_true", help="Show all details")

    # ---- Device management ----
    sub.add_parser("devices", help="List connected devices")
    sub.add_parser("info", help="Device details")
    p = sub.add_parser("connect", help="Set active device")
    p.add_argument("target_serial", help="Device serial number")

    # ---- Project detection ----
    p = sub.add_parser("detect", help="Auto-detect project type (standard/compose/kmp/cmp)")
    p.add_argument("--project", "-p", default=".", help="Project root directory")

    # ---- Build & install ----
    p = sub.add_parser("build", help="Build the Android project")
    p.add_argument("--project", "-p", default=".", help="Project root directory")
    p.add_argument("--variant", "-v", default="debug", choices=["debug", "release"])
    p.add_argument(
        "--module", "-m", default=None,
        help="Gradle module name (auto-detected if omitted)",
    )

    p = sub.add_parser("install", help="Install APK")
    p.add_argument("apk", help="Path to APK file")
    p.add_argument("--no-reinstall", action="store_true")

    p = sub.add_parser("uninstall", help="Uninstall app")
    p.add_argument("package", help="Package name")

    p = sub.add_parser("launch", help="Launch app")
    p.add_argument("package", help="Package name")
    p.add_argument("activity", nargs="?", help="Activity class (optional)")

    p = sub.add_parser("stop", help="Force-stop app")
    p.add_argument("package", help="Package name")

    p = sub.add_parser("clear", help="Clear app data")
    p.add_argument("package", help="Package name")

    # ---- UI ----
    p = sub.add_parser("screenshot", help="Capture screenshot")
    p.add_argument("output", nargs="?", default="screenshot.png", help="Output path")

    p = sub.add_parser("uidump", help="Dump UI hierarchy")
    p.add_argument("--full", action="store_true", help="Include all nodes (no filtering)")
    p.add_argument(
        "--mode", default="auto",
        choices=["auto", "view", "compose", "both"],
        help=(
            "Inspection mode: 'auto' detects Compose and switches, "
            "'view' uses uiautomator, 'compose' uses accessibility tree, "
            "'both' merges results"
        ),
    )

    p = sub.add_parser("compose-tree", help="Dump Compose semantics tree")
    p.add_argument("--package", help="Filter by package name")

    p = sub.add_parser("find", help="Find views by criteria")
    p.add_argument("--text", "-t", help="Match by visible text")
    p.add_argument("--id", "-i", dest="resource_id", help="Match by resource ID")
    p.add_argument("--desc", "-d", dest="content_desc", help="Match by content description")
    p.add_argument("--class", dest="class_name", help="Match by class name")
    p.add_argument("--tag", dest="test_tag", help="Match by Compose testTag")
    p.add_argument("--role", help="Match by Compose semantic role (Button, Checkbox, etc.)")
    p.add_argument(
        "--mode", default="auto", choices=["auto", "view", "compose", "both"],
        help="Inspection mode",
    )

    p = sub.add_parser("tap", help="Tap at coordinates")
    p.add_argument("x", type=int, help="X coordinate")
    p.add_argument("y", type=int, help="Y coordinate")

    p = sub.add_parser("tap-view", help="Find and tap a view")
    p.add_argument("--text", "-t")
    p.add_argument("--id", "-i", dest="resource_id")
    p.add_argument("--desc", "-d", dest="content_desc")
    p.add_argument("--tag", dest="test_tag", help="Compose testTag")
    p.add_argument("--role", help="Compose semantic role")

    p = sub.add_parser("swipe", help="Swipe gesture")
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    p.add_argument("--duration", type=int, default=300, help="Duration in ms")

    p = sub.add_parser("text", help="Type text")
    p.add_argument("content", help="Text to type")

    p = sub.add_parser("key", help="Send key event")
    p.add_argument("keyname", help="Key name (BACK, HOME, ENTER, etc.) or code")

    p = sub.add_parser("longpress", help="Long press at coordinates")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--duration", type=int, default=1000, help="Duration in ms")

    sub.add_parser("scroll-down", help="Scroll down one page")
    sub.add_parser("scroll-up", help="Scroll up one page")

    p = sub.add_parser("wait-for", help="Wait for a view to appear")
    p.add_argument("--text", "-t", help="Match by visible text")
    p.add_argument("--id", "-i", dest="resource_id", help="Match by resource ID")
    p.add_argument("--tag", dest="test_tag", help="Match by Compose testTag")
    p.add_argument("--desc", "-d", dest="content_desc", help="Match by content description")
    p.add_argument("--timeout", type=int, default=10, help="Seconds to wait (default 10)")
    p.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds")

    # ---- Logs ----
    p = sub.add_parser("logs", help="Filtered logcat output")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--level", choices=["V", "D", "I", "W", "E", "F"], help="Minimum level")
    p.add_argument("--package", help="Filter by package name")
    p.add_argument("--lines", "-n", type=int, default=50, help="Number of lines")
    p.add_argument("--grep", "-g", help="Grep pattern")

    sub.add_parser("logs-clear", help="Clear logcat buffer")

    p = sub.add_parser("crash", help="Get crash logs for a package")
    p.add_argument("package", help="Package name")

    # ---- Debug ----
    p = sub.add_parser("shell", help="Run adb shell command")
    p.add_argument("cmd", help="Shell command to run")
    p.add_argument("--timeout", type=int, default=60)

    p = sub.add_parser("pull", help="Pull file from device")
    p.add_argument("device_path", help="Path on device")
    p.add_argument("local_path", help="Local destination path")

    p = sub.add_parser("push", help="Push file to device")
    p.add_argument("local_path", help="Local file path")
    p.add_argument("device_path", help="Destination on device")

    p = sub.add_parser("perms", help="List app permissions")
    p.add_argument("package", help="Package name")

    p = sub.add_parser("grant", help="Grant permission")
    p.add_argument("package", help="Package name")
    p.add_argument("permission", help="Permission name (e.g. CAMERA)")

    p = sub.add_parser("revoke", help="Revoke permission")
    p.add_argument("package", help="Package name")
    p.add_argument("permission", help="Permission name")

    p = sub.add_parser("prefs", help="Dump SharedPreferences")
    p.add_argument("package", help="Package name")
    p.add_argument("name", nargs="?", help="Specific prefs file name")

    p = sub.add_parser("db", help="Query SQLite database")
    p.add_argument("package", help="Package name")
    p.add_argument("db_name", help="Database filename")
    p.add_argument("query", help="SQL query")

    # ---- Init ----
    p = sub.add_parser("init", help="Generate .claude/CLAUDE.md for this project")
    p.add_argument("--project", "-p", default=".", help="Project root directory")
    p.add_argument("--force", "-f", action="store_true", help="Overwrite existing file")

    # ---- Workflows ----
    p = sub.add_parser("run", help="Build + install + launch")
    p.add_argument("--project", "-p", default=".", help="Project root")
    p.add_argument("--package", required=True, help="App package name")
    p.add_argument("--variant", "-v", default="debug")
    p.add_argument("--module", "-m", default=None, help="Gradle module (auto-detected)")
    p.add_argument("--activity", help="Launch activity")
    p.add_argument("--no-clear-logs", action="store_true")

    p = sub.add_parser("validate", help="Run UI test sequence from JSON file")
    p.add_argument("steps_file", help="Path to JSON steps file")

    # ---- Parse and dispatch ----
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    adb = Adb(serial=args.serial)
    _dispatch(args, adb)


def _dispatch(args: argparse.Namespace, adb: Adb) -> None:
    """Route the parsed command to the right module function."""
    cmd = args.command

    # Doctor / preflight
    if cmd == "doctor":
        doctor.doctor(adb, project_dir=args.project, verbose=args.verbose)
        return

    # Auto-preflight: for device-dependent commands, verify adb works first.
    # This catches the "adb not found" case before the user gets a confusing error.
    _OFFLINE_COMMANDS = {"detect", "build", "doctor", "init"}
    if cmd not in _OFFLINE_COMMANDS:
        adb_check = doctor._check_adb_binary(adb)
        if adb_check["status"] == "fail":
            err(
                adb_check["detail"],
                hint=adb_check.get("fix", "Install Android SDK Platform-Tools."),
            )
            return

    # Device
    if cmd == "devices":
        device.devices(adb)
    elif cmd == "info":
        device.info(adb)
    elif cmd == "connect":
        device.connect(args.target_serial)

    # Project detection
    elif cmd == "detect":
        build.detect(args.project)

    # Build & install
    elif cmd == "build":
        build.build(args.project, variant=args.variant, module=args.module)
    elif cmd == "install":
        build.install(adb, args.apk, reinstall=not args.no_reinstall)
    elif cmd == "uninstall":
        build.uninstall(adb, args.package)
    elif cmd == "launch":
        build.launch(adb, args.package, args.activity)
    elif cmd == "stop":
        build.stop(adb, args.package)
    elif cmd == "clear":
        build.clear_data(adb, args.package)

    # UI
    elif cmd == "screenshot":
        ui.screenshot(adb, args.output)
    elif cmd == "uidump":
        ui.uidump(adb, simplify=not args.full, mode=args.mode)
    elif cmd == "compose-tree":
        ui.compose_tree(adb, package=args.package)
    elif cmd == "find":
        ui.find_view(
            adb,
            text=args.text,
            resource_id=args.resource_id,
            class_name=args.class_name,
            content_desc=args.content_desc,
            test_tag=args.test_tag,
            role=args.role,
            mode=args.mode,
        )
    elif cmd == "tap":
        ui.tap(adb, args.x, args.y)
    elif cmd == "tap-view":
        ui.tap_view(
            adb,
            text=args.text,
            resource_id=args.resource_id,
            content_desc=args.content_desc,
            test_tag=args.test_tag,
            role=args.role,
        )
    elif cmd == "swipe":
        ui.swipe(adb, args.x1, args.y1, args.x2, args.y2, args.duration)
    elif cmd == "text":
        ui.input_text(adb, args.content)
    elif cmd == "key":
        ui.keyevent(adb, args.keyname)
    elif cmd == "longpress":
        ui.long_press(adb, args.x, args.y, args.duration)
    elif cmd == "scroll-down":
        ui.scroll_down(adb)
    elif cmd == "scroll-up":
        ui.scroll_up(adb)
    elif cmd == "wait-for":
        ui.wait_for_view(
            adb,
            text=args.text,
            resource_id=args.resource_id,
            test_tag=args.test_tag,
            content_desc=args.content_desc,
            timeout_sec=args.timeout,
            poll_interval=args.interval,
        )

    # Logs
    elif cmd == "logs":
        logs.logs(adb, tag=args.tag, level=args.level, package=args.package, lines=args.lines, grep=args.grep)
    elif cmd == "logs-clear":
        logs.logs_clear(adb)
    elif cmd == "crash":
        logs.crash_log(adb, args.package)

    # Debug
    elif cmd == "shell":
        debug.shell(adb, args.cmd, timeout=args.timeout)
    elif cmd == "pull":
        debug.pull_file(adb, args.device_path, args.local_path)
    elif cmd == "push":
        debug.push_file(adb, args.local_path, args.device_path)
    elif cmd == "perms":
        debug.permissions(adb, args.package)
    elif cmd == "grant":
        debug.grant_permission(adb, args.package, args.permission)
    elif cmd == "revoke":
        debug.revoke_permission(adb, args.package, args.permission)
    elif cmd == "prefs":
        debug.shared_prefs(adb, args.package, args.name)
    elif cmd == "db":
        debug.query_db(adb, args.package, args.db_name, args.query)

    # Init
    elif cmd == "init":
        init_mod.init(args.project, force=args.force)

    # Workflows
    elif cmd == "run":
        workflow.run(
            adb,
            project_dir=args.project,
            package=args.package,
            variant=args.variant,
            module=args.module,
            activity=args.activity,
            clear_logs=not args.no_clear_logs,
        )
    elif cmd == "validate":
        workflow.validate(adb, args.steps_file)

    else:
        err(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
