# Jeremias HACS Implementation Plan

**Goal:** Generalize the prototype into a reusable native HA integration with a schedule-management panel.
**Architecture:** Async API, validated controller, polling coordinator, native entities and admin panel. One building per entry, multiple unit sensors.
**Tech stack:** Python 3.14, Home Assistant 2026.9, aiohttp, voluptuous, Web Components, pytest.
**Spec:** DESIGN.md.

## Constraints and review focus

No hardcoded personal data; no live device mutations; HTTPS credentials server-side only; en/es parity; no optimistic physical state. Test mixed-unit state, session expiry, stale schedule edits, foreign IDs and unload/reload behavior.

- [x] Protocol and controller: `api.py`, `models.py`, `controller.py`; tests for discovery, bounds, scope, cookies, profile/mode CRUD and schedule revision safety. Read exact public request constructions documented in PROTOCOL.md. A day must start at 00:00, times increase, every mode belongs to selected building, total week <=150. Snapshot hash mismatch must abort before POST.
- [x] HA lifecycle and native entities: config flow discovers building and units, migration preserves old entry identity, unload releases listeners/session; fan controls building, unit telemetry reports unknown for invalid sensor values; all commands route through controller.
- [x] Admin panel: scoped WebSocket endpoint, schedule editor, profiles and modes forms, history and export. No arbitrary API passthrough. Non-admin request must fail before a network call. Panel render uses escaped text and fixed operations only.
- [x] Distribution: HACS metadata, CI, diagnostics redaction, translations, original neutral icon, README, protocol/parity documentation and source/install ZIPs. Run pytest, compile/static checks and UI smoke tests; independent final review before reporting readiness.

Implementation complete for the beta scope. Authenticated equipment acceptance and full real HA installation/migration remain pending in VALIDATION.md; checked tasks do not imply production certification.
