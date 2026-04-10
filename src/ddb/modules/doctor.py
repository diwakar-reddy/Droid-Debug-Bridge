"""Module 7 — Doctor: preflight dependency validation.

Checks that all tools ddb depends on are installed and configured
correctly before the user runs into a cryptic error mid-workflow.

Usage:
    ddb doctor                   # full check
    ddb doctor --project ./app   # also check Gradle/build setup
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ddb.utils.adb import Adb
from ddb.utils.output import err, ok


# Each check returns a dict with:
#   name: human-readable label
#   status: "ok" | "warn" | "fail"
#   detail: what was found
#   fix: how to fix it (only when status != "ok")

CheckResult = Dict[str, str]


def doctor(
    adb: Adb,
    project_dir: Optional[str] = None,
    verbose: bool = False,
) -> Dict:
    """Run all preflight checks and return a structured health report.

    Checks (in order):
      1. ADB binary found and executable
      2. ADB server running and responsive
      3. Platform-tools version
      4. At least one device/emulator connected
      5. Device is online (not offline/unauthorized)
      6. Java/JDK available (needed for Gradle builds)
      7. ANDROID_HOME / ANDROID_SDK_ROOT set
      8. (optional) Gradle wrapper present in project
      9. (optional) Project is buildable (gradlew permissions)
    """
    checks: List[CheckResult] = []

    # 1 — ADB binary
    checks.append(_check_adb_binary(adb))

    # 2 — ADB server
    checks.append(_check_adb_server(adb))

    # 3 — Platform-tools version
    checks.append(_check_platform_tools_version(adb))

    # 4 + 5 — Device connectivity
    device_check, device_detail_checks = _check_devices(adb)
    checks.append(device_check)
    checks.extend(device_detail_checks)

    # 6 — Java / JDK
    checks.append(_check_java())

    # 7 — ANDROID_HOME
    checks.append(_check_android_home())

    # 8 + 9 — Project-specific (optional)
    if project_dir:
        checks.extend(_check_project(project_dir))

    # Summarize
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    ok_count = sum(1 for c in checks if c["status"] == "ok")
    total = len(checks)

    overall = "healthy"
    if fail_count > 0:
        overall = "unhealthy"
    elif warn_count > 0:
        overall = "degraded"

    data: Dict[str, Any] = {
        "overall": overall,
        "total": total,
        "passed": ok_count,
        "warnings": warn_count,
        "failures": fail_count,
        "checks": checks,
    }

    if fail_count > 0:
        # Surface the first failure's fix as a top-level hint
        first_fail = next(c for c in checks if c["status"] == "fail")
        return ok(
            data,
            message=(
                f"Environment unhealthy: {fail_count} issue(s) found. "
                f"First: {first_fail['name']} — {first_fail.get('fix', 'see details')}"
            ),
        )

    if warn_count > 0:
        return ok(data, message=f"Environment OK with {warn_count} warning(s)")

    return ok(data, message=f"All {total} checks passed — environment is ready")


# ------------------------------------------------------------------
# Individual checks
# ------------------------------------------------------------------

def _check_adb_binary(adb: Adb) -> CheckResult:
    """Check that the adb binary exists and is executable."""
    path = adb.adb_path
    if not path or path == "adb":
        # It's the fallback — check if it's actually on PATH
        found = shutil.which("adb")
        if not found:
            return {
                "name": "ADB binary",
                "status": "fail",
                "detail": "adb not found on PATH or in common SDK locations.",
                "fix": (
                    "Install Android SDK Platform-Tools:\n"
                    "  macOS:  brew install --cask android-platform-tools\n"
                    "  Linux:  sudo apt install android-sdk-platform-tools\n"
                    "  Manual: https://developer.android.com/tools/releases/platform-tools"
                ),
            }
        path = found

    if not os.path.isfile(path):
        return {
            "name": "ADB binary",
            "status": "fail",
            "detail": f"Path '{path}' does not exist.",
            "fix": "Set ADB_PATH env var or install Platform-Tools.",
        }

    if not os.access(path, os.X_OK):
        return {
            "name": "ADB binary",
            "status": "fail",
            "detail": f"'{path}' exists but is not executable.",
            "fix": f"Run: chmod +x {path}",
        }

    return {
        "name": "ADB binary",
        "status": "ok",
        "detail": f"Found at {path}",
    }


def _check_adb_server(adb: Adb) -> CheckResult:
    """Check that adb server is responsive."""
    result = adb.run(["version"], timeout=10)
    if not result.success:
        return {
            "name": "ADB server",
            "status": "fail",
            "detail": f"adb version failed: {result.stderr}",
            "fix": "Try: adb kill-server && adb start-server",
        }

    return {
        "name": "ADB server",
        "status": "ok",
        "detail": result.stdout.splitlines()[0] if result.stdout else "responsive",
    }


def _check_platform_tools_version(adb: Adb) -> CheckResult:
    """Check platform-tools version (need 30+ for modern features)."""
    result = adb.run(["version"], timeout=10)
    if not result.success:
        return {
            "name": "Platform-tools version",
            "status": "warn",
            "detail": "Could not determine version.",
            "fix": "Ensure adb is installed and accessible.",
        }

    # Parse version from "Android Debug Bridge version X.Y.Z"
    version_str = ""
    for line in result.stdout.splitlines():
        if "Version" in line or "version" in line:
            parts = line.strip().split()
            version_str = parts[-1] if parts else ""
            break

    if not version_str:
        return {
            "name": "Platform-tools version",
            "status": "warn",
            "detail": "Could not parse version number.",
        }

    try:
        major = int(version_str.split(".")[0])
    except (ValueError, IndexError):
        return {
            "name": "Platform-tools version",
            "status": "warn",
            "detail": f"Unparseable version: {version_str}",
        }

    if major < 30:
        return {
            "name": "Platform-tools version",
            "status": "warn",
            "detail": f"Version {version_str} — some features require 30+.",
            "fix": (
                "Update Platform-Tools:\n"
                "  macOS:  brew upgrade android-platform-tools\n"
                "  Manual: sdkmanager --update"
            ),
        }

    return {
        "name": "Platform-tools version",
        "status": "ok",
        "detail": f"Version {version_str}",
    }


def _check_devices(adb: Adb) -> tuple:
    """Check that at least one device is connected and online.

    Returns (main_check, [per_device_checks]).
    """
    result = adb.run(["devices", "-l"], timeout=10)
    if not result.success:
        main = {
            "name": "Connected devices",
            "status": "fail",
            "detail": f"Cannot list devices: {result.stderr}",
            "fix": "Ensure adb server is running: adb start-server",
        }
        return main, []

    lines = [l.strip() for l in result.stdout.splitlines()[1:] if l.strip()]
    if not lines:
        main = {
            "name": "Connected devices",
            "status": "fail",
            "detail": "No devices or emulators found.",
            "fix": (
                "Connect a device via USB (enable USB debugging in Developer Options) "
                "or start an emulator: emulator -avd <avd_name>"
            ),
        }
        return main, []

    device_checks: List[CheckResult] = []
    online_count = 0

    for line in lines:
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"

        if state == "device":
            online_count += 1
            device_checks.append({
                "name": f"Device {serial}",
                "status": "ok",
                "detail": f"Online — {' '.join(parts[2:])}",
            })
        elif state == "unauthorized":
            device_checks.append({
                "name": f"Device {serial}",
                "status": "fail",
                "detail": "Unauthorized — USB debugging not approved on device.",
                "fix": (
                    f"On the device, check for the 'Allow USB debugging?' dialog "
                    f"and tap 'Allow'. If it doesn't appear, revoke authorizations: "
                    f"Settings > Developer Options > Revoke USB debugging authorizations, "
                    f"then reconnect."
                ),
            })
        elif state == "offline":
            device_checks.append({
                "name": f"Device {serial}",
                "status": "fail",
                "detail": "Offline — device not responding.",
                "fix": (
                    "Try: adb kill-server && adb start-server\n"
                    "If it's an emulator, restart it.\n"
                    "If USB, unplug and replug the cable."
                ),
            })
        else:
            device_checks.append({
                "name": f"Device {serial}",
                "status": "warn",
                "detail": f"State: {state}",
            })

    if online_count == 0:
        main = {
            "name": "Connected devices",
            "status": "fail",
            "detail": f"Found {len(lines)} device(s) but none are online.",
            "fix": "See per-device details below.",
        }
    else:
        main = {
            "name": "Connected devices",
            "status": "ok",
            "detail": f"{online_count} online device(s)",
        }

    return main, device_checks


def _check_java() -> CheckResult:
    """Check that Java/JDK is available (required for Gradle builds)."""
    java_home = os.environ.get("JAVA_HOME", "")

    # Check java on PATH
    java_path = shutil.which("java")
    if not java_path:
        return {
            "name": "Java / JDK",
            "status": "warn",
            "detail": "java not found on PATH.",
            "fix": (
                "Install a JDK (17+ recommended for modern Android):\n"
                "  macOS:  brew install openjdk@17\n"
                "  Linux:  sudo apt install openjdk-17-jdk\n"
                "  Or set JAVA_HOME to an existing JDK installation."
            ),
        }

    # Get version
    try:
        proc = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # java -version outputs to stderr
        version_output = proc.stderr or proc.stdout
        version_line = version_output.splitlines()[0] if version_output else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        version_line = "unknown"

    detail = f"{version_line}"
    if java_home:
        detail += f" (JAVA_HOME={java_home})"

    return {
        "name": "Java / JDK",
        "status": "ok",
        "detail": detail,
    }


def _check_android_home() -> CheckResult:
    """Check that ANDROID_HOME or ANDROID_SDK_ROOT is set."""
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")

    if not android_home:
        # Check common default locations
        home = os.path.expanduser("~")
        common = [
            os.path.join(home, "Library", "Android", "sdk"),  # macOS
            os.path.join(home, "Android", "Sdk"),             # Linux
        ]
        for c in common:
            if os.path.isdir(c):
                return {
                    "name": "ANDROID_HOME",
                    "status": "warn",
                    "detail": f"Not set, but SDK found at {c}.",
                    "fix": f"Add to your shell profile: export ANDROID_HOME={c}",
                }

        return {
            "name": "ANDROID_HOME",
            "status": "warn",
            "detail": "Not set. Some tools may not locate the SDK.",
            "fix": (
                "Set ANDROID_HOME to your SDK path:\n"
                "  export ANDROID_HOME=$HOME/Library/Android/sdk   # macOS\n"
                "  export ANDROID_HOME=$HOME/Android/Sdk           # Linux"
            ),
        }

    if not os.path.isdir(android_home):
        return {
            "name": "ANDROID_HOME",
            "status": "fail",
            "detail": f"Set to '{android_home}' but directory does not exist.",
            "fix": f"Fix the path or reinstall the Android SDK.",
        }

    # Check for key subdirectories
    missing: List[str] = []
    for subdir in ["platform-tools", "build-tools"]:
        if not os.path.isdir(os.path.join(android_home, subdir)):
            missing.append(subdir)

    if missing:
        return {
            "name": "ANDROID_HOME",
            "status": "warn",
            "detail": f"Set to {android_home} but missing: {', '.join(missing)}.",
            "fix": f"Install missing components: sdkmanager '{' '.join(missing)}'",
        }

    return {
        "name": "ANDROID_HOME",
        "status": "ok",
        "detail": android_home,
    }


def _check_project(project_dir: str) -> List[CheckResult]:
    """Check project-specific requirements (Gradle wrapper, permissions)."""
    checks: List[CheckResult] = []
    project_dir = os.path.abspath(project_dir)

    # Gradle wrapper
    gradlew = os.path.join(project_dir, "gradlew")
    if not os.path.isfile(gradlew):
        checks.append({
            "name": "Gradle wrapper",
            "status": "fail",
            "detail": f"No gradlew in {project_dir}",
            "fix": (
                "Not an Android project root, or Gradle wrapper is missing.\n"
                "Generate with: gradle wrapper --gradle-version 8.5"
            ),
        })
    else:
        if not os.access(gradlew, os.X_OK):
            checks.append({
                "name": "Gradle wrapper",
                "status": "fail",
                "detail": f"gradlew exists but is not executable.",
                "fix": f"Run: chmod +x {gradlew}",
            })
        else:
            checks.append({
                "name": "Gradle wrapper",
                "status": "ok",
                "detail": f"Found at {gradlew}",
            })

    # Check for build.gradle
    has_build = any(
        os.path.isfile(os.path.join(project_dir, f))
        for f in ["build.gradle", "build.gradle.kts"]
    )
    if has_build:
        checks.append({
            "name": "Build file",
            "status": "ok",
            "detail": "build.gradle(.kts) found",
        })
    else:
        checks.append({
            "name": "Build file",
            "status": "fail",
            "detail": "No build.gradle or build.gradle.kts found.",
            "fix": "Make sure --project points to the project root.",
        })

    # Check gradle/wrapper/gradle-wrapper.properties
    wrapper_props = os.path.join(project_dir, "gradle", "wrapper", "gradle-wrapper.properties")
    if os.path.isfile(wrapper_props):
        with open(wrapper_props, "r") as f:
            content = f.read()
        if "distributionUrl" in content:
            # Extract Gradle version
            import re
            m = re.search(r"gradle-(\d+\.\d+(?:\.\d+)?)", content)
            version = m.group(1) if m else "unknown"
            checks.append({
                "name": "Gradle version",
                "status": "ok",
                "detail": f"Gradle {version}",
            })
    else:
        checks.append({
            "name": "Gradle version",
            "status": "warn",
            "detail": "gradle-wrapper.properties not found.",
            "fix": "Run: gradle wrapper",
        })

    return checks
