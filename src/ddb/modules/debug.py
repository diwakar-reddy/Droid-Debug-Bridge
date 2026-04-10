"""Module 5 — Debugging and diagnostics: shell, files, permissions, prefs, db."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from ddb.utils.adb import Adb
from ddb.utils.output import err, ok


def shell(adb: Adb, command: str, timeout: int = 60) -> Dict:
    """Run an arbitrary adb shell command."""
    result = adb.shell(command, timeout=timeout)
    return ok(
        {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode},
        message="Command completed" if result.success else "Command failed",
    )


def pull_file(adb: Adb, device_path: str, local_path: str) -> Dict:
    """Pull a file from the device to local filesystem."""
    result = adb.run(["pull", device_path, local_path])
    if not result.success:
        return err(f"Pull failed: {result.stderr}")

    abs_path = os.path.abspath(local_path)
    return ok(
        {"local_path": abs_path, "device_path": device_path},
        message=f"Pulled {device_path} -> {abs_path}",
    )


def push_file(adb: Adb, local_path: str, device_path: str) -> Dict:
    """Push a file from local filesystem to the device."""
    if not os.path.exists(local_path):
        return err(f"Local file not found: {local_path}")

    result = adb.run(["push", local_path, device_path])
    if not result.success:
        return err(f"Push failed: {result.stderr}")

    return ok(
        {"local_path": os.path.abspath(local_path), "device_path": device_path},
        message=f"Pushed {local_path} -> {device_path}",
    )


def permissions(adb: Adb, package: str) -> Dict:
    """List granted and denied runtime permissions for an app."""
    result = adb.shell(f"dumpsys package {package}")
    if not result.success:
        return err(f"Failed to get package info: {result.stderr}")

    granted: List[str] = []
    denied: List[str] = []
    install_perms: List[str] = []

    in_runtime = False
    in_install = False

    for line in result.stdout.splitlines():
        stripped = line.strip()

        if "runtime permissions:" in stripped.lower():
            in_runtime = True
            in_install = False
            continue
        if "install permissions:" in stripped.lower():
            in_install = True
            in_runtime = False
            continue
        if stripped.startswith("gids=") or (not stripped.startswith("android.permission") and "permission" not in stripped.lower()):
            if in_runtime or in_install:
                # Might be end of section
                if not stripped or stripped.startswith("["):
                    in_runtime = False
                    in_install = False
                continue

        if in_runtime:
            if ": granted=true" in stripped:
                perm = stripped.split(":")[0].strip()
                granted.append(perm)
            elif ": granted=false" in stripped:
                perm = stripped.split(":")[0].strip()
                denied.append(perm)

        if in_install and stripped.startswith("android.permission"):
            perm = stripped.split(":")[0].strip()
            install_perms.append(perm)

    return ok({
        "package": package,
        "runtime_granted": granted,
        "runtime_denied": denied,
        "install_permissions": install_perms,
    })


def grant_permission(adb: Adb, package: str, permission: str) -> Dict:
    """Grant a runtime permission to an app."""
    # Normalize — accept shorthand like "CAMERA"
    if not permission.startswith("android.permission."):
        permission = f"android.permission.{permission}"

    result = adb.shell(f"pm grant {package} {permission}")
    if not result.success:
        return err(f"Grant failed: {result.stderr}")

    return ok(
        {"package": package, "permission": permission},
        message=f"Granted {permission} to {package}",
    )


def revoke_permission(adb: Adb, package: str, permission: str) -> Dict:
    """Revoke a runtime permission from an app."""
    if not permission.startswith("android.permission."):
        permission = f"android.permission.{permission}"

    result = adb.shell(f"pm revoke {package} {permission}")
    if not result.success:
        return err(f"Revoke failed: {result.stderr}")

    return ok(
        {"package": package, "permission": permission},
        message=f"Revoked {permission} from {package}",
    )


def shared_prefs(adb: Adb, package: str, prefs_name: Optional[str] = None) -> Dict:
    """Dump SharedPreferences for a debug app.

    Args:
        package: App package name.
        prefs_name: Specific prefs file name. If None, lists all available.
    """
    prefs_dir = f"/data/data/{package}/shared_prefs"

    if prefs_name:
        result = adb.shell(f"run-as {package} cat shared_prefs/{prefs_name}.xml")
        if not result.success:
            # Try without run-as (for debuggable apps on rooted devices)
            result = adb.shell(f"cat {prefs_dir}/{prefs_name}.xml")
        if not result.success:
            return err(
                f"Cannot read prefs '{prefs_name}': {result.stderr}",
                hint="App must be debuggable (debug build) or device must be rooted.",
            )
        return ok({"file": prefs_name, "content": result.stdout})

    # List all prefs files
    result = adb.shell(f"run-as {package} ls shared_prefs/")
    if not result.success:
        result = adb.shell(f"ls {prefs_dir}/")
    if not result.success:
        return err(
            f"Cannot list shared prefs: {result.stderr}",
            hint="App must be debuggable or device must be rooted.",
        )

    files = [f.strip().replace(".xml", "") for f in result.stdout.splitlines() if f.strip()]
    return ok(
        {"package": package, "files": files},
        message=f"Found {len(files)} SharedPreferences file(s)",
    )


def query_db(adb: Adb, package: str, db_name: str, query: str) -> Dict:
    """Run a SQLite query on an app's database.

    Args:
        package: App package name.
        db_name: Database filename (e.g. 'app.db').
        query: SQL query to execute.
    """
    # Escape quotes in query
    safe_query = query.replace("'", "'\\''")
    db_path = f"databases/{db_name}"

    result = adb.shell(
        f"run-as {package} sqlite3 {db_path} '{safe_query}'"
    )
    if not result.success:
        return err(
            f"Query failed: {result.stderr}",
            hint="Ensure the app is debuggable and the database exists.",
        )

    # Parse sqlite output into rows
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    return ok(
        {"query": query, "row_count": len(rows), "rows": rows},
        message=f"Query returned {len(rows)} row(s)",
    )
