# AirQ bridge removal — 1.0.2

## Implementation plan

- Remove the AirQ bridge, synthetic sensor platform, lifecycle hooks, unused translations and `airzone_cloud` loading dependency.
- Keep regulation connected to Home Assistant sensor states and registries. Preserve saved mode, sensor IDs, thresholds and manual controls; do not guess replacement entity IDs.
- Verify setup never enumerates another integration's entries, generic sensors still drive the existing controller, and missing former bridge sensors remain invalid without sending commands.
- Update English/Spanish upgrade guidance, run the complete local suite and minimum/latest HA, HACS and hassfest CI, then publish 1.0.2 and re-request review on the existing HACS submission.

## Upgrade guidance

The removed bridge borrowed Airzone Cloud's internal client/session and made additional device-status requests. From 1.0.2, Jeremias reads only the sensor entities exposed in Home Assistant by their owning integrations. It does not log in to Airzone, poll its account or create AirQ measurement entities.

If you selected CO₂, TVOC or humidity entities created by the former Jeremias bridge, those entities will no longer update. Open **Jeremias → Sensors and thresholds**, deselect the unavailable entities and select replacements actually exposed by Airzone Cloud or another installed sensor integration. Check each entity's device class, measurement unit and freshness before enabling Automatic. CO₂ is ppm; TVOC is ppb or ppm; humidity is %. AQI may be used only with a known higher-is-worse scale and cannot substitute for gas concentrations.

Saved selections and thresholds are retained for inspection. No replacement IDs are invented or selected automatically. If all selected readings are invalid, regulation sends no commands; a partly invalid selection blocks reductions and maintenance renewals while valid readings may still justify a rise. Existing finite cloud overrides retain their original expiry. Select Manual or Jeremias Schedule explicitly if you want that ownership during reconfiguration.

If Airzone Cloud does not expose a required measurement, support belongs in the Home Assistant core Airzone Cloud integration. This release does not claim that every AirQ measurement is currently available there. Historical validation notes for bridge-based readings describe older versions, not a capability of 1.0.2.
