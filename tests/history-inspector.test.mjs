import assert from "node:assert/strict";
import test from "node:test";
import * as dashboard from "../custom_components/wifimodule/frontend/dashboard.js";
import { regulationLocales } from "../custom_components/wifimodule/frontend/regulation-locales.js";

test("chart inspection snaps to recorded changes and preserves unavailable gaps", () => {
  const candidate = (entity_id, zone) => ({ entity_id, zone, unit: "ppm" });
  const sensorA = candidate("sensor.a", "Living room");
  const sensorB = candidate("sensor.b", "Bedroom");
  const automatic = {
    settings: { co2_target: 800, co2_full: 1500 },
    sensors: { co2: [sensorA.entity_id, sensorB.entity_id] },
    candidates: { co2: [sensorA, sensorB] },
  };
  const sample = (time, state) => ({
    last_changed: new Date(time).toISOString(),
    state,
  });
  const history = {
    start: 0,
    end: 10000,
    series: {
      [sensorA.entity_id]: [
        sample(-1000, "600"),
        sample(1000, "650"),
        sample(4000, "unavailable"),
        sample(7000, "800"),
      ],
      [sensorB.entity_id]: [
        sample(3000, "750"),
        sample(4000, "710"),
        sample(10000, "720"),
      ],
    },
  };
  const chart = dashboard.historyChartData(automatic, history)[0];
  assert.equal(chart.inspector.nearest(3900), 2);
  assert.deepEqual(chart.inspector.times, [1000, 3000, 4000, 7000, 10000]);
  assert.deepEqual(chart.inspector.readings(2), [null, 710]);
  assert.deepEqual(chart.inspector.readings(3), [800, 710]);
  assert.deepEqual(chart.inspector.readings(4), [800, 720]);
  assert.match(
    dashboard.historyCharts(automatic, history, regulationLocales.en, "en"),
    /type="range"[^>]*data-chart-scrubber/,
  );
});
