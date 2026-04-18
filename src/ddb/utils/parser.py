"""Parsers for ADB output formats — UI hierarchy XML, accessibility tree, property lists."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

# ====================================================================
# UI Hierarchy (uiautomator dump) — works for View-based UIs
# ====================================================================


def parse_ui_hierarchy(xml_str: str) -> List[Dict[str, Any]]:
    """Parse uiautomator XML dump into a flat list of view nodes.

    Each node contains:
        - class: e.g. "android.widget.TextView"
        - resource_id: e.g. "com.example:id/title"
        - text: visible text
        - content_desc: accessibility description
        - bounds: {"left": int, "top": int, "right": int, "bottom": int}
        - center: {"x": int, "y": int}
        - clickable, enabled, focusable, scrollable: booleans
        - package: app package name
        - depth: nesting depth in the hierarchy
        - index: sequential index in the flat list
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return []

    nodes: List[Dict[str, Any]] = []
    _walk(root, nodes, depth=0)
    return nodes


def _walk(element: ET.Element, nodes: List[Dict], depth: int) -> None:
    """Recursively walk the XML tree."""
    node = _parse_node(element, depth, len(nodes))
    if node:
        nodes.append(node)
    for child in element:
        _walk(child, nodes, depth + 1)


def _parse_node(el: ET.Element, depth: int, index: int) -> Optional[Dict[str, Any]]:
    """Extract attributes from a single XML element."""
    attrib = el.attrib
    if not attrib:
        return None

    bounds = _parse_bounds(attrib.get("bounds", ""))
    center = None
    if bounds:
        center = {
            "x": (bounds["left"] + bounds["right"]) // 2,
            "y": (bounds["top"] + bounds["bottom"]) // 2,
        }

    return {
        "index": index,
        "depth": depth,
        "class": attrib.get("class", ""),
        "resource_id": attrib.get("resource-id", ""),
        "text": attrib.get("text", ""),
        "content_desc": attrib.get("content-desc", ""),
        "package": attrib.get("package", ""),
        "bounds": bounds,
        "center": center,
        "clickable": attrib.get("clickable") == "true",
        "enabled": attrib.get("enabled") == "true",
        "focusable": attrib.get("focusable") == "true",
        "scrollable": attrib.get("scrollable") == "true",
        "checked": attrib.get("checked") == "true",
        "selected": attrib.get("selected") == "true",
    }


_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _parse_bounds(bounds_str: str) -> Optional[Dict[str, int]]:
    """Parse '[left,top][right,bottom]' into a dict."""
    m = _BOUNDS_RE.match(bounds_str)
    if not m:
        return None
    return {
        "left": int(m.group(1)),
        "top": int(m.group(2)),
        "right": int(m.group(3)),
        "bottom": int(m.group(4)),
    }


# ====================================================================
# Compose / Accessibility Tree (dumpsys accessibility)
# ====================================================================
#
# Jetpack Compose doesn't use traditional View IDs. Instead, it exposes
# a semantics tree through the accessibility framework. We parse the
# output of `dumpsys activity top` and `dumpsys accessibility` to get
# richer Compose-aware node data including:
#   - testTag (Modifier.testTag)
#   - role (Button, Checkbox, etc.)
#   - stateDescription
#   - actions (tap, scroll, setText, etc.)
#
# The accessibility dump format looks like:
#   android.view.accessibility.AccessibilityNodeInfo@HEXID;
#     boundsInParent: Rect(0, 0 - 1080, 2340); boundsInScreen: Rect(0, 0 - 1080, 2340);
#     packageName: com.example; className: android.widget.FrameLayout;
#     text: Hello; contentDescription: greeting; viewIdResourceName: com.example:id/text;
#     ...

_A11Y_NODE_START_RE = re.compile(
    r"android\.view\.accessibility\.AccessibilityNodeInfo@([0-9a-fA-F]+)"
)

_A11Y_BOUNDS_RE = re.compile(r"boundsInScreen:\s*Rect\((\d+),\s*(\d+)\s*-\s*(\d+),\s*(\d+)\)")

_A11Y_KV_PATTERNS = {
    "text": re.compile(r"text:\s*(.+?)(?:;|$)"),
    "content_desc": re.compile(r"contentDescription:\s*(.+?)(?:;|$)"),
    "class": re.compile(r"className:\s*(\S+?)(?:;|$)"),
    "package": re.compile(r"packageName:\s*(\S+?)(?:;|$)"),
    "resource_id": re.compile(r"viewIdResourceName:\s*(\S+?)(?:;|$)"),
    "state_desc": re.compile(r"stateDescription:\s*(.+?)(?:;|$)"),
    "error": re.compile(r"error:\s*(.+?)(?:;|$)"),
    "tooltip": re.compile(r"tooltipText:\s*(.+?)(?:;|$)"),
}

# Compose testTag appears as viewIdResourceName or in extras
_COMPOSE_TAG_RE = re.compile(r"tag=([^,;\]]+)")

# Compose role info
_COMPOSE_ROLE_RE = re.compile(r"Role=(\w+)")


def parse_accessibility_tree(dump_output: str) -> List[Dict[str, Any]]:
    """Parse ``dumpsys accessibility`` output into a flat list of nodes.

    Returns nodes with similar structure to parse_ui_hierarchy but with
    additional Compose-specific fields:
        - test_tag: Modifier.testTag value (Compose)
        - role: semantic role (Button, Checkbox, etc.)
        - state_desc: state description text
        - actions: list of available accessibility actions
        - is_compose: True if this node is from a Compose hierarchy
    """
    nodes: List[Dict[str, Any]] = []
    current_lines: List[str] = []
    depth = 0

    for line in dump_output.splitlines():
        # Detect indentation depth (each level is typically 2-4 spaces)
        stripped = line.lstrip()
        if not stripped:
            continue

        indent = len(line) - len(stripped)

        if _A11Y_NODE_START_RE.search(stripped):
            # Process previous node if any
            if current_lines:
                node = _parse_a11y_node(current_lines, depth, len(nodes))
                if node:
                    nodes.append(node)
            current_lines = [stripped]
            depth = indent // 2
        elif current_lines:
            current_lines.append(stripped)

    # Process last node
    if current_lines:
        node = _parse_a11y_node(current_lines, depth, len(nodes))
        if node:
            nodes.append(node)

    return nodes


def _parse_a11y_node(lines: List[str], depth: int, index: int) -> Optional[Dict[str, Any]]:
    """Parse a single accessibility node from its text lines."""
    text = " ".join(lines)

    # Extract bounds
    bounds_match = _A11Y_BOUNDS_RE.search(text)
    bounds = None
    center = None
    if bounds_match:
        bounds = {
            "left": int(bounds_match.group(1)),
            "top": int(bounds_match.group(2)),
            "right": int(bounds_match.group(3)),
            "bottom": int(bounds_match.group(4)),
        }
        center = {
            "x": (bounds["left"] + bounds["right"]) // 2,
            "y": (bounds["top"] + bounds["bottom"]) // 2,
        }

    # Extract key-value fields
    node: Dict[str, Any] = {
        "index": index,
        "depth": depth,
        "bounds": bounds,
        "center": center,
    }

    for key, pattern in _A11Y_KV_PATTERNS.items():
        m = pattern.search(text)
        node[key] = m.group(1).strip() if m else ""

    # Clean up "null" values that ADB sometimes returns
    for key in list(node.keys()):
        if node[key] == "null":
            node[key] = ""

    # Detect Compose-specific info
    is_compose = "AndroidComposeView" in text or "ComposeView" in node.get("class", "")

    # Extract testTag — Compose exposes this in extras or as resource-id
    test_tag = ""
    tag_match = _COMPOSE_TAG_RE.search(text)
    if tag_match:
        test_tag = tag_match.group(1).strip()
    elif "TestTag" in text:
        # Sometimes appears as: extras: [TestTag=my_tag]
        tt_match = re.search(r"TestTag=([^,;\]\s]+)", text)
        if tt_match:
            test_tag = tt_match.group(1)

    node["test_tag"] = test_tag

    # Extract role
    role_match = _COMPOSE_ROLE_RE.search(text)
    node["role"] = role_match.group(1) if role_match else ""

    # Detect Compose node
    node["is_compose"] = is_compose or bool(test_tag) or bool(node.get("role"))

    # Extract boolean properties
    node["clickable"] = "clickable" in text.lower() and "not clickable" not in text.lower()
    node["enabled"] = "disabled" not in text.lower()
    node["focusable"] = "focusable" in text.lower() and "not focusable" not in text.lower()
    node["scrollable"] = "scrollable" in text.lower()
    node["checked"] = "checked: true" in text.lower() or "STATE_CHECKED" in text
    node["selected"] = "selected: true" in text.lower() or "STATE_SELECTED" in text

    # Extract available actions
    actions: List[str] = []
    action_pattern = re.compile(r"AccessibilityAction:\s*(\w+)")
    for m in action_pattern.finditer(text):
        actions.append(m.group(1))
    # Also capture simpler action format
    simple_actions = re.compile(r"actions:\s*\[([^\]]+)\]")
    sa_match = simple_actions.search(text)
    if sa_match:
        actions.extend(a.strip() for a in sa_match.group(1).split(","))
    node["actions"] = list(set(actions))

    return node


# ====================================================================
# Compose Window dump (dumpsys activity top)
# ====================================================================
#
# `dumpsys activity top` includes Compose hierarchy info showing
# the recomposition tree. We parse this to detect Compose layout
# structure.


def detect_compose_in_hierarchy(xml_str: str) -> bool:
    """Check if a uiautomator dump contains Compose views.

    Compose renders into a single AndroidComposeView, so the hierarchy
    will show that as a parent with Compose content inside.
    """
    return "AndroidComposeView" in xml_str or "ComposeView" in xml_str


# ====================================================================
# Logcat parsing
# ====================================================================

_LOGCAT_RE = re.compile(
    r"^(?P<date>\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEF])\s+"
    r"(?P<tag>\S+)\s*:\s+"
    r"(?P<message>.*)$"
)


def parse_logcat_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single logcat line (threadtime format) into a dict."""
    m = _LOGCAT_RE.match(line)
    if not m:
        return None
    return m.groupdict()


# ====================================================================
# Compose recomposition count parsing
# ====================================================================

_RECOMP_RE = re.compile(
    r"Recomposition\s+(?P<composable>\S+)\s+" r"count=(?P<count>\d+)\s+" r"skipped=(?P<skipped>\d+)"
)


def parse_recomposition_stats(logcat_output: str) -> List[Dict[str, Any]]:
    """Parse Compose recomposition statistics from logcat.

    Requires the app to have composition tracing enabled.
    Returns list of composables with their recomposition counts.
    """
    stats: List[Dict[str, Any]] = []
    for line in logcat_output.splitlines():
        m = _RECOMP_RE.search(line)
        if m:
            stats.append(
                {
                    "composable": m.group("composable"),
                    "recomposition_count": int(m.group("count")),
                    "skipped": int(m.group("skipped")),
                }
            )
    return stats


# ====================================================================
# Device properties
# ====================================================================


def parse_getprop(output: str) -> Dict[str, str]:
    """Parse ``adb shell getprop`` output into a dict."""
    props: Dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("[") and "]: [" in line:
            key, _, val = line[1:].partition("]: [")
            props[key] = val.rstrip("]")
    return props


# ====================================================================
# Project type detection
# ====================================================================

# KMP/CMP common module names
KMP_MODULES = [
    "composeApp",
    "androidApp",
    "shared",
    "common",
    "iosApp",
    "desktopApp",
    "webApp",
]

# Gradle files that signal project type
COMPOSE_MARKERS = [
    "org.jetbrains.compose",  # CMP plugin
    "org.jetbrains.kotlin.multiplatform",  # KMP plugin
    "compose.desktop",  # CMP desktop
    "compose.experimental.web",  # CMP web
    'kotlin("multiplatform")',  # KMP DSL
]


def detect_project_type(build_gradle_content: str) -> Dict[str, Any]:
    """Analyze a build.gradle(.kts) to detect the project type.

    Returns:
        {
            "type": "standard" | "compose" | "kmp" | "cmp",
            "has_compose": bool,
            "is_multiplatform": bool,
            "targets": ["android", "ios", "desktop", "web"],
        }
    """
    content = build_gradle_content.lower()

    has_compose = any(
        marker.lower() in content
        for marker in [
            "compose",
            "jetpack compose",
            "org.jetbrains.compose",
            "compose-compiler",
            "compose.ui",
            "androidx.compose",
        ]
    )

    is_kmp = any(
        marker.lower() in content
        for marker in [
            "multiplatform",
            'kotlin("multiplatform")',
            "org.jetbrains.kotlin.multiplatform",
        ]
    )

    is_cmp = "org.jetbrains.compose" in content or "compose.desktop" in content

    targets: List[str] = []
    if "android" in content:
        targets.append("android")
    if "ios" in content or "iosx64" in content or "iosarm64" in content:
        targets.append("ios")
    if "desktop" in content or "jvm" in content:
        targets.append("desktop")
    if "js(" in content or "wasm" in content or "web" in content:
        targets.append("web")

    if is_cmp:
        project_type = "cmp"
    elif is_kmp:
        project_type = "kmp"
    elif has_compose:
        project_type = "compose"
    else:
        project_type = "standard"

    return {
        "type": project_type,
        "has_compose": has_compose,
        "is_multiplatform": is_kmp or is_cmp,
        "targets": targets,
    }
