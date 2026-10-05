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

## 0.4.0b1 dashboard / zero minimum

- Python suite: 102 passing, including zero demand slow switch-off, rise from zero,
  missing-input protection, zero acknowledgement/renewal/manual takeover and
  persistence. Catalogue tests cover registered names, incompatible units,
  stale and restored readings.
- Frontend tests: 8 passing for steps/gaps/zero, escaped names, checkbox
  selection, zero input, translation parity and long retained histories. Lifecycle
  regressions cover null manual setpoints and late-history responses on reconnect.
- Isolated browser: checkbox save and min=0 payload checked; moving the manual
  slider sends no command, Apply submits speed=0 through the unchanged operation.
  At 390 px, content width equals viewport with no horizontal overflow. Range and
  exact numeric values match, including TVOC full-demand 1000.
- Live deployment and physical actuation evidence are recorded separately. These
  simulated checks are not physical acceptance of automatic on/off or cloud loss.

### Live 0.4.0b1 update

Installed release 0.4.0b1 through the existing HACS repository. The target HA
configuration check passed, and HA restarted successfully with no scripts or
automations running at the restart prompt. The new panel loaded in the user's dark
theme, grouped both real AirQ devices correctly, displayed changing measurements,
and loaded actual Recorder charts plus min/max/last values. The 6-hour period
selector worked. Saved Manual mode, four gas entities, thresholds and minimum 1 /
maximum 7 remained intact; the minimum control now exposes lower bound 0.
No live fan/control/automatic-enable command was issued during this update.


## 0.4.0b2 state versus command

Observed a schedule-controlled building with manual_active=false, retained
manual_speed=0 and fresh reported pwr=1/spe=4. The old UI presented the inactive
manual selection as Off; the reported speed itself follows the equipment
registers. Regression tests reproduce the expired-off selection, preserve active
commands distinct from reported state, hide stale speed summaries, and show Off
for pwr=0 even when spe retains a previous level. 105 Python and 11 frontend
tests pass. No live equipment command was used to manufacture a matching state.
The user's physical-off observation is not disproved by cloud telemetry; an
independent local indication is still needed if the device and cloud disagree.

### Live 0.4.0b2 update

Installed the exact 0.4.0b2 prerelease through HACS. The HA configuration check
passed and the restart confirmation reported no active scripts or automations.
After restarting and reloading the browser, the new labels appeared and Manual
regulation was preserved. During initial heartbeat warmup, the reported speed was
hidden; after communication advanced, it showed 4. Refreshing the panel selected
4 in the clearly labelled command slider instead of the inactive Off value.
Equipment control remained Schedule, with reported power on and speed 4. AirQ
measurements and Recorder graphs loaded. No live equipment command was issued.
The physical-off/cloud-on discrepancy remains unverified pending an independent
observation from the equipment or its local control.

## 0.4.0b3 editable sensor names

105 Python and 15 frontend tests pass. Coverage checks registered versus standalone
sensor cards, escaped names, exact device-registry-only writes, input validation
and error propagation. Isolated browser checks verify Cancel without a write,
blank-name rejection, failure retaining the draft, persistence through the 10-second
reading refresh, Save refreshing both card and graph names, and a 390 px editor.
Live installation evidence is recorded separately; simulation does not establish
physical equipment behavior.
