# Jeremias / WifiModule integration design

Build a reusable community Home Assistant integration, distributable through a HACS custom repository, for normal ventilation operation and the website's programming features. Domain `wifimodule` retains compatibility with the earlier prototype. Minimum supported Home Assistant: 2026.9.0; Python 3.14.

## Architecture and ownership

- One config entry per building, discovered after sign-in; no embedded user IDs, house names, addresses or credentials.
- Timezone names remain strings in config entries. Setup and configuration flows resolve them with `dt_util.async_get_time_zone`; the controller receives the resolved `tzinfo` and performs no timezone file lookup. Unknown names prevent setup/configuration rather than falling back to the host's timezone.
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


## Sensor demand extension (0.3.0b1)

`demand.py` contains a deterministic, I/O-free demand/filter/timing engine. `automatic.py` owns HA state reads, config-entry persistence, diagnostics, lifecycle and guarded lease writes through the existing Controller/API. Options and native entities expose the same validated settings; the existing panel adds a separate regulation section. Cancellation guards reach the serialized API immediately before each write attempt, including reauthentication. Commands from existing manual surfaces pause regulation first. See [behavior](AUTOMATIC_CONTROL.md) and [acceptance](VALIDATION.md).

## Dashboard and optional switch-off (0.4.0b1)

The existing cloud transport remains the only implemented transport: HTTPS to
wifimodule.eu using the config entry's credentials. A changed LAN address of the
ventilation unit does not change that URL. Local control/offline failover is not
claimed; it requires an independently verified device protocol. The dashboard
shows cloud reachability separately from equipment freshness.

`panel_sensors.py` supplies registered device names, units and readings validated
with the same freshness/range rules as regulation. `dashboard.js` renders zone
cards and selected entities' Recorder history (6 h / 24 h / 7 d) through HA's
existing authenticated frontend client. Unknown states break the step charts;
no gas values are derived from the categorical AQI. History failure never affects
control. Period/entry request revisions discard late history responses.

The packaged UI uses reusable setting rows (range plus exact integer input),
checkbox sensor groups, disclosure sections and a Manual/Automatic selector.
Settings require Save; changing the mode does not save unfinished edits. Slider
movement does not send equipment commands; Apply retains the existing control
path. Themes, keyboard labels, reduced motion, responsive layout and EN/ES text
are retained. All assets share the existing versioned static path.

Minimum speed now accepts 0 without migrating existing configurations away from
1. Zero means physical off; valid sustained zero demand, slow fall confirmation,
command acknowledgement and finite renewable leases still apply. Invalid input
never authorizes a reduction or renews an off command. Physical off/restart
acceptance remains required before declaring 1.0.0 stable.

## Editable sensor names (0.4.0b3)

Zone cards expose an Edit name action only when a registered device exists. A
small shared dialog module uses HA's admin-only device-registry update command,
changing only name_by_user. The native registry persists names across restarts;
entity identifiers, history, Airzone links and ventilation settings are untouched.
The dialog lives outside periodically replaced cards. Save validates a trimmed
1–100 character name, blocks duplicate submissions and retains the draft on error.
Cancel/Escape discards an unsaved edit. Focus returns to the matching card.


## Persistent manual ownership (0.4.0b4)

ManualControl isolates persistent manual intent from sensor demand. It sends a single non-expiring command after fresh telemetry, verifies acknowledgement and restores saved speed on restart. Explicit schedule release clears ownership. Uncertain writes or external changes clear restoration intent; no blind retries. Generation guards cancel superseded writes before transmission. Normal manual UI hides irrelevant duration; temporary boost/device-auto controls retain it.

## Flexible controls (0.5.0b1)

ManualControl persists an absolute UTC deadline and explicit return destination. Schedule returns serialize the same deadline on cloud restore; Automatic returns keep the cloud manual hold until HA can resume demand control. Invalid/uncertain commands do not create replay intent. Bypass-only commands retain mode and manual deadline; Automatic bypass changes use guarded finite leases and subsequent speed commands carry the saved preference. Fresh report is distinct from requested bypass.

Sensor catalogues use HA device classes/units rather than brands, include area names for selection and explain unsupported units. VOC ppm is normalized to ppb in both demand calculation and history display; no mass-to-molar inference is made. Browser control-options owns timer presentation/validation; backend validates requests independently.

## Integrated controls and release maintenance (0.6.0)

The initial regulation card owns the Manual editor (speed, native mode and timed return), plus one independent bypass control. The editor is visible in HA Manual before sensor cards/charts, including when another programming tab is selected. Drafts survive bypass requests; Apply sends the explicit draft through the existing backend and widget-compatible command path. `manual-controls.js` and `machine-status.js` keep presentation separate from panel lifecycle. Equipment/maintenance follows charts; its telemetry refreshes from the existing live status response, without extra cloud metadata reads.

`filter_days_remaining` derives floor(fil / 24), confirmed in the vendor’s public index-Nhn3YcyL.js display. Negative/missing/noninteger counters stay unknown. The hours entity keeps its identity and raw reading; no assumed installation date or service interval is introduced.

The normal-release channel uses canonical X.Y.Z tags matched to manifest/VERSION. A tag invokes the reusable validation workflow (minimum/latest HA, frontend, hassfest, HACS) before publishing an install ZIP/checksum as a normal GitHub release. Main is hidden from HACS downloads. No changes to HACS internals or its stored installation state are made. Weekly dependency PRs, pinned Actions and scheduled compatibility checks maintain the repo; the HACS default-catalogue request remains deferred until 1.0.0.

## Bypass ownership (0.6.1)

Saved Automatic bypass preference is not an active Schedule request. Snapshots expose an effective request only while HA owns Automatic/Manual. Manual takeover captures fresh reported bypass with speed instead of replaying a prior preference. A mismatch is pending only for 180 seconds after an actual command timestamp; afterward it is explicitly unconfirmed. A shared frontend presentation function handles initial render and polling consistently. Preference persistence, finite Automatic leases and independent Manual deadlines remain unchanged.
