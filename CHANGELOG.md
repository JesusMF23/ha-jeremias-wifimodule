# Changelog

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
