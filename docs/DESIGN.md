# Jeremias / WifiModule integration design

Build a reusable community Home Assistant integration, distributable through a HACS custom repository, for normal ventilation operation and the website's programming features. Domain `wifimodule` retains compatibility with the earlier prototype. Minimum supported Home Assistant: 2026.9.0; Python 3.14.

## Architecture and ownership

- One config entry per building, discovered after sign-in; no embedded user IDs, house names, addresses or credentials.
- Group controls reflect the API's actual building-wide scope. Individual units have telemetry devices; adding/removing units requires reconfiguration before group writes resume.
- Async HTTPS API client with isolated in-memory cookies, one authentication refresh after explicit rejection, bounded responses/timeouts and no automatic retries of ambiguous writes.
- A polling coordinator supplies native fan, select, switch, number, button, sensor and binary_sensor entities. Physical telemetry and requested state remain distinct.
- An admin-only HA panel manages modes, profiles and weekly schedules, backed by admin-only WebSocket handlers and the same validated controller used by service actions. Browser never receives WifiModule credentials or cookies.
- All write paths validate membership, IDs, field ranges and freshness where physical control is involved. Schedule writes use a revision check, preserve unaffected days, and enforce the website's 150 transitions/week constraint. No claim of atomic concurrency control: server offers no transaction or ETag.
- Web UI uses local packaged JavaScript, semantic HA theme variables, native labelled controls and Spanish/English. No CDN, copied proprietary frontend or third-party account tracking.

## Functional scope

On/off, seven speeds, automatic/manual/schedule mode, timed manual overrides, timed boost, bypass; per-unit power, speed, errors, filters, sensor readings and last communication; existing cloud history; profile and mode creation/edit/deletion/activation; weekly daily editor and copy-day; configuration export. No commands are sent to the user's live system during development.

Account registration, password resets, unit pairing/ownership transfer and installer calibration/factory reset remain in the manufacturer's website. Installer operations use a separate service-role API and require an exact hardware model; exposing them generically would misrepresent compatibility. This boundary is explicit in the README and parity table, not silently called complete web parity.

## Verification and release

Protocol evidence: actual user status/control captures plus public JS request construction. New API methods are source-confirmed but need authenticated acceptance testing before a stable release. Build as 0.2.0b1, not an official/vendor-supported integration. Test protocol, isolated HTTP authentication, group protection, weekly edits, conflicts, permissions, entities and local UI. Produce source ZIP and installable integration ZIP. Publishing to GitHub and HACS default catalog is a separate final step after a reviewable result exists.
