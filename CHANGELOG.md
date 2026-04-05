# Changelog

All notable changes to CallLock AgentOS will be documented in this file.

## [0.1.0.0] - 2026-04-05

### Added
- Dynamic hotkey legend bar showing available keys per stage, toggleable with `?`
- Alt+1-4 cross-stage intent overrides (request bridge/objection responses from any stage without changing state)
- Last-3-keys breadcrumb trail for steering history visibility
- Stage transition flash indicator (green for manual, blue for AI-driven)
- Post-call replay timeline showing all keypresses and stage transitions with timing
- Keypress telemetry in session audit trail for override pattern analysis
- HOTKEY_CONFIG single source of truth in taxonomy.js for all hotkey consumers
- "Also heard" signal badge for burst detection in center panel
- 25 new tests (340 total) covering HOTKEY_CONFIG, composer intent overrides, and replay timeline

### Changed
- Refactored 44-line context-sensitive key handler to 10-line HOTKEY_CONFIG lookup
- Composer accepts cross-stage requestIntent as action payload (not reducer state)
- Legend bar only re-renders on stage change instead of every dispatch

### Removed
- Unused BRIDGE_CARDS constant from ui.js (replaced by HOTKEY_CONFIG)
- Dead NUMERIC_BLOCKED_STAGES export (blocking now implicit via empty config arrays)
