# Changelog

## 1.0.0

- First owner-approved community release with native control, sensor-driven regulation, persistent Manual/timed returns, independent bypass and weekly programming in the existing integration.
- Keep cloud machine history optional, label its scope in English/Spanish and report unavailable queries in their own state without implying a failed equipment-control operation. Preserve HA Recorder air-quality graphs and all existing widget/backend operations.
- Include bypass ownership/confirmation and Profiles rendering fixes, real HA restart/timer/programming evidence, normal-release packaging and HACS submission preparation. The vibe coding disclaimer remains in both READMEs.

## 0.6.2

- Fix Profiles failing to open because the active-profile marker referenced an undefined variable. Add a regression exercising the actual panel method with active/inactive profiles and escaped names.

## 0.6.1

- Show reported bypass in Schedule; do not present a saved sensor-Automatic preference as a pending command. Capture current bypass on Manual takeover.
- Bound bypass confirmation to three minutes after a submitted command. Show unconfirmed requests separately and use the same presentation during initial rendering and live refresh.
- Extend acceptance coverage with real HTTP programming round trips and real HA entity-registry migration, preserving existing widget entity IDs. Add an explicit 1.0.0 acceptance checklist.

## 0.6.0

- Integrate Manual speed, timed return and independent bypass with the initial mode controls, before readings and graphs. Retain drafts during unrelated actions.
- Show filter days remaining using the manufacturer’s floor(hours / 24) calculation, add a native days entity and preserve the existing hours entity. Refresh maintenance telemetry with the live panel status.
- Publish normal GitHub releases from canonical X.Y.Z tags after minimum/latest HA, frontend, hassfest and HACS validation. Reject version mismatches and prerelease tags; include a clean install ZIP and SHA256.
- Hide main from HACS downloads to keep installations on versioned releases. This addresses the all-prereleases/commit fallback path; local HACS metadata still needs live verification after migration.
- Add weekly Dependabot updates, pinned actions, scheduled minimum/latest HA tests and an English/Spanish vibe coding disclaimer. Default HACS listing remains deferred until 1.0.0.

## 0.5.0b1

- Select compatible sensors from any HA integration with search, area filtering and unit explanations. Normalize VOC ppm to ppb in regulation and charts.
- Restore optional timed Manual with return to sensor Automatic or vendor Schedule. Absolute deadlines survive restarts; schedule expiry also lives in the cloud.
- Independent bypass preserves sensor Automatic and Manual timers. Retain requested preference and show physical reported state separately.
- Preserve permanent Manual/off, existing widget calls, saved sensors and limits.

## 0.4.0b4

Permanent Manual ownership and saved speed restoration after fresh communication on restart; explicit Schedule release. Verified Manual/off across two real HA restarts.


## 0.4.0b3

Edit sensor device names directly from zone cards with Save/Cancel. Names persist in the Home Assistant device registry without changing entity IDs, history or ventilation settings. The editor survives live reading refreshes, rejects blank names, preserves drafts on errors and supports keyboard use, mobile layouts and English/Spanish.

## 0.4.0b2

Fix confusing command/state presentation: an expired manual-off override no longer preloads Off when fresh equipment telemetry reports a running speed. The slider explicitly prepares a command and does not represent equipment status. Reported off takes precedence over the retained speed register in unit cards; missing fresh equipment/cloud data no longer appears as a current speed in the regulation summary. Manual regulation is explicitly described as pausing HA control, not switching the unit off.

## 0.4.0b1

- Redesigned the existing panel with responsive zone cards, real Home Assistant history charts, Manual/Automatic selection, sliders plus exact values, and checkbox sensor selection. Advanced settings stay in disclosure sections.
- Added optional minimum speed 0 (off); existing minimum 1 and saved settings are preserved. Zero uses the same slow recovery, valid-input, acknowledgement and lease protections.
- Show the existing wifimodule.eu connection explicitly. Credentials already live in the integration; no device LAN address is required. No unverified local transport or offline failover is claimed.
- Added backend and frontend regression checks, including history gaps, stale/restored sensors, escaping and zero persistence. Stable 1.0 hardware acceptance is still pending.

## 0.3.0b2

Fix panel loading after an upgrade by versioning the whole frontend module directory. Relative and nested imports now receive new URLs on every release; old cached translations can no longer break the new regulation controls. Adds a regression covering module URLs across two releases.

## 0.3.0b1

Adds persistent Home Assistant Automatic/Manual demand control using selected CO₂, TVOC, optional humidity/AQI entities. Worst-zone progressive speeds, asymmetric filtering/delays, hysteresis, min/max bounds, native settings/diagnostics and existing-panel configuration. Manual controls take priority. Renewable overrides expire back to the vendor schedule, and uncertain writes stop automatic control. No new hardware, dependencies or hardcoded household entities. Optional AirQ gas adapter reuses the existing Airzone Cloud session to expose native CO₂/TVOC/humidity readings with availability checks. See docs/VALIDATION.md for acceptance evidence.

## 0.2.0b1

First shareable beta: UI discovery and per-building entries, native controls and telemetry, admin panel with profiles/modes/weekly programming/history, protected cloud writes, schedule conflict checks, English/Spanish UI and private diagnostics.

Migrates the earlier single-unit prototype to a building entry without silently approving additional units. Timers use the cloud building timezone. Full authenticated hardware acceptance remains pending; see docs/VALIDATION.md.
