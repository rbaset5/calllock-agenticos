# Changelog

All notable changes to CallLock AgentOS will be documented in this file.

## [0.1.4.0] - 2026-04-06

### Added
- State filter buttons on Speed Dial: filter 790 leads by state (MI, TX, IL, FL, AZ)
- "Next 15" batch advance button to skip through leads in groups of 15
- Batch indicator showing current position (Batch N of M)
- Manual keypad tab for dialing arbitrary phone numbers with DTMF support
- Leads sorted by state then score for geographic call batching

### Changed
- Prospects endpoint limit increased from 200 to 1000 to load all call-ready leads

## [0.1.3.1] - 2026-04-06

### Added
- LSA discovery expanded to 8 states: OH, GA, NC added to MI/FL/TX/IL/AZ
- 408 new small-market towns (139 OH, 130 GA, 139 NC) in discovery pipeline
- Full flywheel script chains CID lookup → LSA sweep → export in one run

### Changed
- Ingest review filter loosened from 10-100 to 5-150 reviews (adds ~30% more prospects)
- METRO_FILTERS updated with OH, GA, NC entries for queue builder routing
- State whitelist in `ingest_from_lsa()` expanded to include OH, GA, NC
- Sprint schedule uses individual state codes instead of SE/MW clusters
- Tests updated for individual state sprint schedule (SE→FL, MW→MI, dials 13→11)

## [0.1.3.0] - 2026-04-06

### Added
- Scoring feedback loop: tracks call outcomes to measure which signals predict "interested" prospects
- Bayesian-smoothed signal effectiveness (precision, lift, coverage) per scoring dimension
- Concordance index (AUC proxy) measures how well total_score separates positive from negative outcomes
- Advisory weight suggestions scaled by lift, renormalized to preserve budget
- Website scanner: detects competitor call-tracking and chat widgets via HTML fingerprinting
- `already_served` penalty signal (-15) in dispatch scoring when competitor widget detected
- Supabase migration 067: scoring_feedback table for persisting feedback run results
- CLI entrypoint: `python -m outbound.feedback_loop [--dry-run] [--json]`
- 21 tests for feedback loop, 12 tests for website scanner

### Changed
- `compute_total_score` now clamps to max(0, ...) to handle negative penalty signals
- Discrimination score samples to 500 per class to prevent O(n*m) blowup on large datasets
- HUD review intel panel: fixed double-escaping in signal evidence display

## [0.1.2.0] - 2026-04-05

### Added
- Google review scanner: LLM-powered enrichment extracts dispatch-pain signals from business reviews via SerpAPI
- Desperation scoring (0-100) from review signals, wired into queue builder for priority ordering
- Review Intel section in Sales HUD left rail: opener, signal evidence, desperation badge, owner style hints
- Discord enrichment summary posted after batch scan completes
- Place ID lookup with SQLite caching to avoid redundant SerpAPI credit usage
- Supabase migration 066: review_signals, review_opener, review_enrichment_score, desperation_score columns
- 515 small-market towns across MI/FL/TX/IL/AZ for LSA discovery expansion
- MI added to ingest state filter for sprint calling

### Changed
- Queue builder blends desperation score into learned ranking (15% weight when available)
- CID lookup rate limit increased from 3s to 20s for SerpAPI Starter plan
- Review enrichment is idempotent: re-running subtracts old delta before adding new

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
