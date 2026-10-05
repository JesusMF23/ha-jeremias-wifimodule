# Changelog

## 0.3.0b1

Adds persistent Home Assistant Automatic/Manual demand control using selected CO₂, TVOC, optional humidity/AQI entities. Worst-zone progressive speeds, asymmetric filtering/delays, hysteresis, min/max bounds, native settings/diagnostics and existing-panel configuration. Manual controls take priority. Renewable overrides expire back to the vendor schedule, and uncertain writes stop automatic control. No new hardware, dependencies or hardcoded household entities. Optional AirQ gas adapter reuses the existing Airzone Cloud session to expose native CO₂/TVOC/humidity readings with availability checks. See docs/VALIDATION.md for acceptance evidence.

## 0.2.0b1

First shareable beta: UI discovery and per-building entries, native controls and telemetry, admin panel with profiles/modes/weekly programming/history, protected cloud writes, schedule conflict checks, English/Spanish UI and private diagnostics.

Migrates the earlier single-unit prototype to a building entry without silently approving additional units. Timers use the cloud building timezone. Full authenticated hardware acceptance remains pending; see docs/VALIDATION.md.
