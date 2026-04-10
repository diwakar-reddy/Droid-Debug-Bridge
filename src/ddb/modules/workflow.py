"""Module 6 — Workflow shortcuts: compound commands for common dev loops."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from ddb.utils.adb import Adb
from ddb.utils.output import err, ok
from ddb.modules import build as build_mod
from ddb.modules import ui as ui_mod
from ddb.modules import logs as logs_mod


def run(
    adb: Adb,
    project_dir: str,
    package: str,
    variant: str = "debug",
    module: Optional[str] = None,
    activity: Optional[str] = None,
    clear_logs: bool = True,
) -> Dict:
    """Build, install, and launch in one command.

    This is the main developer loop: build -> install -> clear logs -> launch.
    Auto-detects project type (standard/Compose/KMP/CMP) and the correct
    module if not specified.

    Returns results from each step.
    """
    steps: List[Dict[str, Any]] = []

    # Step 1: Build (auto-detects module for KMP/CMP if not specified)
    build_result = build_mod.build(project_dir, variant=variant, module=module)
    steps.append({"step": "build", "result": build_result})
    if not build_result.get("success"):
        return ok({"steps": steps, "completed": False}, message="Build failed — stopping.")

    apk_path = build_result["data"]["apk_path"]

    # Step 2: Install
    install_result = build_mod.install(adb, apk_path)
    steps.append({"step": "install", "result": install_result})
    if not install_result.get("success"):
        return ok({"steps": steps, "completed": False}, message="Install failed — stopping.")

    # Step 3: Clear logs
    if clear_logs:
        logs_mod.logs_clear(adb)
        steps.append({"step": "clear_logs", "result": {"success": True}})

    # Step 4: Launch
    launch_result = build_mod.launch(adb, package, activity)
    steps.append({"step": "launch", "result": launch_result})

    all_ok = all(s["result"].get("success", False) for s in steps)
    return ok(
        {"steps": steps, "completed": all_ok},
        message="App built, installed, and launched!" if all_ok else "Completed with errors.",
    )


def validate(adb: Adb, steps_file: str) -> Dict:
    """Run a JSON-defined UI test sequence.

    The steps file is a JSON array of actions:

    [
        {"action": "wait", "seconds": 2},
        {"action": "screenshot", "name": "initial"},
        {"action": "tap", "x": 540, "y": 960},
        {"action": "tap_view", "text": "Login"},
        {"action": "tap_view", "test_tag": "btn_login"},
        {"action": "type", "text": "hello@example.com"},
        {"action": "keyevent", "key": "ENTER"},
        {"action": "wait", "seconds": 1},
        {"action": "wait_for", "text": "Welcome", "timeout": 5},
        {"action": "assert_visible", "text": "Welcome"},
        {"action": "assert_visible", "test_tag": "welcome_screen"},
        {"action": "screenshot", "name": "after_login"},
        {"action": "scroll_down"},
        {"action": "logs", "tag": "MyApp", "lines": 10}
    ]
    """
    if not os.path.isfile(steps_file):
        return err(f"Steps file not found: {steps_file}")

    with open(steps_file, "r") as f:
        try:
            steps = json.load(f)
        except json.JSONDecodeError as e:
            return err(f"Invalid JSON in steps file: {e}")

    if not isinstance(steps, list):
        return err("Steps file must contain a JSON array.")

    results: List[Dict[str, Any]] = []
    screenshot_dir = os.path.dirname(os.path.abspath(steps_file))

    for i, step in enumerate(steps):
        action = step.get("action", "")
        step_result: Dict[str, Any] = {"step": i, "action": action}

        try:
            if action == "wait":
                time.sleep(step.get("seconds", 1))
                step_result["result"] = {"success": True}

            elif action == "screenshot":
                name = step.get("name", f"step_{i}")
                path = os.path.join(screenshot_dir, f"{name}.png")
                step_result["result"] = ui_mod.screenshot(adb, path)

            elif action == "tap":
                step_result["result"] = ui_mod.tap(adb, step["x"], step["y"])

            elif action == "tap_view":
                step_result["result"] = ui_mod.tap_view(
                    adb,
                    text=step.get("text"),
                    resource_id=step.get("resource_id"),
                    content_desc=step.get("content_desc"),
                    test_tag=step.get("test_tag"),
                    role=step.get("role"),
                )

            elif action == "type":
                step_result["result"] = ui_mod.input_text(adb, step["text"])

            elif action == "keyevent":
                step_result["result"] = ui_mod.keyevent(adb, step["key"])

            elif action == "swipe":
                step_result["result"] = ui_mod.swipe(
                    adb, step["x1"], step["y1"], step["x2"], step["y2"],
                    step.get("duration_ms", 300),
                )

            elif action == "scroll_down":
                step_result["result"] = ui_mod.scroll_down(adb)

            elif action == "scroll_up":
                step_result["result"] = ui_mod.scroll_up(adb)

            elif action == "wait_for":
                step_result["result"] = ui_mod.wait_for_view(
                    adb,
                    text=step.get("text"),
                    resource_id=step.get("resource_id"),
                    test_tag=step.get("test_tag"),
                    content_desc=step.get("content_desc"),
                    timeout_sec=step.get("timeout", 10),
                )

            elif action == "assert_visible":
                found = ui_mod.find_view(
                    adb,
                    text=step.get("text"),
                    resource_id=step.get("resource_id"),
                    content_desc=step.get("content_desc"),
                    test_tag=step.get("test_tag"),
                    role=step.get("role"),
                )
                if found.get("success"):
                    step_result["result"] = {"success": True, "message": "View found"}
                else:
                    step_result["result"] = {
                        "success": False,
                        "error": f"Assertion failed: view not found",
                    }

            elif action == "logs":
                step_result["result"] = logs_mod.logs(
                    adb,
                    tag=step.get("tag"),
                    level=step.get("level"),
                    lines=step.get("lines", 20),
                )

            else:
                step_result["result"] = {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            step_result["result"] = {"success": False, "error": str(e)}

        results.append(step_result)

        # Stop on assertion failure unless told to continue
        if (
            action == "assert_visible"
            and not step_result["result"].get("success")
            and not step.get("continue_on_fail")
        ):
            return ok(
                {"steps": results, "completed": False, "failed_at": i},
                message=f"Validation failed at step {i}: {action}",
            )

    return ok(
        {"steps": results, "completed": True},
        message=f"Validation passed: {len(results)} step(s) completed",
    )
