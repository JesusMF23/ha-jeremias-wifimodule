// Sensor regulation uses the integration backend; credentials never enter the UI.
export const escapeText = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const e = escapeText;
export const speedLabel = (v, t) => (v === 0 ? t.off : (v ?? "—"));

export function automaticStatus(a, t) {
  const s = a.enabled ? a.source : null;
  return `<div class="status-top"><span class="pill ${a.enabled ? "active" : ""}">${e(t.states[a.status] || a.status)}</span><span class="muted">${e(t.cloud)} · ${e(a.connection?.available ? (a.connection.device_ready ? t.connected : t.deviceWaiting) : t.disconnected)}</span></div>
    <div class="regulation-metrics"><div><span class="eyebrow">${e(t.actual)}</span><strong class="speed-number">${e(speedLabel(a.actual_speed, t))}</strong></div><div><span class="eyebrow">${e(t.target)}</span><strong class="speed-number">${e(speedLabel(a.enabled ? a.target_speed : a.mode === "manual" ? a.manual_speed : null, t))}</strong></div><div class="demand"><span class="eyebrow">${e(t.source)}</span><strong>${s ? e(s.name) : e(a.enabled ? t.noSource : a.mode === "manual" ? t.manualHold : a.mode === "schedule" ? t.scheduleHelp : t.paused)}</strong>${s ? `<small>${e(t.kinds[s.kind])} · ${e(s.value)} ${e(s.unit)} · ${e(a.demand_percent)}%</small>` : ""}${a.enabled && a.wait_seconds ? `<small>${e(t.wait)}: ${e(a.wait_seconds)} s</small>` : ""}</div></div>
    ${a.enabled && a.invalid_sensors?.length ? `<p class="notice error">${e(t.invalid)}: ${a.invalid_sensors.map(e).join(", ")}</p>` : ""}`;
}

function setting(k, a, t, busy) {
  const spec = a.parameters[k];
  return `<div class="setting"><label for="setting-${k}">${e(t.parameters[k])}</label><div class="range-field"><input type="range" data-setting-range="${k}" aria-label="${e(t.parameters[k])}" min="${spec[1]}" max="${spec[2]}" step="1" value="${a.settings[k]}" ${busy ? "disabled" : ""}><input id="setting-${k}" data-auto-setting="${k}" type="number" min="${spec[1]}" max="${spec[2]}" step="1" value="${a.settings[k]}" ${busy ? "disabled" : ""}></div></div>`;
}
function sensorChoices(k, a, t, busy) {
  const options = [...(a.candidates[k] || [])];
  for (const id of a.sensors[k])
    if (!options.some((x) => x.entity_id === id))
      options.push({ entity_id: id, name: id, value: null, valid: false });
  return `<fieldset data-sensor-group="${k}"><legend>${e(t.kinds[k])}</legend><div class="sensor-choices">${options.length ? options.map((s) => `<label class="sensor-choice"><input type="checkbox" data-auto-sensors="${k}" value="${e(s.entity_id)}" ${a.sensors[k].includes(s.entity_id) ? "checked" : ""} ${busy ? "disabled" : ""}><span>${e(s.name)}<small>${s.valid ? `${e(s.value)} ${e(s.unit)}` : e(t.unavailable)}</small></span></label>`).join("") : `<p class="muted">${e(t.noSensors)}</p>`}</div></fieldset>`;
}
export function automaticCard(a, t, busy) {
  if (!a) return "";
  const core = [
    "min_speed",
    "max_speed",
    "co2_target",
    "co2_full",
    "tvoc_target",
    "tvoc_full",
  ];
  const optional = [
    "humidity_target",
    "humidity_full",
    "aqi_target",
    "aqi_full",
  ];
  const advanced = Object.keys(a.parameters).filter(
    (k) => ![...core, ...optional].includes(k),
  );
  return `<section class="regulation" aria-label="${e(t.title)}"><div class="section-heading"><div><span class="eyebrow">${e(t.ventilation)}</span><h2>${e(t.title)}</h2></div><div class="segmented" role="group" aria-label="${e(t.controlMode)}"><button data-action="automatic-enable" aria-pressed="${a.enabled}" ${busy ? "disabled" : ""}>${e(t.enable)}</button><button data-action="automatic-manual" aria-pressed="${(a.mode ?? (a.enabled ? "automatic" : "manual")) === "manual"}" ${busy ? "disabled" : ""}>${e(t.manual)}</button><button data-action="automatic-schedule" aria-pressed="${a.mode === "schedule"}" ${busy ? "disabled" : ""}>${e(t.schedule)}</button></div></div>
    <div id="automatic-status">${automaticStatus(a, t)}</div>
    <details class="regulation-settings" data-disclosure="settings"><summary>${e(t.settings)}</summary><p class="muted">${e(t.explanation)}</p>
    <h3>${e(t.limits)}</h3><div class="grid">${core.map((k) => setting(k, a, t, busy)).join("")}</div><p class="muted">${e(t.zeroHint)}</p>
    <h3>${e(t.zones)}</h3><p class="muted">${e(t.multi)}</p><div class="grid">${["co2", "tvoc"].map((k) => sensorChoices(k, a, t, busy)).join("")}</div>
    <details data-disclosure="optional"><summary>${e(t.optional)}</summary><p class="muted">${e(t.units)}</p><div class="grid">${["humidity", "aqi"].map((k) => sensorChoices(k, a, t, busy)).join("")}${optional.map((k) => setting(k, a, t, busy)).join("")}</div></details>
    <details data-disclosure="advanced"><summary>${e(t.advanced)}</summary><div class="grid spaced">${advanced.map((k) => setting(k, a, t, busy)).join("")}</div></details>
    <div class="actions spaced"><button class="primary" data-action="automatic-save" ${busy ? "disabled" : ""}>${e(t.save)}</button><span class="muted">${e(t.savedOnly)}</span></div></details></section>`;
}
export function automaticInputs(root) {
  const settings = {},
    sensors = {};
  root.querySelectorAll("[data-auto-setting]").forEach((el) => {
    settings[el.dataset.autoSetting] =
      el.value === "" ? null : Number(el.value);
  });
  root.querySelectorAll("[data-sensor-group]").forEach((el) => {
    sensors[el.dataset.sensorGroup] = Array.from(
      el.querySelectorAll("input:checked"),
      (o) => o.value,
    );
  });
  return { settings, sensors };
}
export function bindAutomatic(root, change) {
  root
    .querySelectorAll(
      "[data-auto-setting], [data-auto-sensors], [data-setting-range]",
    )
    .forEach((el) => {
      el.oninput = () => {
        const k = el.dataset.settingRange || el.dataset.autoSetting;
        if (k) {
          const counterpart = root.querySelector(
            el.dataset.settingRange
              ? `[data-auto-setting="${k}"]`
              : `[data-setting-range="${k}"]`,
          );
          counterpart.value = el.value;
        }
        change(automaticInputs(root));
      };
    });
}
