"""Low-level ADB command runner with structured output."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AdbResult:
    """Structured result from an ADB command."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
        }


class AdbError(Exception):
    """Raised when an ADB command fails."""

    def __init__(self, message: str, result: Optional[AdbResult] = None):
        super().__init__(message)
        self.result = result


class Adb:
    """Wrapper around the ADB command-line tool.

    Usage:
        adb = Adb()                          # auto-detect adb binary
        adb = Adb(serial="emulator-5554")    # target specific device

    All methods return structured AdbResult objects. For convenience,
    higher-level modules should use these building blocks rather than
    calling subprocess directly.
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        adb_path: Optional[str] = None,
    ):
        self.serial = serial or os.environ.get("CAB_DEVICE_SERIAL")
        self.adb_path = adb_path or self._find_adb()

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def run(
        self,
        args: List[str],
        timeout: int = 120,
        check: bool = False,
    ) -> AdbResult:
        """Run an adb command and return an AdbResult.

        Args:
            args: Arguments to pass after ``adb [-s serial]``.
            timeout: Seconds before the command is killed.
            check: If True, raise AdbError on non-zero exit.

        Returns:
            AdbResult with stdout/stderr captured.
        """
        cmd = self._build_cmd(args)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result = AdbResult(
                success=proc.returncode == 0,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                returncode=proc.returncode,
            )
            if check and not result.success:
                raise AdbError(
                    f"adb {' '.join(args)} failed (rc={proc.returncode}): {result.stderr}",
                    result=result,
                )
            return result
        except subprocess.TimeoutExpired:
            return AdbResult(success=False, stderr=f"Command timed out after {timeout}s")
        except FileNotFoundError:
            return AdbResult(
                success=False,
                stderr=f"adb not found at '{self.adb_path}'. Install Android SDK Platform-Tools.",
            )

    def shell(self, cmd: str, timeout: int = 60) -> AdbResult:
        """Shortcut for ``adb shell <cmd>``."""
        return self.run(["shell", cmd], timeout=timeout)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_cmd(self, args: List[str]) -> List[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += args
        return cmd

    @staticmethod
    def _find_adb() -> str:
        """Locate the adb binary."""
        # 1. Explicit env var
        env_path = os.environ.get("ADB_PATH")
        if env_path and os.path.isfile(env_path):
            return env_path

        # 2. On PATH
        found = shutil.which("adb")
        if found:
            return found

        # 3. Common locations
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Library", "Android", "sdk", "platform-tools", "adb"),
            os.path.join(home, "Android", "Sdk", "platform-tools", "adb"),
            "/usr/local/bin/adb",
            "/opt/homebrew/bin/adb",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

        # Fallback — will fail at runtime with a clear message
        return "adb"

    def ensure_connected(self) -> None:
        """Verify at least one device is available, raising AdbError if not."""
        result = self.run(["devices"])
        if not result.success:
            raise AdbError(f"Cannot reach adb: {result.stderr}", result)
        lines = [
            line
            for line in result.stdout.splitlines()[1:]
            if line.strip() and "offline" not in line
        ]
        if not lines:
            raise AdbError(
                "No devices connected. Start an emulator or connect a device via USB.",
                result,
            )
