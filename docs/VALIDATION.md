# Validation — 0.3.0b1

Date: 5 October 2026. Status: **local experimental prerelease; target installation and physical acceptance pending**. No live HVAC command, account mutation or installation was performed while implementing this extension.

## Automated checks

- Python 3.14, Home Assistant 2026.9.3. **97 tests passed** (38 existing tests, 50 demand/lifecycle/transport regressions, 9 AirQ adapter tests). Five dependency deprecation warnings, no test failures.
- Actual localhost aiohttp transport/cookie behavior; actual Home Assistant state, ConfigEntry, Coordinator, entity and OptionsFlow classes. Cloud equipment remains mocked. HA option disk updates are mocked; restart reconstruction uses the saved options object.
- Covers worst normalized zone/variable, rejected units and non-finite/stale data, filter elapsed time and settling to minimum, asymmetric delays, hysteresis, bounds, partial-data behavior, Manual zero writes, persistent errors, restart warmup, physical acknowledgement timeout, external schedule changes, lease renewal during long falls and native options when cloud startup failed.
- Race regressions cover cancellation after controller polling, during API lock wait and after explicit auth rejection; unknown write failures when sensors/configuration change; successful in-flight command tracking; minimum interval retention after edits; fresh physical speed/fault/boost revalidation; timer stop and non-overlap.
- Ruff lint/format, Python compilation, every frontend JavaScript module's syntax, Prettier, JSON validity and English/Spanish translation-key parity passed.
- Final independent verification confirmed both last corrections and the original 88-test suite; no findings remained within that verification scope.

## UI checks

Local `http://127.0.0.1:8766/`, actual panel modules, fictional demonstration data and mocked HA WebSocket responses. No vendor calls.

| Check | Result |
|---|---|
| Page identity / meaningful content / no error overlay | Pass |
| Save selected CO₂ and TVOC sensors, objective 850 ppm | Pass; visible outgoing configuration matches |
| Enable Automatic | Pass; worst-zone diagnosis, reported/target speed and wait shown |
| Return to Manual | Pass; only `enabled:false` requested |
| Preserve unsaved weekly schedule through Manual action | Pass; row remains 09:00; navigation requests discard confirmation |
| Reject invalid target above full threshold | Pass in simulated backend; typed 2000 remains in draft |
| Console | No application errors/warnings in inspected run |
| Visual inspection | Desktop screenshot inspected; no clipping in shown control section |

The in-app browser's native confirmation dialog timed out. Subsequent testing used Brave through the same computer-use API and a test-only confirmation callback returning Cancel; this verifies the panel's draft state and confirmation invocation, not browser-native dialog interaction. No callback override exists in the shipped integration. Mobile, screen-reader and real HA frontend acceptance remain untested.

## Distribution

Version constants and manifest agree at 0.3.0b1. The local install archive contains only the component, license and installation notes, excluding tests, repository metadata, caches and household fixtures. No hardcoded household entity IDs or credentials are present in component defaults. This version has not been pushed, released or validated by remote hassfest/HACS CI. Historical CI results from 0.2.0b1 are not claimed for this version.

## Target-installation acceptance still required

1. Publish a prerelease of the existing HACS repository, install its update through HACS, preserve the existing integration entry, check configuration and restart. Check logs and confirm native controls/widget still operate.
2. The supplied diagnostic confirms raw aq_co2/aq_tvoc/humidity fields. Core omits the gas entities. Validate the new read-only device-status adapter against live responses; unit fixtures cover cached-data rejection, failed/disconnected measurements, source reload, late discovery and shared polling/unload cancellation. No household diagnostic data is shipped.
3. Select verified entities/units and reasonable thresholds. Check that all selected sensors continue reporting at the configured freshness interval.
4. With the owner present, enable Automatic and compare cloud acknowledgement with physical speed telemetry. Confirm actual fast rise/slow fall, limits, Manual takeover and existing widget priority.
5. Verify HA restart, sensor/network loss, ambiguous-write diagnosis, external control and the vendor's 15-minute lease expiry/return to schedule on this specific equipment. Restore the desired operating mode after testing.

The new regulation is implemented and locally tested. These pending steps prevent calling the requested end-to-end installation complete.
