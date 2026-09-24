# Validation — 0.2.0b1

Date: 24 September 2026. Status: **experimental beta**, pending authenticated equipment acceptance. No live HVAC commands or account changes were made while implementing this version.

## Local evidence

- Python 3.14.6, Home Assistant 2026.9.3, pytest 9.1.1, pytest-asyncio 1.4.0.
- **38 automated tests passed**. Tests use real HA imports, a real localhost aiohttp server for HTTP/cookies and fictional fixtures; they do not connect to a household or vendor account.
- Coverage includes session cookie login, one bounded renewal, permission rejection, redirects/malformed/oversized responses, no retry of ambiguous writes, strict identifiers, profile/building scope, membership-change protection, current heartbeat requirement, boost bounds, profile/mode payloads, active-profile and used-mode deletion protection, daily/weekly constraints, stale revisions, DST, AQS recovery, cloud timezone discovery, the actual HA non-admin WebSocket guard, unload bookkeeping and history query encoding.
- Ruff checks and formatting, JavaScript syntax, frontend formatting and translation-key parity checked locally.
- Independent final review verified five corrected findings: failed installation switch isolation, profile activation membership/freshness, daylight-saving timer calculation, AQS recovery, and unsaved-draft protection. No remaining severe issue was identified within that review's scope.

## Frontend evidence

A local demonstration with fictional data exercised actual panel controls through a browser: manual speed with duration, adding/saving a weekly row, creating a mode, creating a profile and querying history with date bounds. Requests were inspected in the demo's visible output; they never reached WifiModule.

The final reviewer additionally exercised a failed installation switch and cancellation of unsaved-draft discard in an isolated frontend harness. An attempted native confirmation-dialog interaction in the in-app browser timed out, so that browser run alone is not evidence of successful dialog handling. The separate reviewer checks cover the state transitions.

## Distribution checks

The repository contains HACS metadata, local original brand icon, English/Spanish documentation, MIT license, a read-only GitHub Actions workflow, and no captured account fixtures. The first published workflow passed all three jobs: tests (pytest, Ruff, JavaScript syntax and formatting), Home Assistant hassfest, and HACS validation. [Successful run](https://github.com/JesusMF23/ha-jeremias-wifimodule/actions/runs/35997310671). Automated distribution checks are not a substitute for physical-device acceptance.

## Remaining acceptance before a stable release

1. Install into a backed-up test Home Assistant instance, sign in through the config flow and confirm correct building, timezone and unit discovery.
2. Wait for real `last_comm` progress; compare telemetry to the website. Check HA restart/unload/reload and reauthentication. Test migration from the earlier prototype on a copied configuration before upgrading an important installation.
3. With the equipment owner present, send a short, reversible speed/boost override, confirm physical telemetry, and explicitly return to the previous schedule. A successful cloud response alone is insufficient.
4. Export the existing programming. On a disposable **inactive** profile, create/edit modes and a week, copy a day and compare all seven days in the website. Changing existing modes can affect active schedules; use new modes. Confirm conflict protection by editing the disposable profile from a second client.
5. Verify account-specific permissions and retention for cloud history. Check multiple buildings and multi-unit groups using real supported installations.
6. Perform mobile, keyboard and screen-reader checks inside Home Assistant's real frontend. The local demo does not reproduce every HA frontend behavior.
7. Confirm CI checks and create a tagged prerelease for testers. Do not claim default-catalogue HACS inclusion without its separate review.

Installer calibration and Airzone wiring remain outside this acceptance scope.
