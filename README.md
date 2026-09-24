# Jeremias / WifiModule for Home Assistant

[![Validate](https://github.com/JesusMF23/ha-jeremias-wifimodule/actions/workflows/validate.yaml/badge.svg)](https://github.com/JesusMF23/ha-jeremias-wifimodule/actions/workflows/validate.yaml)

Community integration for heat-recovery ventilation controlled through **wifimodule.eu**. Includes native Home Assistant entities and a **Jeremias** sidebar panel for modes, profiles and weekly programming. No extra hardware is required. This integration depends on the WifiModule cloud and is not a local Modbus integration.

**0.2.0b1 is a beta.** The basic status and control endpoints have user-captured evidence. Programming endpoints are implemented from the website's public JavaScript and tested against simulated responses; complete authenticated hardware acceptance is still pending. This is not an official Jeremias product and is not yet listed in the HACS default catalogue.

[Español](README.es.md) · [Protocol and coverage](docs/PROTOCOL.md) · [Validation](docs/VALIDATION.md)

## Features

| Area | Available functionality |
| --- | --- |
| Setup | UI sign-in; building discovery; multiple installations; multiple units per installation; reauthentication and reconfiguration |
| Native controls | Fan with seven levels and off; automatic or manual mode; return to schedule; bypass; timed override; five-minute boost; active profile selector |
| Telemetry | Per-unit power, actual speed, boost, bypass, errors, filter counter, last communication and AQS values when valid |
| Weekly programming | Load a profile; edit daily time/mode transitions; copy a day to another day; activate profiles; reject stale edits |
| Profiles | Create, rename and delete inactive profiles |
| Modes | Create/edit speed, automatic/manual operation, bypass, colour and name; delete unused modes |
| History | Cloud chart and table, optional date range up to 366 days; actual retention depends on the cloud account |
| Other | English/Spanish UI; local JSON export of the loaded programming; redacted diagnostics |

Controls act on **every unit in the selected building**, as the website API does. Sensor entities report each unit separately. Automatic mode uses the recuperator's own sensor logic: it does not automatically connect Airzone AirQ sensors.

## Requirements

- Home Assistant **2026.9.0 or newer**. Tested locally with 2026.9.3.
- An existing WifiModule cloud account with access to the building and paired unit.
- Internet access from Home Assistant to `https://wifimodule.eu`.
- HACS is optional. A built-in WifiModule module is sufficient; no additional gateway is used.

## Install

### HACS custom repository

Repository: `https://github.com/JesusMF23/ha-jeremias-wifimodule`.

1. Open HACS → menu → **Custom repositories**.
2. Enter that repository URL and select **Integration**.
3. Download **Jeremias / WifiModule**, enabling beta releases when required.
4. Restart Home Assistant.
5. Go to Settings → Devices & services → Add integration → **Jeremias / WifiModule**.
6. Enter your WifiModule email/password in the Home Assistant form and select your building. Add the integration again for another building.

HACS custom repositories and inclusion in the default catalogue are different: default catalogue submission has not been performed.

### Manual installation

Copy the entire `custom_components/wifimodule` directory into `/config/custom_components/wifimodule`. Do not nest another `wifimodule` directory inside it. Restart Home Assistant, then follow steps 5–6 above. No YAML, copied browser cookie or API key is needed.

The `jeremias-wifimodule-0.2.0b1-install.zip` distribution contains the `custom_components` directory and license. Extract it into the Home Assistant configuration directory, preserving that structure.

## Use

Native entities appear under the integration's building and unit devices. Open **Jeremias** in the sidebar as an administrator for the full editor. If a previously cached frontend remains visible after an update, refresh the browser.

1. Wait for the unit's `last_comm` to advance after loading/restarting the integration. Until then physical controls are unavailable; this prevents treating a cached cloud response as current. A lack of progress for ten minutes blocks controls again.
2. Set the default override duration using the number entity, or choose a duration in the panel. The default is **30 minutes**. Zero means indefinite, including an indefinite off command. Manual overrides return to the cloud schedule on expiry.
3. Boost's button uses five minutes. Panel boost requires 1–60 minutes. Choose **Return to schedule** to cancel an override.
4. In **Modes**, create reusable operating modes. Editing a mode affects every schedule that references it.
5. In **Profiles**, create a profile. In **Weekly schedule**, select that profile and each day, edit transitions and **Save day**. The first transition must be 00:00; times must be distinct. The total week is limited to 150 transitions.
6. **Copy & save** immediately replaces the target day's entire schedule with the currently edited rows. Export first if you want a local record. Export covers the loaded profile's week and the profile/mode lists, not every profile's week; there is no import/restore feature yet.
7. Activate the desired profile. A manual override may still take priority: use **Return to schedule** to hand control back to programming.

History date fields and overrides use the building's timezone from WifiModule. Because the API accepts timestamps without offsets, a timed command whose expiry falls in a repeated daylight-saving hour is rejected. The server accepts only minute precision, so a timer can be shorter by up to 59 seconds.

Use standard Home Assistant fan, select, switch, button and number actions in automations. Entity names depend on your building and HA language; choose the entities from the automation editor rather than copying guessed IDs. Native fan percentages map to seven levels (e.g. 43% requests level 4). Changing the duration number affects future commands, not an already running timer.

## Boundaries

- Installer calibration, fan balancing, installation type, factory resets, device pairing, ownership transfers, password and account management remain on the vendor website. Exposing those service-role endpoints generically would require model-specific documentation and separate testing.
- Airzone O1/O2 and heating/cooling configuration are not modified. AirQ-to-Jeremias automation requires confirmed sensor entities and user-selected thresholds; it is not enabled automatically.
- Cloud API availability, rate limits, history retention and firmware differences are outside this project's control. API changes may require an integration update.
- Schedule conflict detection compares the loaded week with a fresh read before writing. The server has no observed atomic version check, so simultaneous edits within that small read/write window remain possible. Avoid editing the same profile in two clients at once.
- An acknowledgement is not proof of physical actuation. Unit entities retain reported telemetry until the equipment communicates again. Ambiguous write failures are not automatically retried: reload and inspect the website before repeating a programming operation.
- If units are added/removed from a building, controls and programming writes stop. Use the integration's **Reconfigure** flow to review and accept current membership.

## Privacy and contributing

Credentials are stored in Home Assistant's config entry, used only by the backend and never sent to the custom frontend. Treat your HA configuration and backups as secret. Diagnostics deliberately exclude credentials, account data, identifiers, names and raw telemetry. Programming exports contain your own names and schedule; review before sharing.

Report a failure with HA/integration versions, a redacted diagnostic file and steps to reproduce. Do not attach cookies, passwords, HAR files or full config entries. Source and tests contain fictional fixtures only.

Development: install `requirements-dev.txt` under Python 3.14, run `pytest -q`, `ruff check .`, and `ruff format --check .`. See [validation](docs/VALIDATION.md) for the remaining release acceptance work.

MIT licensed. Brand names identify compatible products; no affiliation or endorsement is claimed.
