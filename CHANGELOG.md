# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-04-13

### Added

- **Device management:** `devices`, `info`, `connect` commands
- **Preflight checks:** `doctor` with 9 dependency checks (ADB, Java, SDK, device connectivity) and auto-fix hints
- **Project detection:** `detect` auto-identifies standard Android, Jetpack Compose, KMP, and CMP project layouts
- **Build & install:** `build`, `install`, `uninstall`, `launch`, `stop`, `clear` with auto-detected Gradle module
- **UI inspection:** `screenshot`, `uidump` (auto/view/compose/both modes), `compose-tree`, `find` (by text, id, tag, role, desc)
- **UI interaction:** `tap`, `tap-view`, `swipe`, `text`, `key`, `longpress`, `scroll-down`, `scroll-up`, `wait-for`
- **Logs:** `logs` (filtered logcat), `logs-clear`, `crash` trace retrieval
- **Debugging:** `shell`, `pull`, `push`, `perms`, `grant`, `revoke`, `prefs` (SharedPreferences), `db` (SQLite queries)
- **Workflows:** `run` (build+install+launch), `validate` (automated UI test sequences from JSON)
- **Claude Code integration:** `init` generates project-tailored `.claude/CLAUDE.md`
- **Structured JSON output** for all commands with `success`, `data`, `error`, and `hint` fields
- **Auto-preflight** ADB check before every device command

[0.1.0]: https://github.com/diwakar-reddy/Droid-Debug-Bridge/releases/tag/v0.1.0
