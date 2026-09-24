# Observed protocol and coverage

Inspected 24 September 2026. This is a reverse-engineered community client, not a vendor API specification. Requests use HTTPS, JSON bodies for POST, and session cookies from sign-in. The integration never exports those cookies to the browser or logs response bodies.

## Evidence levels

- **Captured**: the user observed authenticated GET `/api/status` and a successful POST `/api/unit-config` with building, manual, speed, bypass, mode and switch fields. Private captured account/building/unit identifiers are deliberately absent from this repository.
- **Source-confirmed**: payload construction and response parsing inspected in public JavaScript served by [wifimodule.eu](https://wifimodule.eu/). Exact cloud account permissions, firmware variation and success responses still need authenticated hardware acceptance for these endpoints.
- **Simulated**: tests validate our implementation using fictional fixtures and localhost HTTP. This is not hardware certification.

Public bundle evidence included the shared Display bundle, `ModesPage-BSCyAtQl.js`, `ProfilesPage-oshzDsEf.js`, `SchedulePage-CnLUO5wI.js`, `BuildingsPage-4nhI_Yuu.js`, `UnitsPage-CHdKW8I4.js`, `SensorHistoryPage-ySJzNF8W.js`, `UnitSettingsPage-Br5HCfdG.js` and `UnitSettingsProtocol-D749xJAk.js`. Bundle names can change after site deployment; rediscover them from the site's HTML/module imports. No vendor bundle is redistributed here.

## Read and control

All paths below are relative to `https://wifimodule.eu/api/`.

| Request | Contract | Evidence |
| --- | --- | --- |
| POST `login` | `{email,password}`, success message establishes session cookie | Source-confirmed |
| GET `status` | `{msg:"status",status:[building...]}`; units contain raw status register string and `last_comm` | Captured |
| GET `buildings` | `{msg:"buildings",buildings:[...]}`; use building `tz` | Source-confirmed |
| POST `unit-config` | `{building,manual:true,speed,bypass,mode,switch}` | Captured basic command; variants source-confirmed |
| POST `unit-config` | `{building,manual:false}` resumes schedule | Source-confirmed |
| GET `chart?unit=...` | `{msg:"chart",chart:{labels,datasets},...}` | Source-confirmed |
| GET `chart?unit=...&from=...&to=...` | Local datetime `YYYY-MM-DD HH:mm:ss`, URL-encoded | Source-confirmed |

Manual speed: 0=off, 1–7=levels, 8=boost. Mode is `manual` or `auto`; bypass is JSON boolean. `switch` is `never` or building-local `YYYY-MM-DD HH:mm`. The integration adds a bounded boost requirement (1–60 minutes).

Observed registers: `fil` filter counter, `err` error code, `bst` boost flag, `byp` bypass flag, `spe` speed, `pwr` power, `moa` automatic/manual. AQS type 1 is CO₂ (ppm), type 2 humidity (tenths of percent), type 3 radon (Bq/m³). Raw AQS values below 10 are treated as unknown, following web display behavior; unsupported types are unknown. Register interpretations beyond the supplied status capture are based on web source and require model-specific acceptance.

AQS sensor metadata initializes at the first valid type. If the physical sensor type later changes, values stay unknown until reload so different physical quantities cannot be mixed silently in long-term statistics. After a deliberate physical sensor-type change, review/remove old HA statistics before adopting the new type.

## Profiles, modes and programming

| Request | Contract |
| --- | --- |
| GET `profiles?building=ID` | `msg:"profiles"`, profiles array |
| POST `profiles` add | `{op:"add",data:{name,building_id}}` |
| POST `profiles` edit | `{op:"edit",data:{...existingProfile,name}}` |
| POST `profiles` delete | `{op:"delete",data:{id}}` |
| POST `profiles` activate | `{op:"activate",data:{profile,building}}` |
| GET `modes?building=ID` | `msg:"modes"`, modes array |
| POST `modes` | `{op:"add"|"edit"|"delete",data:{...}}` |
| GET `schedule?building=ID&profile=ID` | `msg:"schedule"`, schedule object `d0`…`d6` |
| POST `edit-schedule` | `{building,profile,wday,schedule:[{time,mode}]}` |

These programming requests are **source-confirmed, not yet authenticated acceptance-tested**.

Mode data: `name`, six-digit hex `color`, `speed` clamped 1–7, `off` and `boost` booleans, `bypass` numeric 0/1, and `mode` manual/auto. Add includes `building_id`; edit includes `id`; delete only `id`. The panel uses conceptual speeds 0 and 8, converted to the website's `off`/`boost` flags by the backend.

Days: 0 Sunday, 1 Monday … 6 Saturday. `time` is minutes from midnight. Read rows use `mode_id`; write rows use `mode`. Each write replaces a full day. The first row must start at zero; times strictly increase; mode IDs must belong to the building. The integration rejects more than 150 changes in a week.

A SHA-256 revision derived from all seven days detects edits since the panel loaded. A fresh cloud read is compared before POST. There is no observed server-side compare-and-swap or transactional revision; this check cannot close the final read/write race.

## Explicitly excluded service operations

The public web app also exposes service-role `service-units` operations `load-config`, `save-config`, and `reset-config`, as well as account/pairing/building-administration operations. These may alter calibration, balancing, device type, addressing or ownership. They are not generic everyday HVAC controls and are not implemented in this beta. The exact recuperator model must be established before considering a separate, model-specific installer feature.

## Error handling

HTTP 401/403 and JSON `err:"permissions"` allow one session renewal and one retry. Other HTTP failures, malformed JSON, oversized responses and network failures are not retried automatically, especially for writes. `msg:"success"` is an acknowledgement, not a physical-state update. Traffic stays on the fixed HTTPS origin; HTTP redirects are rejected.

## HA/HACS references

- [HACS integration structure](https://www.hacs.xyz/docs/publish/integration/)
- [HACS publishing prerequisites](https://www.hacs.xyz/docs/publish/start/)
- [HACS validation action](https://www.hacs.xyz/docs/publish/action/)
- [Home Assistant local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
