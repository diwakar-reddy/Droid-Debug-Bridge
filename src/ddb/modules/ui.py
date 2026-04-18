"""Module 3 — UI inspection and interaction.

Supports both View-based and Jetpack Compose UIs.
For Compose, uses the accessibility tree (dumpsys accessibility) which
exposes semantics nodes including testTag, role, and state. Falls back
to uiautomator for View-based UIs automatically.
"""

from __future__ import annotations

import os
import struct
import time
from typing import Any, Dict, List, Optional

from ddb.utils.adb import Adb
from ddb.utils.output import err, ok
from ddb.utils.parser import (
    detect_compose_in_hierarchy,
    parse_ui_hierarchy,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _png_dimensions(path: str) -> tuple[int, int]:
    """Read width and height from a PNG file header without any external library.

    PNG layout: 8-byte signature, then the first chunk is IHDR (4 bytes length,
    4 bytes "IHDR", 4 bytes width, 4 bytes height, ...).
    """
    with open(path, "rb") as f:
        f.read(16)  # skip: 8-byte sig + 4-byte length + 4-byte "IHDR"
        width = struct.unpack(">I", f.read(4))[0]
        height = struct.unpack(">I", f.read(4))[0]
    return width, height


# ------------------------------------------------------------------
# Screenshot
# ------------------------------------------------------------------


def screenshot(adb: Adb, output_path: str = "screenshot.png") -> Dict:
    """Capture a screenshot and save it locally.

    Args:
        adb: Adb instance.
        output_path: Local path to save the PNG.
    """
    device_path = "/sdcard/cab_screenshot.png"

    # Capture on device
    result = adb.shell(f"screencap -p {device_path}")
    if not result.success:
        return err(f"Screenshot capture failed: {result.stderr}")

    # Pull to local
    pull = adb.run(["pull", device_path, output_path])
    if not pull.success:
        return err(f"Failed to pull screenshot: {pull.stderr}")

    # Clean up device
    adb.shell(f"rm {device_path}")

    abs_path = os.path.abspath(output_path)
    width, height = _png_dimensions(abs_path)
    return ok(
        {
            "path": abs_path,
            "size": os.path.getsize(abs_path),
            "width": width,
            "height": height,
        },
        message=f"Screenshot saved to {abs_path}",
    )


# ------------------------------------------------------------------
# UI Hierarchy — Dual mode (uiautomator + accessibility)
# ------------------------------------------------------------------


def uidump(
    adb: Adb,
    simplify: bool = True,
    mode: str = "auto",
) -> Dict:
    """Dump the current UI hierarchy as structured JSON.

    Args:
        adb: Adb instance.
        simplify: If True, filter out nodes without meaningful content.
        mode: Inspection mode:
            - "auto": Try uiautomator first, switch to accessibility if
              Compose is detected (recommended).
            - "view": Force uiautomator (traditional View hierarchy).
            - "compose": Force accessibility tree (best for Compose).
            - "both": Return results from both sources merged.
    """
    if mode == "compose":
        return _a11y_dump(adb, simplify)
    elif mode == "view":
        return _uiautomator_dump(adb, simplify)
    elif mode == "both":
        return _merged_dump(adb, simplify)
    else:  # auto
        # Dump once via uiautomator, then decide how to present
        xml = _uiautomator_dump_raw(adb)
        if not xml:
            return err("UI dump failed. Device may be locked or no activity is focused.")

        if detect_compose_in_hierarchy(xml):
            # Compose detected — enrich with testTag / role / is_compose
            nodes = parse_ui_hierarchy(xml)
            _enrich_compose_nodes(xml, nodes)
            if simplify:
                nodes = [
                    n
                    for n in nodes
                    if (
                        n.get("text")
                        or n.get("resource_id")
                        or n.get("content_desc")
                        or n.get("test_tag")
                        or n.get("role")
                    )
                ]
            return ok(
                {
                    "source": "compose_semantics",
                    "compose_detected": True,
                    "node_count": len(nodes),
                    "nodes": nodes,
                },
                message=f"Compose tree: {len(nodes)} nodes",
            )
        else:
            return _parse_and_return_uiautomator(xml, simplify, compose_detected=False)


def compose_tree(adb: Adb, package: Optional[str] = None) -> Dict:
    """Dump the Compose semantics tree specifically.

    Uses the accessibility service to extract the Compose semantics
    tree with testTags, roles, and states. This is the preferred
    inspection method for Compose UIs.

    Args:
        adb: Adb instance.
        package: Filter by package name (optional).
    """
    result = _a11y_dump(adb, simplify=False)
    if not result.get("success"):
        return result

    nodes = result["data"]["nodes"]

    # Filter for Compose nodes if we can identify them
    compose_nodes = [n for n in nodes if n.get("is_compose")]

    # If no compose nodes detected, return all (might be mixed UI)
    if not compose_nodes:
        compose_nodes = nodes

    # Filter by package
    if package:
        compose_nodes = [n for n in compose_nodes if package in n.get("package", "")]

    return ok(
        {
            "source": "compose_semantics",
            "node_count": len(compose_nodes),
            "nodes": compose_nodes,
        },
        message=f"Compose tree: {len(compose_nodes)} semantic nodes",
    )


def find_view(
    adb: Adb,
    text: Optional[str] = None,
    resource_id: Optional[str] = None,
    class_name: Optional[str] = None,
    content_desc: Optional[str] = None,
    test_tag: Optional[str] = None,
    role: Optional[str] = None,
    mode: str = "auto",
) -> Dict:
    """Find views matching the given criteria.

    Supports both View and Compose attributes:
        - text: Match by visible text content.
        - resource_id: Match by resource ID (View) or resource name.
        - class_name: Match by view class name.
        - content_desc: Match by accessibility description.
        - test_tag: Match by Compose Modifier.testTag (Compose only).
        - role: Match by Compose semantic role — Button, Checkbox, etc.
        - mode: "auto", "view", "compose", or "both".

    Returns matching nodes with bounds and center coordinates.
    """
    has_compose_criteria = bool(test_tag or role)
    if not any([text, resource_id, class_name, content_desc, test_tag, role]):
        return err(
            "Provide at least one of: text, resource_id, class_name, "
            "content_desc, test_tag, role"
        )

    # If searching by testTag or role, force compose mode
    if has_compose_criteria and mode == "auto":
        mode = "compose"

    dump = uidump(adb, simplify=False, mode=mode)
    if not dump.get("success"):
        return dump

    nodes = dump["data"]["nodes"]
    matches: List[Dict] = []

    for node in nodes:
        if text and text.lower() not in node.get("text", "").lower():
            continue
        if resource_id and resource_id not in node.get("resource_id", ""):
            continue
        if class_name and class_name not in node.get("class", ""):
            continue
        if content_desc and content_desc.lower() not in node.get("content_desc", "").lower():
            continue
        if test_tag and test_tag not in node.get("test_tag", ""):
            continue
        if role and role.lower() != node.get("role", "").lower():
            continue
        matches.append(node)

    if not matches:
        hint = "Try `cab uidump` to see all available views."
        if has_compose_criteria:
            hint = (
                "For Compose: ensure views have Modifier.testTag() or "
                "Modifier.semantics { }. Try `cab compose-tree` to inspect."
            )
        return err("No views found matching criteria.", hint=hint)

    return ok(
        {"count": len(matches), "views": matches},
        message=f"Found {len(matches)} matching view(s)",
    )


# ------------------------------------------------------------------
# Interaction
# ------------------------------------------------------------------


def tap(adb: Adb, x: int, y: int) -> Dict:
    """Tap at screen coordinates."""
    result = adb.shell(f"input tap {x} {y}")
    if not result.success:
        return err(f"Tap failed: {result.stderr}")
    return ok({"x": x, "y": y}, message=f"Tapped ({x}, {y})")


def tap_view(
    adb: Adb,
    text: Optional[str] = None,
    resource_id: Optional[str] = None,
    content_desc: Optional[str] = None,
    test_tag: Optional[str] = None,
    role: Optional[str] = None,
) -> Dict:
    """Find a view and tap its center.

    Supports both View and Compose selectors. For Compose, use
    test_tag (Modifier.testTag) or role for reliable element targeting.
    """
    found = find_view(
        adb,
        text=text,
        resource_id=resource_id,
        content_desc=content_desc,
        test_tag=test_tag,
        role=role,
    )
    if not found.get("success"):
        return found

    view = found["data"]["views"][0]
    center = view.get("center")
    if not center:
        return err("View found but has no bounds.")

    return tap(adb, center["x"], center["y"])


def swipe(
    adb: Adb,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
) -> Dict:
    """Swipe from (x1,y1) to (x2,y2)."""
    result = adb.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
    if not result.success:
        return err(f"Swipe failed: {result.stderr}")
    return ok(
        {"from": [x1, y1], "to": [x2, y2], "duration_ms": duration_ms},
        message=f"Swiped ({x1},{y1}) -> ({x2},{y2})",
    )


def input_text(adb: Adb, text: str) -> Dict:
    """Type text into the currently focused input field.

    Special characters are escaped for adb shell input.
    """
    escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
    result = adb.shell(f"input text '{escaped}'")
    if not result.success:
        return err(f"Text input failed: {result.stderr}")
    return ok({"text": text}, message=f"Typed: {text}")


def keyevent(adb: Adb, key: str) -> Dict:
    """Send a key event. Accepts key name or code.

    Common keys: BACK, HOME, ENTER, DPAD_UP, DPAD_DOWN, TAB,
    VOLUME_UP, VOLUME_DOWN, POWER, DELETE, MENU.
    """
    if not key.startswith("KEYCODE_") and not key.isdigit():
        key = f"KEYCODE_{key.upper()}"

    result = adb.shell(f"input keyevent {key}")
    if not result.success:
        return err(f"Key event failed: {result.stderr}")
    return ok({"key": key}, message=f"Sent key: {key}")


def long_press(adb: Adb, x: int, y: int, duration_ms: int = 1000) -> Dict:
    """Long press at coordinates (implemented as a zero-distance swipe)."""
    result = adb.shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
    if not result.success:
        return err(f"Long press failed: {result.stderr}")
    return ok({"x": x, "y": y, "duration_ms": duration_ms}, message=f"Long pressed ({x}, {y})")


def scroll_down(adb: Adb) -> Dict:
    """Scroll down one page (generic swipe gesture)."""
    w, h = _get_screen_size(adb)
    cx = w // 2
    return swipe(adb, cx, int(h * 0.7), cx, int(h * 0.3), 400)


def scroll_up(adb: Adb) -> Dict:
    """Scroll up one page."""
    w, h = _get_screen_size(adb)
    cx = w // 2
    return swipe(adb, cx, int(h * 0.3), cx, int(h * 0.7), 400)


def wait_for_view(
    adb: Adb,
    text: Optional[str] = None,
    resource_id: Optional[str] = None,
    test_tag: Optional[str] = None,
    content_desc: Optional[str] = None,
    timeout_sec: int = 10,
    poll_interval: float = 1.0,
) -> Dict:
    """Wait for a view to appear on screen within a timeout.

    Useful after navigation or animation, especially in Compose where
    recomposition may take a moment.

    Args:
        timeout_sec: Max seconds to wait.
        poll_interval: Seconds between each check.
    """
    start = time.time()
    attempts = 0

    while time.time() - start < timeout_sec:
        attempts += 1
        found = find_view(
            adb,
            text=text,
            resource_id=resource_id,
            test_tag=test_tag,
            content_desc=content_desc,
        )
        if found.get("success"):
            found["data"]["wait_time"] = round(time.time() - start, 2)
            found["data"]["attempts"] = attempts
            return found
        time.sleep(poll_interval)

    return err(
        f"View not found within {timeout_sec}s after {attempts} attempts.",
        hint="The view may not have loaded, or the selector criteria may be wrong.",
    )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _uiautomator_dump_raw(adb: Adb) -> Optional[str]:
    """Dump UI via uiautomator and return raw XML string."""
    device_path = "/sdcard/cab_uidump.xml"

    result = adb.shell(f"uiautomator dump {device_path}")
    if not result.success:
        return None

    cat = adb.shell(f"cat {device_path}")
    adb.shell(f"rm {device_path}")

    if not cat.success:
        return None
    return cat.stdout


def _uiautomator_dump(adb: Adb, simplify: bool) -> Dict:
    """Full uiautomator dump with parsing."""
    xml = _uiautomator_dump_raw(adb)
    if not xml:
        return err("UI dump failed. Device may be locked or no activity is focused.")
    return _parse_and_return_uiautomator(xml, simplify)


def _parse_and_return_uiautomator(
    xml_str: str,
    simplify: bool,
    compose_detected: bool = False,
) -> Dict:
    """Parse uiautomator XML and return as structured response."""
    nodes = parse_ui_hierarchy(xml_str)
    if simplify:
        nodes = [
            n
            for n in nodes
            if (
                n.get("text")
                or n.get("resource_id")
                or n.get("content_desc")
                or n.get("test_tag")
                or n.get("role")
            )
        ]

    data: Dict[str, Any] = {
        "source": "uiautomator",
        "node_count": len(nodes),
        "nodes": nodes,
    }
    if compose_detected:
        data["compose_detected"] = True
        data["hint"] = (
            "Compose UI detected. Use `cab uidump --mode compose` or "
            "`cab compose-tree` for richer semantics data (testTag, role, etc.)."
        )

    return ok(data, message=f"UI hierarchy: {len(nodes)} nodes")


def _a11y_dump(adb: Adb, simplify: bool) -> Dict:
    """Dump UI with Compose-aware enrichment.

    The previous approach (``dumpsys accessibility``) only outputs
    *service configuration* — not the actual node tree — so it always
    returned 0 nodes.  The correct approach for Compose is still
    ``uiautomator dump``: since Compose 1.0 / API 30+, Compose exposes
    its semantics tree through the accessibility framework, and
    uiautomator traverses that same framework.  Key mappings:

        Compose Modifier.testTag("x")  →  resource-id="x"
        Compose role (Button, etc.)    →  className android.widget.Button
        Compose text / contentDesc     →  text / content-desc attributes

    This function uses uiautomator dump + post-processing to tag
    Compose-specific fields (test_tag, role, is_compose).
    """
    xml = _uiautomator_dump_raw(adb)
    if not xml:
        return err("UI dump failed. Device may be locked or no activity is focused.")

    nodes = parse_ui_hierarchy(xml)
    _enrich_compose_nodes(xml, nodes)

    if simplify:
        nodes = [
            n
            for n in nodes
            if (
                n.get("text")
                or n.get("resource_id")
                or n.get("content_desc")
                or n.get("test_tag")
                or n.get("role")
            )
        ]

    return ok(
        {
            "source": "compose_semantics",
            "node_count": len(nodes),
            "nodes": nodes,
        },
        message=f"Compose tree: {len(nodes)} nodes",
    )


# Compose exposes semantic roles via className in uiautomator XML.
_CLASS_TO_ROLE = {
    "android.widget.Button": "Button",
    "android.widget.CheckBox": "Checkbox",
    "android.widget.Switch": "Switch",
    "android.widget.RadioButton": "RadioButton",
    "android.widget.ToggleButton": "Toggle",
    "android.widget.EditText": "TextField",
    "android.widget.AutoCompleteTextView": "TextField",
    "android.widget.ImageView": "Image",
    "android.widget.ImageButton": "ImageButton",
    "android.widget.SeekBar": "Slider",
    "android.widget.ProgressBar": "ProgressBar",
    "android.widget.Spinner": "DropdownMenu",
    "android.widget.TabWidget": "Tab",
}


def _enrich_compose_nodes(xml_str: str, nodes: list) -> None:
    """Add Compose-specific fields to uiautomator nodes in-place.

    Detection strategy:
    1. Walk the flat node list looking for ``AndroidComposeView``.
       Every node whose depth is greater (i.e. nested inside it) is
       marked ``is_compose = True``.
    2. For Compose nodes, ``resource-id`` that does NOT contain ``:id/``
       is treated as a ``Modifier.testTag`` value (Compose ≥ 1.2 maps
       testTag to the accessibility ``viewIdResourceName``).
    3. ``className`` is mapped to a semantic ``role`` string.
    """
    # --- Pass 1: find AndroidComposeView boundaries -----------------
    compose_root_depth: int | None = None

    for node in nodes:
        cls = node.get("class", "")

        if "AndroidComposeView" in cls or "ComposeView" in cls:
            compose_root_depth = node["depth"]
            node["is_compose"] = True
            node.setdefault("test_tag", "")
            node.setdefault("role", "")
            continue

        # Inside the Compose subtree?
        if compose_root_depth is not None and node["depth"] > compose_root_depth:
            node["is_compose"] = True
        else:
            # We left the Compose subtree
            if compose_root_depth is not None and node["depth"] <= compose_root_depth:
                compose_root_depth = None
            node["is_compose"] = False

        # --- testTag extraction -------------------------------------
        rid = node.get("resource_id", "")
        if node.get("is_compose") and rid and ":id/" not in rid:
            # Compose testTag — raw string without the package:id/ prefix
            node["test_tag"] = rid
        else:
            node["test_tag"] = ""

        # --- role inference -----------------------------------------
        node["role"] = _CLASS_TO_ROLE.get(node.get("class", ""), "")


def _merged_dump(adb: Adb, simplify: bool) -> Dict:
    """Merge uiautomator and accessibility dumps for complete picture."""
    ui = _uiautomator_dump(adb, simplify)
    a11y = _a11y_dump(adb, simplify)

    ui_nodes = ui.get("data", {}).get("nodes", []) if ui.get("success") else []
    a11y_nodes = a11y.get("data", {}).get("nodes", []) if a11y.get("success") else []

    # Tag sources
    for n in ui_nodes:
        n["source"] = "uiautomator"
    for n in a11y_nodes:
        n["source"] = "accessibility"

    # Re-index
    all_nodes = ui_nodes + a11y_nodes
    for i, n in enumerate(all_nodes):
        n["index"] = i

    return ok(
        {
            "source": "merged",
            "node_count": len(all_nodes),
            "uiautomator_count": len(ui_nodes),
            "accessibility_count": len(a11y_nodes),
            "nodes": all_nodes,
        },
        message=f"Merged: {len(ui_nodes)} view + {len(a11y_nodes)} accessibility nodes",
    )


def _get_screen_size(adb: Adb) -> tuple:
    """Get screen dimensions, with fallback."""
    size_result = adb.shell("wm size")
    if size_result.success and "x" in size_result.stdout:
        parts = size_result.stdout.split(":")[-1].strip().split("x")
        return int(parts[0]), int(parts[1])
    return 1080, 1920
