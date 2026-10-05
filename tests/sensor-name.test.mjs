import test from "node:test";
import assert from "node:assert/strict";
import { saveDeviceName } from "../custom_components/wifimodule/frontend/sensor-name.js";

test("rename persists the display name without changing entity identities or equipment", async () => {
  const writes = [];
  await saveDeviceName(
    { callWS: async (m) => writes.push(m) },
    "device-a",
    "  AirQ Salón  ",
  );
  assert.deepEqual(writes, [
    {
      type: "config/device_registry/update",
      device_id: "device-a",
      name_by_user: "AirQ Salón",
    },
  ]);
});
test("blank, oversized or missing device names never reach HA", async () => {
  let writes = 0;
  const hass = { callWS: async () => writes++ };
  for (const [id, name] of [
    ["a", "  "],
    ["a", "x".repeat(101)],
    [null, "Room"],
  ])
    await assert.rejects(saveDeviceName(hass, id, name));
  assert.equal(writes, 0);
});
test("HA rejection propagates so the editor can retain its draft", async () => {
  await assert.rejects(
    saveDeviceName(
      {
        callWS: async () => {
          throw Error("denied");
        },
      },
      "a",
      "Room",
    ),
    /denied/,
  );
});
