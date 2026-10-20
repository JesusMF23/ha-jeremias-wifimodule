import { escapeText as e } from "./automatic.js";
import { timerControls } from "./control-options.js";

export function manualControls(a, view, t, busy, draft) {
  if (!view) return "";
  const b = view.building;
  const speed =
    draft?.speed ??
    (a?.mode === "manual"
      ? (a.manual_speed ?? 0)
      : b.manual_active === false && a?.actual_speed != null
        ? a.actual_speed
        : (b.manual_speed ?? 1));
  const mode = draft?.mode ?? b.manual_mode ?? "manual";
  return `<div id="manual-controls" ${a && a.mode !== "manual" ? "hidden" : ""}>
    <fieldset class="manual-form" ${busy || !view.ready ? "disabled" : ""}><legend>${e(t.regulation.manualControl)}</legend>
    <div class="manual-speed"><label for="speed">${e(t.regulation.commandSpeed)}</label><output id="speed-value" for="speed">${e(speed === 0 ? t.off : speed === 8 ? t.boost : speed)}</output><input id="speed" aria-describedby="manual-command-help" type="range" min="0" max="8" step="1" value="${e(speed)}"><div class="range-labels"><span>0 · ${e(t.off)}</span><span>1–7</span><span>8 · ${e(t.boost)}</span></div></div>
    <div class="grid spaced"><label>${e(t.mode)}<select id="control-mode"><option value="manual" ${mode === "manual" ? "selected" : ""}>${e(t.manual)}</option><option value="auto" ${mode === "auto" ? "selected" : ""}>${e(t.auto)}</option></select></label>${timerControls(a, t.regulation, view.duration, draft)}</div>
    <div class="actions spaced"><button class="primary" data-action="apply">${e(t.apply)}</button><span class="muted">${e(view.ready ? t.ready : t.waiting)}</span></div>
    <p id="manual-command-help" class="muted">${e(t.regulation.manualCommandHelp)}</p>
    <details data-disclosure="manual-help"><summary>${e(t.regulation.manualDetails)}</summary><p class="muted">${e(t.scope)} (${view.units.length})</p><p class="muted">${e(t.regulation.manualHoldHelp)}</p><p class="muted">${e(t.regulation.timerHelp)}</p></details></fieldset></div>`;
}
