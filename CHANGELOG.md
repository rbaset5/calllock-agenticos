# Changelog

All notable changes to CallLock AgentOS will be documented in this file.

## [0.1.1.1] - 2026-04-05

### Fixed
- Bridge stage now shows its own line instead of repeating the opener question
- Fixed render crash when advancing to BRIDGE (typo: `competition.competitor` should be `competition.firstResponder` in `linesForStage`)
- New calls no longer reset the HUD mid-conversation (CALL_STARTED guard rejects duplicates and mid-call resets)
- BOOKED calls no longer permanently lock the HUD (added to resettable stages since BOOKED never transitions to ENDED)

### Changed
- Bridge fallback line differentiated from opener: "What does it cost you when one of those calls slips through the cracks?"

## [0.1.1.0] - 2026-04-05

### Fixed
- Transcript health badge now clears between calls (was leaking TRANSCRIPT LAG into the next prospect)
- Added 15-second TRANSCRIPT OFFLINE escalation with red badge and manual-mode lock per spec Section 32
- Rounds and round index now reset on new call (was bleeding previous prospect's round history)
- END_CALL reducer action now clears activeObjection (was persisting stale objection data in session snapshots)
- SET_TURN_ANALYSIS now validates callSid to prevent cross-call state corruption
- AUTO_SET_STAGE now validates stage value against STAGES array

### Added
- Session save coordinator for atomic end-of-call persistence (cancels stale saves when outcome arrives first)
- Heartbeat watchdog (6.5s timeout) with automatic call finalization on connection loss
- Regression test for END_CALL + activeObjection cleanup (345 total tests)

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
