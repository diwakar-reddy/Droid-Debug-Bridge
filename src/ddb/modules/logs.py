"""Module 4 — Log streaming and filtering."""

from __future__ import annotations

from typing import Dict, List, Optional

from ddb.utils.adb import Adb
from ddb.utils.output import err, ok
from ddb.utils.parser import parse_logcat_line


def logs(
    adb: Adb,
    tag: Optional[str] = None,
    level: Optional[str] = None,
    package: Optional[str] = None,
    lines: int = 50,
    grep: Optional[str] = None,
) -> Dict:
    """Capture filtered logcat output.

    Args:
        adb: Adb instance.
        tag: Filter by log tag (e.g. 'MyApp', 'ActivityManager').
        level: Minimum log level: V, D, I, W, E, F.
        package: Filter by app package name (finds PID first).
        lines: Number of recent lines to return.
        grep: Grep pattern to filter log messages.
    """
    # Build logcat command
    cmd_parts = ["logcat", "-d", "-v", "threadtime"]

    # Tag:level filter
    if tag and level:
        cmd_parts += ["-s", f"{tag}:{level}"]
    elif tag:
        cmd_parts += ["-s", f"{tag}:V"]
    elif level:
        cmd_parts += ["*:" + level.upper()]

    # PID filter for package
    pid = None
    if package:
        pid_result = adb.shell(f"pidof {package}")
        if pid_result.success and pid_result.stdout.strip():
            pid = pid_result.stdout.strip().split()[0]
            cmd_parts += ["--pid", pid]
        else:
            # App might not be running — note this but continue
            pass

    cmd = " ".join(cmd_parts)
    result = adb.shell(cmd)

    if not result.success:
        return err(f"Logcat failed: {result.stderr}")

    # Parse and filter
    raw_lines = result.stdout.splitlines()

    # Apply grep filter
    if grep:
        raw_lines = [l for l in raw_lines if grep.lower() in l.lower()]

    # Take last N lines
    raw_lines = raw_lines[-lines:]

    # Parse into structured format
    parsed = []
    for line in raw_lines:
        entry = parse_logcat_line(line)
        if entry:
            parsed.append(entry)
        elif line.strip():
            # Continuation line or unparseable — include raw
            parsed.append({"raw": line.strip()})

    return ok(
        {"count": len(parsed), "entries": parsed},
        message=f"Captured {len(parsed)} log entries",
    )


def logs_clear(adb: Adb) -> Dict:
    """Clear the logcat buffer."""
    result = adb.shell("logcat -c")
    if not result.success:
        return err(f"Failed to clear logs: {result.stderr}")
    return ok(message="Logcat buffer cleared")


def crash_log(adb: Adb, package: str) -> Dict:
    """Get the most recent crash trace for a package.

    Combines logcat crash buffer and dropbox entries.
    """
    # Try crash buffer first
    result = adb.shell(f"logcat -b crash -d -v threadtime --pid=$(pidof {package}) -t 100")
    crash_lines: List[str] = []

    if result.success and result.stdout.strip():
        crash_lines = result.stdout.strip().splitlines()

    # Also try ActivityManager for ANR and crash entries
    am_result = adb.shell(
        f"logcat -d -v threadtime -s ActivityManager:E AndroidRuntime:E -t 100"
    )
    am_lines: List[str] = []
    if am_result.success:
        am_lines = [l for l in am_result.stdout.splitlines() if package in l]

    all_lines = crash_lines + am_lines
    if not all_lines:
        return ok(
            {"entries": []},
            message=f"No crashes found for {package}",
        )

    parsed = []
    for line in all_lines[-100:]:
        entry = parse_logcat_line(line)
        if entry:
            parsed.append(entry)
        elif line.strip():
            parsed.append({"raw": line.strip()})

    return ok(
        {"package": package, "count": len(parsed), "entries": parsed},
        message=f"Found {len(parsed)} crash log entries for {package}",
    )
