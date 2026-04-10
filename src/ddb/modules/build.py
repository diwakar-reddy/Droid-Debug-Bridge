"""Module 2 — Build, install, launch, and manage Android apps.

Supports standard Android, Jetpack Compose, KMP, and CMP project layouts.
"""

from __future__ import annotations

import glob
import os
import subprocess
from typing import Dict, List, Optional, Tuple

from ddb.utils.adb import Adb, AdbError
from ddb.utils.output import err, ok
from ddb.utils.parser import detect_project_type


# ------------------------------------------------------------------
# Project Detection
# ------------------------------------------------------------------

def detect(project_dir: str) -> Dict:
    """Auto-detect project type, module layout, and build configuration.

    Scans the project root for build.gradle(.kts), settings.gradle(.kts),
    and common KMP/CMP module directories.

    Returns structured info about what type of project this is and
    which modules contain the Android target.
    """
    project_dir = os.path.abspath(project_dir)

    # Find root build file
    root_build = _find_build_file(project_dir)
    if not root_build:
        return err(
            f"No build.gradle(.kts) found in {project_dir}",
            hint="Make sure you're in the root of an Android/KMP/CMP project.",
        )

    # Read and analyze root build
    with open(root_build, "r") as f:
        root_content = f.read()

    project_info = detect_project_type(root_content)

    # Find settings.gradle to get all modules
    settings_file = _find_settings_file(project_dir)
    modules = _extract_modules(settings_file) if settings_file else []

    # Auto-detect the Android app module
    android_module = _find_android_module(project_dir, modules, project_info)

    # Find the package name from the module's build file
    package_name = None
    if android_module:
        module_build = _find_build_file(os.path.join(project_dir, android_module))
        if module_build:
            with open(module_build, "r") as f:
                package_name = _extract_package_name(f.read())

    # Also try AndroidManifest.xml
    if not package_name and android_module:
        package_name = _find_package_in_manifest(project_dir, android_module)

    project_info.update({
        "project_dir": project_dir,
        "root_build_file": root_build,
        "modules": modules,
        "android_module": android_module,
        "package_name": package_name,
    })

    return ok(project_info, message=f"Detected {project_info['type']} project")


def build(
    project_dir: str,
    variant: str = "debug",
    module: Optional[str] = None,
    auto_detect: bool = True,
) -> Dict:
    """Build the Android target and return the APK path.

    For standard projects:  :app:assembleDebug
    For KMP/CMP projects:   :composeApp:assembleDebug or :androidApp:assembleDebug

    Args:
        project_dir: Root of the Android/KMP/CMP project (contains gradlew).
        variant: 'debug' or 'release'.
        module: Gradle module name. If None, auto-detects.
        auto_detect: If True (default), detect project type and find the right module.
    """
    project_dir = os.path.abspath(project_dir)
    gradlew = os.path.join(project_dir, "gradlew")
    if not os.path.isfile(gradlew):
        return err(
            f"No gradlew found in {project_dir}",
            hint="Make sure you're in the root of an Android/KMP/CMP project.",
        )

    # Auto-detect module if not specified
    if not module and auto_detect:
        detection = detect(project_dir)
        if detection.get("success") and detection.get("data", {}).get("android_module"):
            module = detection["data"]["android_module"]
            project_type = detection["data"]["type"]
        else:
            module = "app"  # Fallback
            project_type = "standard"
    else:
        module = module or "app"
        project_type = "standard"

    task = f":{module}:assemble{variant.capitalize()}"

    try:
        proc = subprocess.run(
            [gradlew, task, "--no-daemon"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return err("Build timed out after 10 minutes.")

    if proc.returncode != 0:
        error_lines = _extract_build_errors(proc.stderr or proc.stdout)
        return err(
            "Build failed.",
            hint=error_lines or (proc.stderr[-2000:] if proc.stderr else proc.stdout[-2000:]),
        )

    # Find the APK — search multiple possible locations for KMP/CMP
    apk_path = _find_apk(project_dir, module, variant)
    if not apk_path:
        return err(
            "Build succeeded but APK not found.",
            hint=(
                f"Expected in {module}/build/outputs/apk/{variant}/. "
                f"For KMP/CMP, check if the Android module name is correct (detected: {module})."
            ),
        )

    return ok(
        {
            "apk_path": apk_path,
            "variant": variant,
            "module": module,
            "project_type": project_type,
        },
        message=f"Build successful: {os.path.basename(apk_path)}",
    )


def install(adb: Adb, apk_path: str, reinstall: bool = True) -> Dict:
    """Install an APK on the active device.

    Args:
        adb: Adb instance targeting a device.
        apk_path: Path to the .apk file.
        reinstall: If True, pass -r to allow reinstall.
    """
    if not os.path.isfile(apk_path):
        return err(f"APK not found: {apk_path}")

    args = ["install"]
    if reinstall:
        args.append("-r")
    args.append(apk_path)

    result = adb.run(args, timeout=120)
    if not result.success or "Failure" in result.stdout:
        failure_reason = result.stdout if "Failure" in result.stdout else result.stderr
        return err(f"Install failed: {failure_reason}")

    return ok(
        {"apk": os.path.basename(apk_path)},
        message="APK installed successfully.",
    )


def uninstall(adb: Adb, package: str) -> Dict:
    """Uninstall an app by package name."""
    result = adb.run(["uninstall", package], timeout=30)
    if not result.success:
        return err(f"Uninstall failed: {result.stderr}")
    return ok({"package": package}, message=f"Uninstalled {package}")


def launch(adb: Adb, package: str, activity: Optional[str] = None) -> Dict:
    """Launch an app. If no activity given, uses the launcher activity."""
    if activity:
        component = f"{package}/{activity}"
        result = adb.shell(f"am start -n {component}")
    else:
        # Use monkey to launch the default activity
        result = adb.shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )

    if not result.success:
        return err(f"Failed to launch: {result.stderr}")

    return ok({"package": package}, message=f"Launched {package}")


def stop(adb: Adb, package: str) -> Dict:
    """Force-stop an app."""
    result = adb.shell(f"am force-stop {package}")
    if not result.success:
        return err(f"Failed to stop {package}: {result.stderr}")
    return ok({"package": package}, message=f"Stopped {package}")


def clear_data(adb: Adb, package: str) -> Dict:
    """Clear all app data (like a fresh install)."""
    result = adb.shell(f"pm clear {package}")
    if not result.success or "Exception" in result.stdout:
        return err(f"Failed to clear data: {result.stdout} {result.stderr}")
    return ok({"package": package}, message=f"Cleared data for {package}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _find_build_file(directory: str) -> Optional[str]:
    """Find build.gradle or build.gradle.kts in a directory."""
    for name in ["build.gradle.kts", "build.gradle"]:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path
    return None


def _find_settings_file(directory: str) -> Optional[str]:
    """Find settings.gradle(.kts) in a directory."""
    for name in ["settings.gradle.kts", "settings.gradle"]:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path
    return None


def _extract_modules(settings_file: str) -> List[str]:
    """Extract included module names from settings.gradle(.kts)."""
    modules: List[str] = []
    with open(settings_file, "r") as f:
        content = f.read()

    # Match include(":app"), include(":composeApp"), etc.
    import re
    for m in re.finditer(r'include\s*\(\s*"([^"]+)"\s*\)', content):
        mod = m.group(1).lstrip(":")
        modules.append(mod)
    # Also match: include ':app', ':shared'
    for m in re.finditer(r"include\s+['\"]([^'\"]+)['\"]", content):
        for part in m.group(1).split(","):
            mod = part.strip().strip("'\"").lstrip(":")
            if mod and mod not in modules:
                modules.append(mod)

    return modules


def _find_android_module(
    project_dir: str,
    modules: List[str],
    project_info: Dict,
) -> Optional[str]:
    """Determine which module is the Android app module.

    Priority:
    1. composeApp (CMP convention)
    2. androidApp (KMP convention)
    3. app (standard Android convention)
    4. First module with an AndroidManifest.xml
    """
    project_type = project_info.get("type", "standard")

    # CMP projects typically use 'composeApp'
    if project_type == "cmp" and "composeApp" in modules:
        return "composeApp"

    # KMP projects typically use 'androidApp'
    if project_type in ("kmp", "cmp") and "androidApp" in modules:
        return "androidApp"

    # Standard default
    if "app" in modules or not modules:
        return "app"

    # Search for module with AndroidManifest.xml
    for mod in modules:
        manifest_paths = [
            os.path.join(project_dir, mod, "src", "main", "AndroidManifest.xml"),
            os.path.join(project_dir, mod, "src", "androidMain", "AndroidManifest.xml"),
        ]
        for mp in manifest_paths:
            if os.path.isfile(mp):
                return mod

    return modules[0] if modules else "app"


def _extract_package_name(build_content: str) -> Optional[str]:
    """Extract applicationId / namespace from a module's build.gradle(.kts)."""
    import re

    # applicationId "com.example.app"
    m = re.search(r'applicationId\s*[=\s]+["\']([^"\']+)["\']', build_content)
    if m:
        return m.group(1)

    # namespace "com.example.app"  (AGP 8+ / CMP)
    m = re.search(r'namespace\s*[=\s]+["\']([^"\']+)["\']', build_content)
    if m:
        return m.group(1)

    return None


def _find_package_in_manifest(project_dir: str, module: str) -> Optional[str]:
    """Extract package from AndroidManifest.xml."""
    import re

    manifest_paths = [
        os.path.join(project_dir, module, "src", "main", "AndroidManifest.xml"),
        os.path.join(project_dir, module, "src", "androidMain", "AndroidManifest.xml"),
    ]

    for mp in manifest_paths:
        if os.path.isfile(mp):
            with open(mp, "r") as f:
                content = f.read()
            m = re.search(r'package\s*=\s*"([^"]+)"', content)
            if m:
                return m.group(1)
    return None


def _find_apk(project_dir: str, module: str, variant: str) -> Optional[str]:
    """Locate the built APK file — searches standard and KMP/CMP output paths."""
    patterns = [
        # Standard Android
        os.path.join(project_dir, module, "build", "outputs", "apk", variant, "*.apk"),
        os.path.join(project_dir, module, "build", "outputs", "apk", f"*-{variant}.apk"),
        # KMP/CMP (sometimes nested differently)
        os.path.join(project_dir, module, "build", "outputs", "apk", "android", variant, "*.apk"),
        os.path.join(project_dir, module, "build", "intermediates", "apk", variant, "*.apk"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            # Prefer non-unsigned
            for m in matches:
                if "unsigned" not in m:
                    return m
            return matches[0]
    return None


def _extract_build_errors(output: str) -> str:
    """Pull out the most relevant error lines from Gradle output."""
    error_lines: List[str] = []
    capture = False
    for line in output.splitlines():
        if "FAILURE" in line or "error:" in line.lower() or "Error:" in line:
            capture = True
        if capture:
            error_lines.append(line)
            if len(error_lines) > 30:
                break
    return "\n".join(error_lines)
