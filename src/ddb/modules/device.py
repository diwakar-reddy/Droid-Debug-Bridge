"""Module 1 — Device management: list, connect, inspect."""

from __future__ import annotations

from typing import Any, Dict, List

from ddb.utils.adb import Adb, AdbError
from ddb.utils.output import err, ok
from ddb.utils.parser import parse_getprop


def devices(adb: Adb) -> Dict:
    """List all connected devices/emulators with detailed info.

    Returns JSON with a list of devices, each containing serial, state,
    model, sdk version, and transport type.
    """
    result = adb.run(["devices", "-l"])
    if not result.success:
        return err(f"Failed to list devices: {result.stderr}")

    device_list: List[Dict[str, str]] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        state = parts[1]

        # Parse key:value pairs like model:Pixel_6 transport_id:1
        info: Dict[str, str] = {"serial": serial, "state": state}
        for part in parts[2:]:
            if ":" in part:
                k, v = part.split(":", 1)
                info[k] = v

        device_list.append(info)

    if not device_list:
        return err(
            "No devices found.",
            hint="Start an emulator with 'emulator -avd <name>' or connect a device via USB.",
        )

    return ok(device_list, message=f"Found {len(device_list)} device(s)")


def info(adb: Adb) -> Dict:
    """Get detailed information about the active device."""
    try:
        adb.ensure_connected()
    except AdbError as e:
        return err(str(e))

    props_result = adb.shell("getprop")
    if not props_result.success:
        return err(f"Failed to read device properties: {props_result.stderr}")

    props = parse_getprop(props_result.stdout)

    # Screen size
    screen = adb.shell("wm size")
    density = adb.shell("wm density")

    # Battery
    battery = adb.shell("dumpsys battery")
    battery_info = _parse_battery(battery.stdout) if battery.success else {}

    device_info = {
        "model": props.get("ro.product.model", "unknown"),
        "manufacturer": props.get("ro.product.manufacturer", "unknown"),
        "device": props.get("ro.product.device", "unknown"),
        "android_version": props.get("ro.build.version.release", "unknown"),
        "sdk_version": props.get("ro.build.version.sdk", "unknown"),
        "build_id": props.get("ro.build.display.id", "unknown"),
        "abi": props.get("ro.product.cpu.abi", "unknown"),
        "serial": props.get("ro.serialno", adb.serial or "unknown"),
        "screen_size": _extract_value(screen.stdout) if screen.success else "unknown",
        "screen_density": _extract_value(density.stdout) if density.success else "unknown",
        "battery": battery_info,
    }

    return ok(device_info)


def connect(serial: str) -> Dict:
    """Set the active device serial.

    This creates a new Adb instance targeting the device and verifies
    it's reachable. Returns the serial to use for subsequent commands.
    """
    adb = Adb(serial=serial)
    try:
        adb.ensure_connected()
    except AdbError as e:
        return err(str(e))

    return ok({"serial": serial}, message=f"Active device set to {serial}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_value(output: str) -> str:
    """Extract value after 'key: value' or 'key:value' patterns."""
    for line in output.splitlines():
        if ":" in line:
            return line.split(":", 1)[1].strip()
    return output.strip()


def _parse_battery(output: str) -> Dict[str, Any]:
    """Parse dumpsys battery output."""
    info: Dict[str, Any] = {}
    for line in output.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        val = val.strip()
        if val.isdigit():
            info[key] = int(val)
        elif val.lower() in ("true", "false"):
            info[key] = val.lower() == "true"
        else:
            info[key] = val
    return info
