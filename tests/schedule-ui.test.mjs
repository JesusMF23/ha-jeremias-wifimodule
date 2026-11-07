import assert from "node:assert/strict";
import test from "node:test";
import { locales } from "../custom_components/wifimodule/frontend/locales.js";

test("a fresh schedule exposes direct speeds and bypass without a saved mode", async () => {
  const { scheduleEditor } = await import(
    "../custom_components/wifimodule/frontend/schedule.js"
  );
  const view = {
    profiles: [],
    modes: [],
    week: {},
    profile_id: null,
    building: {},
  };
  const html = scheduleEditor(
    view,
    1,
    [{ time: 0, speed: 2, bypass: true }],
    false,
    true,
    locales.es,
  );
  assert.equal((html.match(/data-schedule-day=/g) || []).length, 7);
  assert.match(html, /value="speed:2" selected/);
  assert.match(html, /data-schedule-bypass="0" checked/);
  assert.match(html, /00:00[^<]*–[^<]*24:00/);
  assert.match(html, /Cambios sin guardar/);
});
