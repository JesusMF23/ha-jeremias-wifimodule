import { escapeText as e } from "./automatic.js";
import { historyInspector } from "./history-inspector.js";

export function selectedReadings(a) {
  if (!a) return [];
  return Object.entries(a.sensors).flatMap(([kind, ids]) =>
    ids.map((id) => ({
      kind,
      ...(a.candidates[kind]?.find((s) => s.entity_id === id) || {
        entity_id: id,
        name: id,
        zone_id: id,
        zone: id,
        value: null,
        valid: false,
      }),
    })),
  );
}
export function zoneCards(a, t) {
  const zones = new Map();
  for (const s of selectedReadings(a)) {
    const key = s.zone_id || s.entity_id;
    if (!zones.has(key))
      zones.set(key, {
        name: s.zone || s.name,
        deviceId: s.device_id,
        readings: [],
      });
    zones.get(key).readings.push(s);
  }
  if (!zones.size) return `<p class="empty-state">${e(t.chooseSensors)}</p>`;
  return `<div class="zone-grid">${[...zones.values()].map((z) => `<article class="zone-card"><div class="section-heading"><h3>${e(z.name)}</h3>${z.deviceId ? `<button type="button" data-rename-device="${e(z.deviceId)}" aria-label="${e(t.editName + ": " + z.name)}">${e(t.editName)}</button>` : ""}</div><div class="zone-values">${z.readings.map((s) => `<div><span class="eyebrow">${e(t.kinds[s.kind])}</span><strong>${s.valid ? e(s.value) : "—"} <small>${e(s.unit)}</small></strong><span class="reading-caption">${s.valid ? e(t.fresh) : e(t.unavailable)}${s.valid && s.age_seconds != null ? ` · ${e(s.age_seconds)} s` : ""}</span></div>`).join("")}</div></article>`).join("")}</div>`;
}

// Recorder is state history: step lines show each reported state until its next change.
// Unknown/unavailable samples explicitly break the line; they never become zero.
export function historySegments(samples, start, end, kind, sourceUnit) {
  return historySeries(samples, start, end, kind, sourceUnit).segments;
}

function historySeries(samples, start, end, kind, sourceUnit) {
  const limits = {
    co2: [250, 100000],
    tvoc: [0, 1000000],
    humidity: [0, 100],
    aqi: [0, 500],
  }[kind];
  const points = samples
    .map((p) => ({
      time: Date.parse(p.last_changed || p.last_updated),
      value:
        p.state == null || String(p.state).trim() === ""
          ? NaN
          : Number(p.state) *
            (kind === "tvoc" &&
            (p.attributes?.unit_of_measurement ?? sourceUnit) === "ppm"
              ? 1000
              : 1),
    }))
    .filter((p) => Number.isFinite(p.time) && p.time <= end)
    .sort((a, b) => a.time - b.time);
  const segments = [];
  const recordedTimes = [];
  let endValue = null;
  let current = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i],
      until = Math.min(end, points[i + 1]?.time ?? end);
    if (
      !Number.isFinite(p.value) ||
      p.value < limits[0] ||
      p.value > limits[1]
    ) {
      endValue = null;
      if (current.length) segments.push(current);
      current = [];
      continue;
    }
    endValue = p.value;
    if (until < start || (until === start && p.time < start)) continue;
    if (p.time >= start) recordedTimes.push(p.time);
    current.push(
      [Math.max(start, p.time), p.value],
      [Math.max(start, until), p.value],
    );
  }
  if (current.length) segments.push(current);
  return { segments, recordedTimes, endValue };
}
export function historyChartData(a, history) {
  if (!a || !history?.series) return [];
  const { start, end } = history;
  const readings = selectedReadings(a);
  return Object.keys(a.sensors)
    .filter((kind) => a.sensors[kind].length)
    .map((kind) => {
      const series = readings
        .filter((s) => s.kind === kind)
        .map((s) => ({
          ...s,
          ...historySeries(
            history.series[s.entity_id] || [],
            start,
            end,
            kind,
            s.source_unit,
          ),
        }));
      if (!series.some((s) => s.segments.length)) return { kind };
      const low = a.settings[kind + "_target"];
      const high = a.settings[kind + "_full"];
      let min = low;
      let max = high;
      for (const s of series)
        for (const segment of s.segments)
          for (const [, value] of segment) {
            min = Math.min(min, value);
            max = Math.max(max, value);
          }
      const pad = Math.max(1, (max - min) * 0.1);
      return {
        kind,
        series,
        start,
        end,
        low,
        high,
        x: (time) => 48 + ((time - start) / (end - start)) * 660,
        y: (value) => 166 - ((value - min + pad) / (max - min + pad * 2)) * 144,
        inspector: historyInspector(series, start, end),
      };
    });
}

function chart(model, t, language) {
  const { kind, series, start, end, low, high, x, y, inspector } = model;
  if (!inspector)
    return `<article class="chart-card"><h3>${e(t.kinds[kind])}</h3><p class="empty-state">${e(t.historyEmpty)}</p></article>`;
  const path = (points) =>
    points
      .map(
        ([time, val], i) =>
          `${i ? "L" : "M"}${x(time).toFixed(1)},${y(val).toFixed(1)}`,
      )
      .join(" ");
  const date = (time) =>
    new Date(time).toLocaleString(language, {
      ...(end - start > 86400000 ? { month: "short", day: "numeric" } : {}),
      hour: "2-digit",
      minute: "2-digit",
    });
  const colors = [
    "var(--primary-color,#007f83)",
    "var(--warning-color,#c27800)",
    "var(--info-color,#4267c9)",
    "var(--error-color,#c64040)",
  ];
  return `<article class="chart-card" data-quality-chart="${kind}"><div class="section-heading"><h3>${e(t.kinds[kind])}</h3><span class="muted">${e(series[0].unit)}</span></div><svg class="quality-chart" viewBox="0 0 728 200" role="img" aria-label="${e(t.kinds[kind] + " · " + t.evolution)}"><title>${e(t.historyDescription)}</title>${[low, high].map((v) => `<line class="chart-guide" x1="48" x2="708" y1="${y(v)}" y2="${y(v)}"/><text class="chart-label" x="2" y="${y(v) + 4}">${e(v)}</text>`).join("")}${series.map((s, i) => s.segments.map((g) => `<path d="${path(g)}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="2.5" ${i >= colors.length ? 'stroke-dasharray="6 3"' : ""}/>`).join("")).join("")}${[start, (start + end) / 2, end].map((time, i) => `<text class="chart-label" x="${x(time)}" y="193" text-anchor="${["start", "middle", "end"][i]}">${e(date(time))}</text>`).join("")}
    <line data-chart-cursor hidden y1="16" y2="170" class="chart-cursor"/>
    ${series.map((_, i) => `<circle data-chart-dot hidden r="5" class="chart-dot" fill="${colors[i % colors.length]}"/>`).join("")}
    </svg><div class="chart-legend">${series.map((s, i) => `<span><i style="background:${colors[i % colors.length]}"></i>${e(s.zone || s.name)}</span>`).join("")}</div>
    <label class="chart-explore"><span>${e(t.historyExplore)}</span><input type="range" data-chart-scrubber min="0" max="${Math.max(1, inspector.times.length - 1)}" value="${inspector.times.length - 1}" aria-label="${e(t.kinds[kind] + " · " + t.historyExplore)}"></label>
    <div class="chart-selection" data-chart-details hidden><div class="section-heading"><time></time><button type="button" data-chart-close>${e(t.historyClose)}</button></div><dl>${series.map((s, i) => `<dt><i style="background:${colors[i % colors.length]}"></i>${e(s.zone || s.name)}</dt><dd></dd>`).join("")}</dl></div>
    <details><summary>${e(t.historyValues)}</summary><div class="table-wrap"><table><thead><tr><th>${e(t.zones)}</th><th>${e(t.minimum)}</th><th>${e(t.maximum)}</th><th>${e(t.last)}</th></tr></thead><tbody>${series
      .map((s) => {
        const v = s.segments.flatMap((g) => g.map((p) => p[1]));
        return `<tr><td>${e(s.name)}</td><td>${v.length ? e(v.reduce((a, b) => Math.min(a, b), Infinity)) : "—"}</td><td>${v.length ? e(v.reduce((a, b) => Math.max(a, b), -Infinity)) : "—"}</td><td>${v.length ? e(v.at(-1)) : "—"}</td></tr>`;
      })
      .join("")}</tbody></table></div></details></article>`;
}
export function historyCharts(
  a,
  history,
  t,
  language,
  charts = historyChartData(a, history),
) {
  if (!history || history.loading)
    return `<p class="empty-state" role="status">${e(t.historyLoading)}</p>`;
  if (history.error)
    return `<p class="notice error" role="status">${e(t.historyError)}</p>`;
  if (!charts.length) return `<p class="empty-state">${e(t.chooseSensors)}</p>`;
  return `<div class="charts">${charts
    .map((model) => chart(model, t, language))
    .join("")}</div><p class="muted chart-note">${e(t.historyDescription)}</p>`;
}
export function dashboard(a, history, hours, t, language, charts) {
  return `<section class="air-quality"><div class="section-heading"><h2>${e(t.airQuality)}</h2><span class="muted">${e(t.selectedZones)}</span></div><div id="zone-cards">${zoneCards(a, t)}</div><div class="section-heading spaced"><h3>${e(t.evolution)}</h3><div class="actions"><div class="segmented" role="group" aria-label="${e(t.period)}">${[
    [6, "6 h"],
    [24, "24 h"],
    [168, "7 d"],
  ]
    .map(
      ([v, l]) =>
        `<button data-history-hours="${v}" aria-pressed="${hours === v}">${l}</button>`,
    )
    .join(
      "",
    )}</div><button data-history-refresh aria-label="${e(t.historyRefresh)}">↻</button></div></div><div id="quality-history">${historyCharts(a, history, t, language, charts)}</div></section>`;
}
