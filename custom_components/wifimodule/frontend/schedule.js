import { escapeText as e } from "./automatic.js";

const days = [1, 2, 3, 4, 5, 6, 0];
const dayEnd = 24 * 60;
const isDirect = (row) => "speed" in row;
const minute = (n) =>
  `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
const speedName = (speed, t) => (speed === 0 ? t.off : `${t.speed} ${speed}`);
const bypassName = (enabled, t) =>
  `${t.bypass} · ${enabled ? t.scheduleBypassOn : t.off}`;

export function scheduleDraft(view, day) {
  const modes = new Map(view?.modes?.map((mode) => [mode.id, mode]));
  return (view?.week?.[`d${day}`] || []).map(({ time, mode_id, mode }) => {
    const id = mode_id ?? mode;
    const speed = modes.get(id)?.schedule_speed;
    return speed ? { time, ...speed } : { time, mode: id };
  });
}

export function sortedSchedule(rows) {
  return [...rows].sort((a, b) => a.time - b.time);
}

export function scheduleIssue(view, destinations, rows) {
  const sorted = sortedSchedule(rows);
  if (!rows.length) return "scheduleEmpty";
  if (
    sorted[0].time !== 0 ||
    sorted.some(
      (row, i) =>
        !Number.isInteger(row.time) ||
        row.time < 0 ||
        row.time >= dayEnd ||
        row.time === sorted[i - 1]?.time,
    )
  )
    return "scheduleInvalidTimes";
  if (
    sorted.some(
      (row) =>
        !isDirect(row) && !view.modes.some((mode) => mode.id === row.mode),
    )
  )
    return "scheduleMissingMode";
  const otherDays = days
    .filter((d) => !destinations.includes(d))
    .reduce((sum, d) => sum + (view.week?.[`d${d}`]?.length || 0), 0);
  return otherDays + rows.length * destinations.length > 150
    ? "scheduleLimit"
    : "";
}

export function addScheduleRow(rows) {
  const used = new Set(rows.map((row) => row.time));
  const last = sortedSchedule(
    rows.filter((row) => Number.isInteger(row.time)),
  ).at(-1);
  let time = last ? Math.min(last.time + 60, dayEnd - 1) : 0;
  while (used.has(time)) time--;
  return {
    time,
    speed: last && isDirect(last) ? last.speed : 1,
    bypass: last && isDirect(last) ? last.bypass : false,
  };
}

function track(rows, modes, t) {
  const sorted = sortedSchedule(rows);
  if (
    sorted[0]?.time !== 0 ||
    sorted.some(
      (row, i) =>
        !Number.isInteger(row.time) ||
        row.time < 0 ||
        row.time >= dayEnd ||
        row.time === sorted[i - 1]?.time,
    )
  )
    return "";
  return sorted
    .map((row, i) => {
      const end = sorted[i + 1]?.time ?? dayEnd;
      const mode = modes.get(row.mode);
      const label = isDirect(row)
        ? speedName(row.speed, t)
        : (mode?.name ?? t.unknown);
      const bypass = isDirect(row)
        ? row.bypass
        : mode?.bypass === 1 || mode?.bypass === true;
      const description = `${minute(row.time)}–${minute(end)} · ${label} · ${bypassName(bypass, t)}`;
      const width = ((end - row.time) / dayEnd) * 100;
      const color = isDirect(row)
        ? row.speed
          ? `color-mix(in srgb,var(--primary-color,#007f83) ${22 + row.speed * 10}%,var(--card-background-color,#fff))`
          : "var(--divider-color,#dce1e6)"
        : /^#[a-f0-9]{6}$/i.test(mode?.color)
          ? mode.color
          : "var(--divider-color,#dce1e6)";
      const short = isDirect(row) && row.speed > 0 ? row.speed : label;
      return `<span class="schedule-segment${bypass ? " schedule-bypass" : ""}" style="flex-basis:${width}%;--segment-color:${color}" title="${e(description)}"><span>${e(short)}</span></span>`;
    })
    .join("");
}

export function schedulePreview(view, day, draft, busy, dirty, t) {
  const modes = new Map(view.modes.map((mode) => [mode.id, mode]));
  return `<div class="schedule-axis" aria-hidden="true"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div><div class="schedule-week">${days
    .map((d) => {
      const rows = d === day ? draft : scheduleDraft(view, d);
      const description = `${t.days[d]} · ${rows.length} ${t.scheduleBlocks}${d === day && dirty ? ` · ${t.scheduleDraft}` : ""}`;
      return `<button type="button" class="schedule-day" data-schedule-day="${d}" aria-label="${e(description)}" aria-pressed="${d === day}" ${busy ? "disabled" : ""}><span class="schedule-day-name" aria-hidden="true">${e(t.days[d])}</span><span class="schedule-track" aria-hidden="true">${track(rows, modes, t)}</span></button>`;
    })
    .join(
      "",
    )}</div><p class="schedule-legend muted"><span>${e(t.scheduleFixed)}</span><span><i class="schedule-bypass" aria-hidden="true"></i>${e(bypassName(true, t))}</span></p>`;
}

const option = (value, label, selected) =>
  `<option value="${e(value)}"${value === selected ? " selected" : ""}>${e(label)}</option>`;

function scheduleRow(row, i, end, view, t) {
  const direct = isDirect(row);
  const selected = direct ? `speed:${row.speed}` : `mode:${row.mode}`;
  const modes = view.modes.filter((mode) => !mode.schedule_speed);
  const speeds = Array.from({ length: 8 }, (_, speed) =>
    option(`speed:${speed}`, speedName(speed, t), selected),
  ).join("");
  const existing = modes
    .map((mode) => option(`mode:${mode.id}`, mode.name, selected))
    .join("");
  const missing = !direct && !modes.some((mode) => mode.id === row.mode);
  return `<div class="schedule-row">
    <div class="schedule-row-range" data-schedule-range="${i}">${rangeLabel(row, end)}</div>
    <label>${e(t.start)}<input type="time" data-schedule-time="${i}" value="${Number.isInteger(row.time) ? minute(row.time) : ""}" ${i === 0 ? "disabled" : ""}></label>
    <label>${e(t.scheduleVentilation)}<select data-schedule-choice="${i}"><optgroup label="${e(t.scheduleFixed)}">${speeds}</optgroup>${existing ? `<optgroup label="${e(t.modes)}">${existing}</optgroup>` : ""}${missing ? option(selected, t.unknown, selected) : ""}</select></label>
    <label class="check schedule-bypass-toggle" ${direct ? "" : "hidden"}><input type="checkbox" data-schedule-bypass="${i}" ${row.bypass ? "checked" : ""} ${direct ? "" : "disabled"}>${e(t.bypass)}</label>
    <button type="button" data-action="remove-row" data-index="${i}" ${i === 0 ? "disabled" : ""}>${e(t.remove)}</button></div>`;
}

function rangeLabel(row, end) {
  return Number.isInteger(row.time) && end > row.time
    ? `${minute(row.time)} – ${minute(end)}`
    : "—";
}

export function scheduleEditor(
  view,
  day,
  draft,
  busy,
  dirty,
  t,
  copyDays = [],
) {
  const current = view.profile_id;
  const active = current != null && current === view.building.profile_id;
  const ends = scheduleEnds(draft);
  const action = (name, text, disabled = false, cls = "") =>
    `<button type="button" class="${cls}" data-action="${name}" ${busy || disabled ? "disabled" : ""}>${e(text)}</button>`;
  const copyTargets = days.filter((d) => d !== day);
  const issue = scheduleIssue(view, [day], draft);
  const copyIssue = copyDays.length ? scheduleIssue(view, copyDays, draft) : "";
  return `<section class="schedule-editor"><div class="section-heading"><h2>${e(t.schedule)}</h2>${active ? `<span class="pill active">${e(t.active)}</span>` : ""}</div>
    <div class="toolbar schedule-profile"><label>${e(t.profile)}<select id="profile" ${busy || !view.profiles.length ? "disabled" : ""}>${view.profiles.map((p) => option(p.id, p.name, current)).join("")}</select></label>${action("activate", t.activate, active || current == null)}</div>
    <div id="schedule-preview">${schedulePreview(view, day, draft, busy || current == null, dirty, t)}</div>
    <div class="section-heading schedule-heading"><h3>${e(t.days[day])}</h3><span id="schedule-draft" class="pill" ${dirty ? "" : "hidden"}>${e(t.scheduleDraft)}</span></div>
    <fieldset class="schedule-rows" aria-label="${e(t.scheduleBlocks)}" ${busy ? "disabled" : ""}>${draft.map((row, i) => scheduleRow(row, i, ends.get(row.time), view, t)).join("")}</fieldset>
    <p id="schedule-issue" class="muted" role="status" ${issue ? "" : "hidden"}>${e(t[issue])}</p>
    <div class="actions">${action("add-row", t.scheduleAdd, current == null || draft.length >= 150)}${action("save-day", t.saveDay, current == null || !!issue, "primary")}</div>
    <fieldset class="schedule-copy spaced" ${busy || current == null ? "disabled" : ""}>
      <legend>${e(t.copy)}</legend><p class="muted">${e(t.scheduleCopyHelp)}</p>
      <div class="schedule-copy-days">${copyTargets.map((d) => `<label class="check"><input type="checkbox" data-schedule-copy-day="${d}"${copyDays.includes(d) ? " checked" : ""}>${e(t.days[d])}</label>`).join("")}</div>
      <p id="schedule-copy-issue" class="muted" role="status" ${copyIssue ? "" : "hidden"}>${e(t[copyIssue])}</p>
      <div class="actions"><button type="button" data-schedule-copy-all>${e(copyDays.length === copyTargets.length ? t.scheduleCopyClear : t.scheduleCopyAll)}</button>${action("copy-day", t.copyButton, current == null || !copyDays.length || !!copyIssue)}</div>
    </fieldset>
    <details class="schedule-help"><summary>${e(t.scheduleHelp)}</summary><p class="muted">${e(t.revision)}</p></details>
    </section>`;
}

function scheduleEnds(rows) {
  const sorted = sortedSchedule(
    rows.filter((row) => Number.isInteger(row.time)),
  );
  return new Map(
    sorted.map((row, i) => [row.time, sorted[i + 1]?.time ?? dayEnd]),
  );
}

export function updateScheduleEditor(
  root,
  view,
  day,
  draft,
  busy,
  dirty,
  t,
  copyDays,
) {
  root.querySelector("#schedule-preview").innerHTML = schedulePreview(
    view,
    day,
    draft,
    busy,
    dirty,
    t,
  );
  root.querySelector("#schedule-draft").hidden = !dirty;
  const issue = scheduleIssue(view, [day], draft);
  const status = root.querySelector("#schedule-issue");
  status.hidden = !issue;
  status.textContent = t[issue] || "";
  root.querySelector('[data-action="save-day"]').disabled =
    busy || view.profile_id == null || !!issue;
  const copyIssue = copyDays.length ? scheduleIssue(view, copyDays, draft) : "";
  const copyStatus = root.querySelector("#schedule-copy-issue");
  copyStatus.hidden = !copyIssue;
  copyStatus.textContent = t[copyIssue] || "";
  root.querySelector('[data-action="copy-day"]').disabled =
    busy || view.profile_id == null || !copyDays.length || !!copyIssue;
  root.querySelector("[data-schedule-copy-all]").textContent =
    copyDays.length === days.length - 1
      ? t.scheduleCopyClear
      : t.scheduleCopyAll;
  const ends = scheduleEnds(draft);
  root.querySelectorAll("[data-schedule-range]").forEach((element, i) => {
    element.textContent = rangeLabel(draft[i], ends.get(draft[i].time));
  });
}
