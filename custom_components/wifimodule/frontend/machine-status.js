import { escapeText as e } from "./automatic.js";

export function machineCards(units, t) {
  return units
    .map((u) => {
      const hours = u.values?.fil;
      const days =
        Number.isInteger(hours) && hours >= 0 ? Math.floor(hours / 24) : null;
      return `<article class="card"><h3>${e(u.name)}</h3><div class="filter-life"><span class="eyebrow">${e(t.filter)}</span><strong>${days == null ? e(t.unknown) : e(days)}</strong>${days == null ? "" : `<span>${e(t.remainingDays)}</span>`}</div><dl><dt>${e(t.power)}</dt><dd>${u.values?.pwr === 1 ? e(t.on) : u.values?.pwr === 0 ? e(t.off) : e(t.unknown)}</dd><dt>${e(t.speed)}</dt><dd>${u.values?.pwr === 0 ? e(t.off) : e(u.values?.spe ?? t.unknown)}</dd><dt>${e(t.errors)}</dt><dd>${e(u.values?.err ?? t.unknown)}</dd></dl><small>${e(t.lastComm)}: ${e(u.last_comm)}</small></article>`;
    })
    .join("");
}
