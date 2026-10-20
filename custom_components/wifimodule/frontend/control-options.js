import { escapeText as e } from "./automatic.js";

export function timerSummary(a, t, now = Date.now()) {
  const timer = a?.manual_timer;
  if (!timer?.expires_at) return "";
  const minutes = Math.max(
    0,
    Math.ceil((Date.parse(timer.expires_at) - now) / 60000),
  );
  return `${t.returnIn} ${minutes} ${t.minutes} → ${timer.return_to === "automatic" ? t.enable : t.schedule}`;
}
export function timerControls(a, t, duration = 30, draft = null) {
  const target = draft?.return_to ?? a?.manual_timer?.return_to ?? "none";
  const remaining =
    draft?.duration ??
    (a?.manual_timer?.expires_at
      ? Math.max(
          1,
          Math.ceil(
            (Date.parse(a.manual_timer.expires_at) - Date.now()) / 60000,
          ),
        )
      : Number(duration) || 30);
  return `<label id="return-row">${e(t.afterManual)}<select id="return-to"><option value="none" ${target === "none" ? "selected" : ""}>${e(t.noLimit)}</option><option value="automatic" ${target === "automatic" ? "selected" : ""}>${e(t.enable)}</option><option value="schedule" ${target === "schedule" ? "selected" : ""}>${e(t.schedule)}</option></select></label><label id="duration-row" hidden>${e(t.durationLabel)}<input id="duration" type="number" min="1" max="10080" step="1" value="${remaining}"><select id="duration-unit" aria-label="${e(t.durationUnit)}"><option value="1" ${draft?.unit !== "60" ? "selected" : ""}>${e(t.minutes)}</option><option value="60" ${draft?.unit === "60" ? "selected" : ""}>${e(t.hours)}</option></select></label>`;
}
export function timerInputs(root) {
  const q = (s) => root.querySelector(s).value;
  const temporary = Number(q("#speed")) === 8 || q("#control-mode") === "auto";
  const return_to = temporary ? "none" : q("#return-to");
  const duration =
    !temporary && return_to === "none"
      ? 0
      : Number(q("#duration")) * Number(q("#duration-unit"));
  if (
    !Number.isInteger(duration) ||
    duration < 0 ||
    duration > 10080 ||
    ((temporary || return_to !== "none") && duration < 1) ||
    (Number(q("#speed")) === 8 && duration > 60)
  )
    throw new Error("Invalid timer");
  return { duration, return_to };
}
export function bindTimer(root) {
  const q = (s) => root.querySelector(s);
  const update = () => {
    const temporary =
      Number(q("#speed").value) === 8 || q("#control-mode").value === "auto";
    q("#return-row").hidden = temporary;
    q("#duration-row").hidden = !temporary && q("#return-to").value === "none";
  };
  q("#return-to").onchange = update;
  update();
  return update;
}
export function bypassPresentation(a, t) {
  const owned = a?.mode === "automatic" || a?.mode === "manual";
  const requested = owned ? a?.bypass_requested : null;
  const reported = a?.bypass_reported;
  const mismatch = requested != null && requested !== reported;
  const suffix = mismatch
    ? a?.bypass_pending
      ? t.bypassPending
      : t.bypassUnconfirmed
    : "";
  return {
    checked: requested ?? reported ?? false,
    text: `${t.bypassReported}: ${reported == null ? t.unknown : reported ? t.on : t.off}${suffix ? " · " + suffix : ""}`,
  };
}
export function bypassControl(a, t, busy) {
  const state = bypassPresentation(a, t);
  return `<div class="bypass-control"><label class="check"><input id="regulation-bypass" type="checkbox" ${state.checked ? "checked" : ""} ${busy || !a?.connection?.device_ready ? "disabled" : ""}>${e(t.bypassLabel)}</label><small>${e(t.bypassHelp)}</small><small id="bypass-status">${e(state.text)}</small></div>`;
}
