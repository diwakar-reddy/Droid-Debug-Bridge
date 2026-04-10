# Droid Debug Bridge (ddb)

This project is the `ddb` CLI tool — a bridge between AI coding assistants and Android devices/emulators. When working on an Android project that uses `ddb`, follow these instructions.

## Setup

`ddb` must be installed before use. If a `ddb` command fails with "command not found":

```bash
pip install -e /path/to/ddb   # if working within the ddb repo
# OR
pip install ddb-tool           # if installed from PyPI
```

Verify: `ddb --version` should print the version.

Then run the preflight check to validate all dependencies:

```bash
ddb doctor                   # check adb, Java, SDK, device connectivity
ddb doctor --project .       # also check Gradle wrapper and build files
```

This validates: ADB binary + server, platform-tools version (30+ recommended), device connectivity (online vs unauthorized vs offline), Java/JDK, ANDROID_HOME, and optionally Gradle wrapper + build files. Every issue includes a `"fix"` field with exact commands to resolve it.

**ddb also auto-checks** that `adb` is reachable before any device command. If it's missing, you'll get a clear error with install instructions instead of a cryptic failure mid-workflow.

## When to Use ddb

**Always use `ddb` instead of raw `adb` commands** when working on Android projects. `ddb` returns structured JSON that you can parse reliably. Use it for:

- Building and installing the app
- Taking screenshots to verify UI changes
- Inspecting the UI hierarchy to find views
- Tapping buttons, typing text, navigating the app
- Reading logs to debug issues
- Validating that features work end-to-end

## Core Workflow

After making code changes, follow this loop:

```bash
# 1. Build, install, and launch the app
ddb run --project . --package <PACKAGE_NAME>

# 2. Wait for the app to settle (Compose recomposition, animations)
ddb wait-for --text "expected text" --timeout 5
# or
ddb wait-for --tag "screen_tag" --timeout 5

# 3. Take a screenshot to verify the UI
ddb screenshot

# 4. Check for errors
ddb logs --tag <APP_TAG> --level E --lines 30

# 5. If the UI needs interaction:
ddb uidump                            # see what's on screen
ddb tap-view --text "Button Label"    # tap by text
ddb tap-view --tag "compose_test_tag" # tap by Compose testTag
```

## Project Type Detection

Before building, detect the project layout (especially for KMP/CMP):

```bash
ddb detect --project .
```

This tells you the project type (`standard`, `compose`, `kmp`, `cmp`), the Android module name, and the package name. **You don't need to manually specify `--module` for build commands** — `ddb` auto-detects it.

## UI Inspection — Compose vs Views

### Auto mode (recommended)

```bash
ddb uidump
```

This auto-detects whether the app uses Jetpack Compose. If Compose is detected, it switches to the accessibility tree which provides richer data (testTag, role, state).

### Force a specific mode

```bash
ddb uidump --mode view      # traditional View hierarchy (uiautomator)
ddb uidump --mode compose   # Compose semantics via accessibility tree
ddb uidump --mode both      # merge both for hybrid UIs
ddb compose-tree            # dedicated Compose inspection command
```

### Finding views

```bash
# By visible text (works for both View and Compose)
ddb find --text "Login"

# By resource ID (View-based)
ddb find --id "com.example:id/btn_login"

# By Compose testTag (Modifier.testTag)
ddb find --tag "btn_login"

# By Compose semantic role
ddb find --role "Button"

# By content description (accessibility)
ddb find --desc "Login button"

# Combined criteria
ddb find --tag "email_field" --text "Enter email"
```

### Tapping views

```bash
# By text
ddb tap-view --text "Submit"

# By Compose testTag — most reliable for Compose UIs
ddb tap-view --tag "btn_submit"

# By coordinates (from uidump or screenshot analysis)
ddb tap 540 1200
```

### Waiting for views (important for Compose)

Compose recomposition is async. After navigation or state changes, wait for the target to appear:

```bash
ddb wait-for --text "Welcome" --timeout 10
ddb wait-for --tag "home_screen" --timeout 5
```

## Text Input

```bash
# Type text into the currently focused field
ddb text "hello@example.com"

# Send key events
ddb key ENTER
ddb key BACK
ddb key TAB
ddb key DELETE
```

## Scrolling

```bash
ddb scroll-down
ddb scroll-up
ddb swipe 540 1500 540 500 --duration 400   # custom swipe
```

## Logs and Debugging

```bash
# Filtered logcat
ddb logs --tag MyAppTag --level E --lines 50
ddb logs --package com.example.myapp --grep "Exception"

# Clear logs before a test run
ddb logs-clear

# Get crash traces
ddb crash com.example.myapp

# Run arbitrary shell commands
ddb shell "dumpsys activity top"
ddb shell "pm list packages | grep example"

# Inspect app data (debug builds only)
ddb prefs com.example.myapp                    # list SharedPreferences files
ddb prefs com.example.myapp my_prefs           # dump specific prefs
ddb db com.example.myapp app.db "SELECT * FROM users LIMIT 5"

# Permissions
ddb perms com.example.myapp
ddb grant com.example.myapp CAMERA
ddb revoke com.example.myapp LOCATION
```

## Automated UI Test Sequences

Create a `steps.json` to validate a flow:

```json
[
  {"action": "wait", "seconds": 2},
  {"action": "screenshot", "name": "01_initial"},
  {"action": "tap_view", "tag": "btn_login"},
  {"action": "type", "text": "user@test.com"},
  {"action": "keyevent", "key": "TAB"},
  {"action": "type", "text": "password123"},
  {"action": "tap_view", "text": "Sign In"},
  {"action": "wait_for", "tag": "home_screen", "timeout": 5},
  {"action": "assert_visible", "text": "Welcome"},
  {"action": "screenshot", "name": "02_logged_in"},
  {"action": "logs", "tag": "AuthManager", "level": "E", "lines": 10}
]
```

Run with: `ddb validate steps.json`

## Building for Different Project Types

### Standard Android
```bash
ddb build --project . --variant debug
# Runs: ./gradlew :app:assembleDebug
```

### Jetpack Compose (same build, different UI inspection)
```bash
ddb build --project .
# Build is the same — the difference is in UI inspection:
ddb uidump --mode compose   # or just `ddb uidump` (auto-detects)
```

### KMP (Kotlin Multiplatform)
```bash
ddb build --project .
# Auto-detects :androidApp:assembleDebug

# Or explicit:
ddb build --project . --module androidApp
```

### CMP (Compose Multiplatform)
```bash
ddb build --project .
# Auto-detects :composeApp:assembleDebug

# Or explicit:
ddb build --project . --module composeApp
```

## Full Feature Validation Workflow

When implementing a new feature end-to-end:

```bash
# 1. Detect project setup
ddb detect --project .

# 2. Build and deploy
ddb run --project . --package com.example.myapp

# 3. Navigate to the feature
ddb wait-for --text "Home" --timeout 10
ddb tap-view --tag "nav_settings"       # or --text "Settings"
ddb wait-for --tag "settings_screen"

# 4. Interact with the feature
ddb tap-view --tag "toggle_dark_mode"
ddb screenshot dark_mode_on.png

# 5. Verify the result
ddb find --tag "theme_label"            # check the label changed
ddb logs --tag ThemeManager --lines 10  # check for errors

# 6. Test edge cases
ddb key BACK
ddb wait-for --tag "home_screen"
ddb screenshot back_navigation.png
```

## Tips

- **Always screenshot after interactions** — this is how you "see" the app.
- **Use `wait-for` after navigation** — Compose recomposition and fragment transitions take time.
- **Prefer `--tag` over `--text` for Compose** — testTags are stable across locales and don't break when copy changes.
- **Clear logs before testing** (`ddb logs-clear`) to avoid noise from previous runs.
- **Use `ddb detect`** at the start of a session to understand the project layout.
- All `ddb` output is JSON. Parse the `"success"` field to know if a command worked, and check `"hint"` in errors for suggested fixes.
- When a device isn't responding, run `ddb devices` first to verify connectivity.
