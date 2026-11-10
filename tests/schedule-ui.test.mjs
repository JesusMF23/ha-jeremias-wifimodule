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

test("copy shows independent day selections and applies the limit to the full batch", async () => {
  const { scheduleEditor, scheduleIssue } = await import(
    "../custom_components/wifimodule/frontend/schedule.js"
  );
  const rows = Array.from({ length: 51 }, (_, time) => ({
    time,
    speed: 1,
    bypass: false,
  }));
  const view = {
    profiles: [{ id: 10, name: "Test" }],
    modes: [],
    week: {},
    profile_id: 10,
    building: {},
  };
  const html = scheduleEditor(view, 1, rows, false, true, locales.es, [2, 4]);
  assert.doesNotMatch(html, /data-schedule-copy-day="1"/);
  assert.match(
    html,
    /<details[^>]+data-disclosure="schedule-copy">\s*<summary>/,
  );
  assert.match(
    html,
    /<input type="checkbox" data-schedule-copy-day="2" checked/,
  );
  assert.match(
    html,
    /<input type="checkbox" data-schedule-copy-day="4" checked/,
  );
  assert.match(html, /<input type="checkbox" data-schedule-copy-day="5">/);
  assert.match(html, /2 días seleccionados/);
  assert.equal(scheduleIssue(view, [2, 4], rows), "");
  assert.equal(scheduleIssue(view, [2, 4, 5], rows), "scheduleLimit");
});
