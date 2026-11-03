# Automatic ventilation — implementation plan

Goal: extend the existing WifiModule integration with Home Assistant demand control, reusing its validated building controller and preserving every existing entity and panel operation.

## Design

- Add an independent HA Automatic/Manual mode, initially Manual. Manual selection sends no HVAC command. Existing manual controls stop HA regulation before sending their command.
- Select actual HA sensor entities through integration options, without hardcoded household IDs. CO₂ uses ppm; TVOC uses ppb (mass concentration is rejected); relative humidity uses %. AQI is optional, explicitly selected, and uses higher-is-worse configurable thresholds; it is not a substitute for measured CO₂/TVOC.
- Normalize each sensor between its configurable target and full-demand threshold; choose the maximum demand across all selected zones/variables. An asymmetric exponential filter, demand hysteresis and continuous rise/fall delays suppress oscillations. Rise can reach the requested speed; fall is one step per confirmed interval.
- Preserve settings and mode in HA config-entry options. Restart clears transient filters/timers and waits for usable sensors plus fresh equipment communication. Missing/stale/invalid selected inputs block reductions; all missing inputs block commands. No zero coercion for unavailable inputs.
- Use the existing API and membership/freshness protection. Automatic commands set manual device mode with a renewable 15-minute lease, renewed every five minutes while healthy. If HA stops, the unchanged vendor schedule resumes after expiry. Manual mode stops lease renewals. Ambiguous command failures stop automatic control until explicit reactivation.
- A final generation guard immediately before the existing API write prevents queued automatic commands after mode/configuration changes. The same controller lock serializes writes.
- Add native configuration/diagnostic entities and a section in the existing panel. UI text remains English/Spanish. No extra package dependencies.

## Tasks

- [x] Demand engine: write failing tests for worst-zone selection, units, non-finite values, filtering, hysteresis, asymmetric timing, partial sensor loss, minimum/maximum limits; implement and run them.
- [x] HA runtime: write failing tests for Manual zero writes, restart warmup, persistent settings, stale readings, command failures, takeover races and lease refresh; implement event/timer lifecycle and unload cleanup.
- [x] UI: add real-entity selectors, editable thresholds/limits, mode and visible diagnostics; preserve widget calls; validate input in backend and translations.
- [x] Local verification: existing/new tests, Python/JavaScript checks, native HA objects/options/lifecycle and package review.
- [ ] Live acceptance: installation on the Raspberry, raw Airzone gas availability and physical equipment response; authenticated HACS browser access is now available.

## Deployment limits

The inspected Airzone installation exposes humidity/AQI but no CO₂/TVOC state entities. No household identifiers are embedded in integration defaults. Raw diagnostics now confirm CO₂/TVOC fields; the adapter, deployed version and physical acceptance must still be verified live.

## Review focus

- Stale timestamps and identical repeated readings must not be confused with valid zero readings.
- Manual takeover must invalidate work already waiting on I/O.
- Unknown API write outcome must not trigger a blind retry.
- Restored mode must not replay an old timer or old demand sample.
- Cloud schedule fallback and physical command acknowledgement must remain visible limitations.

## AirQ gas adapter — confirmed diagnostic follow-up

The supplied diagnostic contains `aq_co2` and `aq_tvoc` for both actual AirQ devices. The core integration discards those fields. Its WebSocket diagnostic cache retains initial full snapshots, so repeated reads of that cache must not masquerade as fresh gas samples.

- Add a read-only adapter inside this same WifiModule integration. Discover real AirQ objects from loaded Airzone Cloud entries and reuse their authenticated client for bounded device-status GET requests (one per AirQ per minute). No separate login, core patch or additional integration.
- Publish CO₂ (ppm), TVOC (ppb) and humidity (%) as native entities named from Airzone's real linked zones. Sensor IDs are assigned by HA, not hardcoded from this household. Keep the existing Airzone CAI entities unchanged.
- Failed/missing measurements, measuring=false or disconnected device state become unavailable. Never fall back to cached initial WebSocket gas snapshots. Use new native entities with the existing demand controller.
- Test extraction, zone matching, no cached replay, numeric/unit bounds, stale/source availability, dynamic discovery and unload. Update the same HACS repository, validate CI, then install the prerelease through the existing HACS UI and inspect real entities before enabling regulation.

## Live acceptance update — 0.3.0b2

- [x] Published through the existing repository; Home Assistant/HACS CI passed.
- [x] Installed with HACS and target configuration check passed.
- [x] Fixed and regression-tested nested frontend module cache invalidation found during upgrade.
- [x] Both AirQs expose changing CO₂/TVOC/humidity readings; actual gas entities selected.
- [x] Saved sensor selections, thresholds and Manual mode survive a real HA restart; existing equipment telemetry remains available.
- [ ] Physical automatic speed changes, active manual takeover, sensor/network outage and lease expiry: deliberately pending while preserving the owner’s active manual-off override.
