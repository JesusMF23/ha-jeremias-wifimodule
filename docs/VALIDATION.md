# Validation — 0.3.0b2

5 October 2026. **Published, installed via the existing HACS repository, configured and checked after a real Home Assistant restart. Automatic physical actuation remains pending.**

## Automated evidence

98 tests pass with Python 3.14 and Home Assistant 2026.9.3. The suite includes the 38 original regressions, 50 demand/lifecycle/transport regressions, 9 AirQ bridge checks and one frontend module cache regression. Five dependency deprecation warnings remain; no test failures. Ruff lint/format, Python compilation, all frontend module syntax, Prettier and EN/ES key parity passed.

Real HA ConfigEntry/Coordinator/entity/options classes and local aiohttp transport are used; cloud equipment is mocked. Coverage includes worst-zone demand, asymmetric filtering and delays, hysteresis and bounds, stale/invalid/partial inputs, persistent Manual/error behavior, restart warmup, external-control detection, acknowledgement timeout, renewable override maintenance and cancellation races before transport writes. AirQ coverage includes fresh GETs instead of cached diagnostic snapshots, invalid/disconnected metrics, source reload during a multi-device batch, late discovery and shared poller cancellation on final unload.

Independent review found and verified corrections for transport/control races and an Airzone mid-batch reload. No findings remained in that review scope.

Remote validation on deployed commit `2759bbca399901baddc854476545abbf146d307a`: tests, hassfest and HACS passed. See [the corrective PR checks](https://github.com/JesusMF23/ha-jeremias-wifimodule/pull/2/checks). The preceding feature PR is [#1](https://github.com/JesusMF23/ha-jeremias-wifimodule/pull/1).

## Live installation evidence

- Used the owner's existing authenticated Home Assistant UI and HACS repository. No SSH, new login, additional integration or permission changes.
- Installed 0.3.0b1, then 0.3.0b2 after finding a real frontend cache issue. A version query on panel.js did not invalidate relative imports: old translations broke the new card. Versioning the entire static module directory fixed the issue; a regression verifies distinct nested module URLs across releases.
- Target Home Assistant configuration check succeeded, followed by restart. The corrected panel displayed both original controls and the new regulation settings. No new WifiModule frontend errors were observed after the correction.
- Both physical AirQs exposed CO₂, TVOC and humidity. Values changed between polls and after restart, confirming the adapter reads current status rather than replaying the supplied diagnostic capture.
- Selected both actual gas entity pairs, saved thresholds and bounds, then restarted HA again. Selections, thresholds and Manual mode were retained. Physical recuperator telemetry continued advancing and original controls remained available.
- The recuperator was already under a manual-off override. It remained off; this verification emitted no automatic speed command. No household entity identifiers, raw diagnostic payloads or account information are published in this repository.

The earlier isolated panel harness also verified save/enable/Manual flows, invalid input preservation and retention of an unsaved weekly schedule. Its responses were simulated; those checks do not establish physical actuation.

## Remaining physical acceptance

When the owner chooses to end the manual-off override, enable Automatic and verify actual speed acknowledgement, fast rise/slow fall, active manual takeover, sensor/network loss, HA restart while Automatic and the manufacturer's return to schedule after a 15-minute override expires. These behaviors have automated coverage, but have not all been exercised on this equipment. Mobile and screen-reader acceptance remain untested.

The installation and configuration are complete. Continuous automatic operation and its physical acceptance are deliberately not claimed while the existing manual-off command is being preserved.
