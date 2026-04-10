# ddb — Droid Debug Bridge

A zero-dependency CLI toolkit that bridges AI coding assistants (Claude Code, Copilot, Cursor, etc.) with Android devices and emulators. Build, install, interact with UI, read logs, and debug — all from structured JSON commands an AI can parse reliably.

Supports **standard Android**, **Jetpack Compose**, **Kotlin Multiplatform (KMP)**, and **Compose Multiplatform (CMP)** projects out of the box.

```
pip install ddb-tool
```

## Why?

AI coding assistants can write Android code, but they can't *see* the app running. **ddb** closes that gap: it gives the AI a set of commands to build the app, install it, tap buttons, read the screen, capture logs, and fix bugs — completing the full development loop without leaving the terminal.

## Quick Start

```bash
# Validate all dependencies are in place
ddb doctor
ddb doctor --project ./MyApp      # also check Gradle/build files

# Auto-detect project type (standard / compose / kmp / cmp)
ddb detect --project ./MyApp

# One command: build -> install -> launch (auto-detects module)
ddb run --project ./MyApp --package com.example.myapp

# See what's on screen
ddb screenshot
ddb uidump                         # auto-detects Compose
ddb uidump --mode compose          # force Compose semantics tree
ddb compose-tree                   # dedicated Compose inspection

# Interact with the app
ddb tap-view --text "Sign In"      # find by text (View or Compose)
ddb tap-view --tag "btn_signin"    # find by Compose testTag
ddb tap-view --role "Button"       # find by Compose semantic role
ddb text "user@example.com"
ddb key ENTER

# Wait for Compose recomposition / navigation
ddb wait-for --text "Welcome" --timeout 5
ddb wait-for --tag "home_screen"

# Check for errors
ddb logs --tag MyApp --level E
ddb crash com.example.myapp
```

## Commands

### Device Management
| Command | Description |
|---------|-------------|
| `ddb devices` | List connected devices/emulators |
| `ddb info` | Device details (model, screen, battery, OS) |
| `ddb connect <serial>` | Target a specific device |

### Preflight & Setup
| Command | Description |
|---------|-------------|
| `ddb doctor` | Validate ADB, Java, SDK, device connectivity |
| `ddb doctor --project .` | Also check Gradle wrapper and build files |
| `ddb detect [--project .]` | Auto-detect project type, modules, and package name |
| `ddb init [--project .] [--force]` | Generate `.claude/CLAUDE.md` for Claude Code integration |

`ddb doctor` runs 9 checks — ADB binary, ADB server, platform-tools version (warns if below 30), device connectivity (online/unauthorized/offline per device), Java/JDK, ANDROID_HOME, and optionally Gradle wrapper + build files. Every issue includes a `fix` field with exact commands to resolve it.

`ddb detect` identifies the project type (`standard`, `compose`, `kmp`, `cmp`), finds the Android module (`app`, `composeApp`, `androidApp`), and extracts the package name from Gradle config or AndroidManifest.

`ddb init` auto-generates a `.claude/CLAUDE.md` file tailored to your project. It runs detection first, then produces instructions with the correct package name, module, and Compose-specific or View-specific guidance so Claude Code knows how to use `ddb` for your project. Use `--force` to overwrite an existing file.

### Build & Install
| Command | Description |
|---------|-------------|
| `ddb build [--project .] [--variant debug]` | Build with Gradle (auto-detects module) |
| `ddb install <apk>` | Install APK on device |
| `ddb uninstall <package>` | Uninstall app |
| `ddb launch <package> [activity]` | Start app |
| `ddb stop <package>` | Force-stop app |
| `ddb clear <package>` | Clear app data |

For KMP/CMP projects, `ddb build` auto-detects the correct module (`composeApp`, `androidApp`, etc.) and Gradle task. Override with `--module` if needed.

### UI Inspection & Interaction
| Command | Description |
|---------|-------------|
| `ddb screenshot [path]` | Capture PNG screenshot |
| `ddb uidump [--mode auto\|view\|compose\|both]` | UI hierarchy as JSON |
| `ddb compose-tree [--package X]` | Compose semantics tree with testTags and roles |
| `ddb find --text "Login"` | Find views by text/id/desc |
| `ddb find --tag "btn_login"` | Find by Compose `Modifier.testTag` |
| `ddb find --role "Button"` | Find by Compose semantic role |
| `ddb tap <x> <y>` | Tap coordinates |
| `ddb tap-view --text "Login"` | Find and tap a view |
| `ddb tap-view --tag "btn_login"` | Find by testTag and tap |
| `ddb swipe <x1> <y1> <x2> <y2>` | Swipe gesture |
| `ddb text "hello"` | Type into focused field |
| `ddb key BACK` | Send key event |
| `ddb longpress <x> <y>` | Long press |
| `ddb scroll-down` / `ddb scroll-up` | Scroll one page |
| `ddb wait-for --text "Welcome"` | Wait for a view to appear (with timeout) |

#### UI Inspection Modes

The `--mode` flag controls how the UI is inspected:

- **`auto`** (default) — Uses `uiautomator dump`, but if it detects Compose (`AndroidComposeView`), automatically switches to the accessibility tree for richer data.
- **`view`** — Forces `uiautomator dump`. Best for traditional View-based UIs.
- **`compose`** — Forces `dumpsys accessibility`. Best for Jetpack Compose, as it exposes `testTag`, semantic `role`, state descriptions, and available actions.
- **`both`** — Merges results from both sources. Useful for hybrid View + Compose UIs.

### Logs
| Command | Description |
|---------|-------------|
| `ddb logs [--tag X] [--level E] [--lines 50]` | Filtered logcat |
| `ddb logs-clear` | Clear log buffer |
| `ddb crash <package>` | Crash/ANR traces |

### Debugging
| Command | Description |
|---------|-------------|
| `ddb shell "ls /sdcard"` | Run adb shell command |
| `ddb pull <device_path> <local>` | Pull file from device |
| `ddb push <local> <device_path>` | Push file to device |
| `ddb perms <package>` | List permissions |
| `ddb grant <package> CAMERA` | Grant permission |
| `ddb prefs <package> [name]` | Dump SharedPreferences |
| `ddb db <pkg> <db> "SELECT ..."` | Query SQLite DB |

### Workflows
| Command | Description |
|---------|-------------|
| `ddb run --project . --package com.example.app` | Build + install + launch |
| `ddb validate steps.json` | Run automated UI test sequence |

## JSON Output

Every command returns structured JSON — designed for AI parsing:

```json
{
  "success": true,
  "message": "Found 3 matching view(s)",
  "data": {
    "count": 3,
    "views": [
      {
        "text": "Sign In",
        "resource_id": "com.example:id/btn_signin",
        "test_tag": "btn_signin",
        "role": "Button",
        "center": {"x": 540, "y": 1200},
        "clickable": true,
        "is_compose": true
      }
    ]
  }
}
```

Errors include hints:
```json
{
  "success": false,
  "error": "No views found matching criteria.",
  "hint": "For Compose: ensure views have Modifier.testTag() or Modifier.semantics { }. Try `ddb compose-tree` to inspect."
}
```

## Working with Jetpack Compose

Compose renders through a single `AndroidComposeView`, so traditional `uiautomator` sees limited information. **ddb** handles this by:

1. **Auto-detecting Compose** — `ddb uidump` checks for `AndroidComposeView` and automatically switches to the accessibility tree.
2. **Exposing Compose semantics** — `testTag`, `role`, `stateDescription`, and available actions are all parsed.
3. **testTag-based targeting** — Use `--tag` in `find`, `tap-view`, and `wait-for` for reliable element targeting.

For best results with Compose, add `testTag` modifiers to key interactive elements:

```kotlin
Button(
    onClick = { /* ... */ },
    modifier = Modifier.testTag("btn_login")
) {
    Text("Login")
}

// Also works with semantics
TextField(
    value = email,
    onValueChange = { email = it },
    modifier = Modifier
        .testTag("input_email")
        .semantics { contentDescription = "Email address" }
)
```

## Working with KMP / Compose Multiplatform

**ddb** auto-detects KMP and CMP project structures:

```bash
# Detect project type and layout
ddb detect --project ./MyKmpApp
# Output: {"type": "cmp", "android_module": "composeApp", "package_name": "com.example.app", ...}

# Build auto-detects the right module
ddb build --project ./MyKmpApp
# Equivalent to: ./gradlew :composeApp:assembleDebug

# Or specify explicitly
ddb build --project ./MyKmpApp --module androidApp
```

Common KMP/CMP module conventions:

| Project Type | Typical Android Module | Source Set |
|---|---|---|
| Standard Android | `app` | `src/main/` |
| KMP | `androidApp` | `src/androidMain/` |
| CMP | `composeApp` | `src/androidMain/` |

## UI Test Sequences

Create a `steps.json` file for automated validation:

```json
[
  {"action": "wait", "seconds": 2},
  {"action": "screenshot", "name": "initial"},
  {"action": "tap_view", "test_tag": "btn_login"},
  {"action": "type", "text": "test@example.com"},
  {"action": "keyevent", "key": "TAB"},
  {"action": "type", "text": "password123"},
  {"action": "tap_view", "text": "Sign In"},
  {"action": "wait_for", "test_tag": "home_screen", "timeout": 5},
  {"action": "assert_visible", "text": "Welcome"},
  {"action": "screenshot", "name": "after_login"}
]
```

Run with: `ddb validate steps.json`

## Use with Claude Code

The fastest way to set up Claude Code integration is `ddb init`:

```bash
cd /path/to/your/android/project
ddb init
```

This generates a `.claude/CLAUDE.md` file tailored to your project — with the correct package name, module, and Compose or View-specific instructions. Claude Code reads this file automatically and knows how to use `ddb` for building, testing, and debugging your app.

If you prefer to write the instructions manually, add something like this to your project's `CLAUDE.md`:

```markdown
## Android Development

This project uses `ddb` (Droid Debug Bridge) for device interaction.
Always use `ddb` commands for building, installing, and testing the app.

Device: emulator-5554 (or run `ddb devices` to check)
Package: com.example.myapp

Workflow:
1. Make code changes
2. `ddb run --project . --package com.example.myapp`
3. `ddb screenshot` to verify UI
4. `ddb logs --tag MyApp --level E` to check for errors
5. For Compose UI: `ddb compose-tree` then `ddb tap-view --tag "..."`
6. Wait for navigation: `ddb wait-for --tag "target_screen"`
```

## Requirements

- Python 3.8+
- Android SDK Platform-Tools (`adb` on PATH)
- A connected device or running emulator

## Development

```bash
git clone https://github.com/trackonomysystems/ddb.git
cd ddb
pip install -e ".[dev]"
pytest
```

## License

MIT
