// Sensor regulation uses the integration backend; credentials never enter the UI.
export const escapeText = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

export function automaticStatus(a, t) {
  const e = escapeText,
    s = a.source;
  return `<p role="status"><strong>${e(t.states[a.status] || a.status)}</strong></p>
    <div class="grid"><div>${e(t.actual)}: <strong>${e(a.actual_speed ?? "—")}</strong></div><div>${e(t.target)}: <strong>${e(a.target_speed ?? "—")}</strong></div></div>
    <p>${s ? `${e(t.source)}: ${e(s.name)} · ${e(t.kinds[s.kind])} ${e(s.value)} ${e(s.unit)} · ${e(a.demand_percent)}%` : e(t.noSource)}</p>
    ${a.wait_seconds ? `<p>${e(t.wait)}: ${e(a.wait_seconds)} s</p>` : ""}
    ${a.invalid_sensors?.length ? `<p class="notice error">${e(t.invalid)}: ${a.invalid_sensors.map(e).join(", ")}</p>` : ""}`;
}

export function automaticCard(a, t, busy) {
  if (!a) return "";
  const e = escapeText;
  return `<section aria-label="${e(t.title)}"><h2>${e(t.title)}</h2>
    <div id="automatic-status">${automaticStatus(a, t)}</div>
    <div class="actions"><button data-action="automatic-enable" ${busy ? "disabled" : ""}>${e(t.enable)}</button><button data-action="automatic-manual" ${busy ? "disabled" : ""}>${e(t.manual)}</button></div>
    <p class="muted">${e(t.explanation)}</p>
    <details><summary>${e(t.settings)}</summary><div class="grid spaced">
    ${Object.keys(a.sensors)
      .map((k) => {
        const options = [...(a.candidates[k] || [])];
        for (const id of a.sensors[k])
          if (!options.some((x) => x.entity_id === id))
            options.push({ entity_id: id, name: id, value: "—" });
        return `<label>${e(t.kinds[k])}<select multiple size="4" data-auto-sensors="${e(k)}" ${busy ? "disabled" : ""}>${options.map((s) => `<option value="${e(s.entity_id)}" ${a.sensors[k].includes(s.entity_id) ? "selected" : ""}>${e(s.name)} (${e(s.value)})</option>`).join("")}</select><small>${options.length ? e(t.multi) : e(t.noSensors)}</small></label>`;
      })
      .join("")}</div><p>${e(t.units)}</p>
    <div class="grid">${Object.entries(a.parameters)
      .map(
        ([k, spec]) =>
          `<label>${e(t.parameters[k])}<input data-auto-setting="${e(k)}" type="number" min="${spec[1]}" max="${spec[2]}" step="${spec[3]}" value="${a.settings[k]}" ${busy ? "disabled" : ""}></label>`,
      )
      .join("")}</div>
    <div class="actions spaced"><button data-action="automatic-save" ${busy ? "disabled" : ""}>${e(t.save)}</button></div></details></section>`;
}

export function automaticInputs(root) {
  const settings = {},
    sensors = {};
  root.querySelectorAll("[data-auto-setting]").forEach((el) => {
    settings[el.dataset.autoSetting] =
      el.value === "" ? null : Number(el.value);
  });
  root.querySelectorAll("[data-auto-sensors]").forEach((el) => {
    sensors[el.dataset.autoSensors] = Array.from(
      el.selectedOptions,
      (o) => o.value,
    );
  });
  return { settings, sensors };
}
