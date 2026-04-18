"""Tests for the parser utilities — these don't require adb or a device."""

from ddb.utils.parser import (
    detect_compose_in_hierarchy,
    detect_project_type,
    parse_accessibility_tree,
    parse_getprop,
    parse_logcat_line,
    parse_recomposition_stats,
    parse_ui_hierarchy,
)

# ------------------------------------------------------------------
# UI Hierarchy (uiautomator)
# ------------------------------------------------------------------

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example" content-desc="" checkable="false" checked="false"
        clickable="false" enabled="true" focusable="false" focused="false"
        scrollable="false" long-clickable="false" password="false" selected="false"
        bounds="[0,0][1080,1920]">
    <node index="0" text="Hello World" resource-id="com.example:id/greeting"
          class="android.widget.TextView" package="com.example" content-desc=""
          checkable="false" checked="false" clickable="true" enabled="true"
          focusable="true" focused="false" scrollable="false" long-clickable="false"
          password="false" selected="false" bounds="[100,200][500,300]" />
    <node index="1" text="" resource-id="com.example:id/btn_ok"
          class="android.widget.Button" package="com.example" content-desc="OK button"
          checkable="false" checked="false" clickable="true" enabled="true"
          focusable="true" focused="false" scrollable="false" long-clickable="false"
          password="false" selected="false" bounds="[200,400][800,500]" />
  </node>
</hierarchy>
"""


def test_parse_ui_hierarchy_basic():
    nodes = parse_ui_hierarchy(SAMPLE_XML)
    assert len(nodes) == 4  # hierarchy root + FrameLayout + TextView + Button


def test_parse_ui_hierarchy_text_node():
    nodes = parse_ui_hierarchy(SAMPLE_XML)
    text_node = next(n for n in nodes if n["text"] == "Hello World")
    assert text_node["resource_id"] == "com.example:id/greeting"
    assert text_node["class"] == "android.widget.TextView"
    assert text_node["clickable"] is True
    assert text_node["center"] == {"x": 300, "y": 250}
    assert text_node["bounds"] == {"left": 100, "top": 200, "right": 500, "bottom": 300}


def test_parse_ui_hierarchy_content_desc():
    nodes = parse_ui_hierarchy(SAMPLE_XML)
    btn = next(n for n in nodes if n["content_desc"] == "OK button")
    assert btn["resource_id"] == "com.example:id/btn_ok"
    assert btn["center"] == {"x": 500, "y": 450}


def test_parse_ui_hierarchy_invalid_xml():
    nodes = parse_ui_hierarchy("not xml at all")
    assert nodes == []


def test_parse_ui_hierarchy_empty():
    nodes = parse_ui_hierarchy('<hierarchy rotation="0"></hierarchy>')
    assert len(nodes) == 1  # hierarchy root itself


# ------------------------------------------------------------------
# Compose detection in uiautomator
# ------------------------------------------------------------------

COMPOSE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" bounds="[0,0][1080,1920]">
    <node class="androidx.compose.ui.platform.AndroidComposeView"
          bounds="[0,0][1080,1920]">
      <node text="Hello Compose" bounds="[100,200][500,300]" />
    </node>
  </node>
</hierarchy>
"""


def test_detect_compose_in_hierarchy_true():
    assert detect_compose_in_hierarchy(COMPOSE_XML) is True


def test_detect_compose_in_hierarchy_false():
    assert detect_compose_in_hierarchy(SAMPLE_XML) is False


# ------------------------------------------------------------------
# Accessibility tree parsing (for Compose)
# ------------------------------------------------------------------

SAMPLE_A11Y = """
  android.view.accessibility.AccessibilityNodeInfo@1a2b3c;
    boundsInParent: Rect(0, 0 - 1080, 1920); boundsInScreen: Rect(0, 0 - 1080, 1920);
    packageName: com.example; className: android.widget.FrameLayout;
    text: null; contentDescription: null;
    actions: [ACTION_FOCUS, ACTION_ACCESSIBILITY_FOCUS]

  android.view.accessibility.AccessibilityNodeInfo@4d5e6f;
    boundsInParent: Rect(100, 200 - 500, 300); boundsInScreen: Rect(100, 200 - 500, 300);
    packageName: com.example; className: android.view.View;
    text: Hello Compose; contentDescription: greeting;
    viewIdResourceName: com.example:id/greeting; clickable;
    extras: [TestTag=greeting_text, Role=Button]
"""


def test_parse_accessibility_tree_basic():
    nodes = parse_accessibility_tree(SAMPLE_A11Y)
    assert len(nodes) == 2


def test_parse_accessibility_tree_compose_fields():
    nodes = parse_accessibility_tree(SAMPLE_A11Y)
    compose_node = next(n for n in nodes if n["text"] == "Hello Compose")
    assert compose_node["content_desc"] == "greeting"
    assert compose_node["test_tag"] == "greeting_text"
    assert compose_node["role"] == "Button"
    assert compose_node["is_compose"] is True
    assert compose_node["center"] == {"x": 300, "y": 250}
    assert compose_node["clickable"] is True


def test_parse_accessibility_tree_bounds():
    nodes = parse_accessibility_tree(SAMPLE_A11Y)
    root = nodes[0]
    assert root["bounds"] == {"left": 0, "top": 0, "right": 1080, "bottom": 1920}
    assert root["center"] == {"x": 540, "y": 960}


def test_parse_accessibility_tree_empty():
    nodes = parse_accessibility_tree("")
    assert nodes == []


# ------------------------------------------------------------------
# Project type detection
# ------------------------------------------------------------------


def test_detect_standard_project():
    content = """
    plugins {
        id 'com.android.application'
        id 'org.jetbrains.kotlin.android'
    }
    android {
        namespace "com.example.app"
        compileSdk 34
    }
    """
    result = detect_project_type(content)
    assert result["type"] == "standard"
    assert result["has_compose"] is False
    assert result["is_multiplatform"] is False


def test_detect_compose_project():
    content = """
    plugins {
        id 'com.android.application'
        id 'org.jetbrains.kotlin.android'
    }
    android {
        namespace "com.example.app"
        buildFeatures {
            compose true
        }
    }
    dependencies {
        implementation "androidx.compose.ui:compose-ui:1.5.0"
    }
    """
    result = detect_project_type(content)
    assert result["type"] == "compose"
    assert result["has_compose"] is True
    assert result["is_multiplatform"] is False


def test_detect_kmp_project():
    content = """
    plugins {
        id("org.jetbrains.kotlin.multiplatform")
        id("com.android.library")
    }
    kotlin {
        androidTarget()
        iosX64()
        iosArm64()
    }
    """
    result = detect_project_type(content)
    assert result["type"] == "kmp"
    assert result["is_multiplatform"] is True
    assert "android" in result["targets"]
    assert "ios" in result["targets"]


def test_detect_cmp_project():
    content = """
    plugins {
        id("org.jetbrains.compose")
        id("org.jetbrains.kotlin.multiplatform")
        id("com.android.application")
    }
    kotlin {
        androidTarget()
        jvm("desktop")
        wasmJs()
    }
    compose.desktop {
        application { }
    }
    """
    result = detect_project_type(content)
    assert result["type"] == "cmp"
    assert result["has_compose"] is True
    assert result["is_multiplatform"] is True
    assert "android" in result["targets"]
    assert "desktop" in result["targets"]
    assert "web" in result["targets"]


# ------------------------------------------------------------------
# Recomposition stats
# ------------------------------------------------------------------


def test_parse_recomposition_stats():
    log = """
    04-09 12:00:00.000  1234  5678 D Recomposition HomeScreen count=15 skipped=3
    04-09 12:00:01.000  1234  5678 D Recomposition LoginButton count=8 skipped=5
    some other log line
    """
    stats = parse_recomposition_stats(log)
    assert len(stats) == 2
    assert stats[0]["composable"] == "HomeScreen"
    assert stats[0]["recomposition_count"] == 15
    assert stats[0]["skipped"] == 3


# ------------------------------------------------------------------
# Logcat
# ------------------------------------------------------------------


def test_parse_logcat_line_valid():
    line = "04-09 12:34:56.789  1234  5678 E MyTag   : Something went wrong"
    result = parse_logcat_line(line)
    assert result is not None
    assert result["level"] == "E"
    assert result["tag"] == "MyTag"
    assert result["message"] == "Something went wrong"
    assert result["pid"] == "1234"


def test_parse_logcat_line_info():
    line = "04-09 10:00:00.000   999  1000 I ActivityManager: Start proc com.example"
    result = parse_logcat_line(line)
    assert result["level"] == "I"
    assert result["tag"] == "ActivityManager"


def test_parse_logcat_line_invalid():
    assert parse_logcat_line("random garbage") is None
    assert parse_logcat_line("") is None


# ------------------------------------------------------------------
# Getprop
# ------------------------------------------------------------------

SAMPLE_GETPROP = """[ro.product.model]: [Pixel 6]
[ro.build.version.sdk]: [33]
[ro.product.manufacturer]: [Google]
[ro.build.display.id]: [TP1A.220624.014]
"""


def test_parse_getprop():
    props = parse_getprop(SAMPLE_GETPROP)
    assert props["ro.product.model"] == "Pixel 6"
    assert props["ro.build.version.sdk"] == "33"
    assert props["ro.product.manufacturer"] == "Google"


def test_parse_getprop_empty():
    assert parse_getprop("") == {}


# ------------------------------------------------------------------
# Compose node enrichment (_enrich_compose_nodes from ui module)
# ------------------------------------------------------------------

COMPOSE_UI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example" content-desc="" checkable="false" checked="false"
        clickable="false" enabled="true" focusable="false" focused="false"
        scrollable="false" long-clickable="false" password="false" selected="false"
        bounds="[0,0][1080,1920]">
    <node index="0" text="" resource-id="" class="androidx.compose.ui.platform.AndroidComposeView"
          package="com.example" content-desc="" checkable="false" checked="false"
          clickable="false" enabled="true" focusable="false" focused="false"
          scrollable="false" long-clickable="false" password="false" selected="false"
          bounds="[0,0][1080,1920]">
      <node index="0" text="Login" resource-id="btn_login"
            class="android.widget.Button" package="com.example" content-desc=""
            checkable="false" checked="false" clickable="true" enabled="true"
            focusable="true" focused="false" scrollable="false" long-clickable="false"
            password="false" selected="false" bounds="[100,200][300,280]" />
      <node index="1" text="" resource-id="input_email"
            class="android.widget.EditText" package="com.example"
            content-desc="Email address" checkable="false" checked="false"
            clickable="true" enabled="true" focusable="true" focused="false"
            scrollable="false" long-clickable="false" password="false" selected="false"
            bounds="[50,300][500,380]" />
      <node index="2" text="Hello World" resource-id="com.example:id/legacy_view"
            class="android.widget.TextView" package="com.example" content-desc=""
            checkable="false" checked="false" clickable="false" enabled="true"
            focusable="false" focused="false" scrollable="false" long-clickable="false"
            password="false" selected="false" bounds="[50,400][500,450]" />
    </node>
  </node>
</hierarchy>"""


def test_enrich_compose_nodes():
    """Verify that _enrich_compose_nodes adds testTag, role, and is_compose."""
    from ddb.modules.ui import _enrich_compose_nodes

    nodes = parse_ui_hierarchy(COMPOSE_UI_XML)
    _enrich_compose_nodes(COMPOSE_UI_XML, nodes)

    # Find the button node (text="Login", resource-id="btn_login")
    btn = [n for n in nodes if n.get("text") == "Login"][0]
    assert btn["is_compose"] is True
    assert btn["test_tag"] == "btn_login"  # testTag from resource-id (no :id/)
    assert btn["role"] == "Button"  # inferred from android.widget.Button

    # Find the EditText node (resource-id="input_email")
    edit = [n for n in nodes if n.get("content_desc") == "Email address"][0]
    assert edit["is_compose"] is True
    assert edit["test_tag"] == "input_email"
    assert edit["role"] == "TextField"

    # The node with com.example:id/legacy_view should NOT have test_tag
    # (it's a View resource-id format, not a Compose testTag)
    legacy = [n for n in nodes if "legacy_view" in n.get("resource_id", "")][0]
    assert legacy["is_compose"] is True  # still under ComposeView subtree
    assert legacy["test_tag"] == ""  # contains :id/ so not a testTag

    # FrameLayout outside ComposeView should not be Compose
    frame = [n for n in nodes if n.get("class") == "android.widget.FrameLayout"][0]
    assert frame["is_compose"] is False
