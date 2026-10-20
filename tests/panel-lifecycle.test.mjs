import test, { after } from "node:test";
import assert from "node:assert/strict";
import { locales } from "../custom_components/wifimodule/frontend/locales.js";

// Keep the real panel methods; replace only the browser host and HA transport.
const previousHTMLElement = globalThis.HTMLElement;
const previousCustomElements = globalThis.customElements;
let Panel;
globalThis.HTMLElement = class {
  isConnected = true;

  attachShadow() {
    this.shadowRoot = { querySelector: () => null };
  }
};
globalThis.customElements = {
  define(_name, implementation) {
    Panel = implementation;
  },
};
await import("../custom_components/wifimodule/frontend/panel.js");
after(() => {
  if (previousHTMLElement === undefined) delete globalThis.HTMLElement;
  else globalThis.HTMLElement = previousHTMLElement;
  if (previousCustomElements === undefined) delete globalThis.customElements;
  else globalThis.customElements = previousCustomElements;
});

test("manual label agrees with its slider when the cloud has no manual speed", () => {
  const panel = new Panel();
  panel.t = locales.es;
  panel._hass = { language: "es" };
  panel.view = {
    building: { manual_speed: null, manual_active: false },
    units: [],
    ready: true,
    duration: 30,
  };

  for (const [speed, label, value] of [
    [null, "1", "1"],
    [undefined, "1", "1"],
    [0, "Apagado", "0"],
    [8, "Boost", "8"],
  ]) {
    panel.view.building.manual_speed = speed;
    const html = panel.manualControls();
    const shown = html.match(
      /<output id="speed-value"[^>]*>([^<]*)<\/output>/,
    )?.[1];
    const selected = html.match(/<input id="speed"[^>]*value="([^"]*)"/)?.[1];
    assert.equal(shown, label, `Label for manual speed ${speed}`);
    assert.equal(selected, value, `Slider for manual speed ${speed}`);
  }
});

test("reconnecting reloads pending history and ignores the old response", async (t) => {
  t.mock.method(globalThis, "setInterval", () => 1);
  t.mock.method(globalThis, "clearInterval", () => {});
  const requests = [];
  const panel = new Panel();
  panel.started = true;
  panel.entryId = "installation-a";
  panel.t = locales.es;
  panel.automatic = {
    sensors: { co2: ["sensor.room_co2"], tvoc: [], humidity: [], aqi: [] },
    candidates: {
      co2: [{ entity_id: "sensor.room_co2", name: "Room", unit: "ppm" }],
    },
    settings: { co2_target: 800, co2_full: 1500 },
  };
  const historyBox = { innerHTML: "" };
  panel.shadowRoot.querySelector = (selector) =>
    selector === "#quality-history" ? historyBox : null;
  panel._hass = {
    language: "es",
    callApi(method, path) {
      assert.equal(method, "GET");
      assert.match(path, /filter_entity_id=sensor.room_co2/);
      const response = Promise.withResolvers();
      requests.push(response);
      return response.promise;
    },
  };
  const samples = (value) => [
    [
      {
        entity_id: "sensor.room_co2",
        state: value,
        last_changed: new Date(Date.now() - 1000).toISOString(),
      },
    ],
  ];

  const originalLoad = panel.loadQualityHistory();
  panel.isConnected = false;
  panel.disconnectedCallback();
  panel.isConnected = true;
  panel.connectedCallback();
  assert.equal(
    requests.length,
    2,
    "Reconnect must replace the invalidated request",
  );

  requests[1].resolve(samples("900"));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(panel.qualityHistory.loading, undefined);
  assert.equal(panel.qualityHistory.series["sensor.room_co2"][0].state, "900");
  assert.match(historyBox.innerHTML, /<svg/);
  assert.doesNotMatch(historyBox.innerHTML, /Cargando el historial/);

  requests[0].resolve(samples("650"));
  await originalLoad;
  assert.equal(panel.qualityHistory.series["sensor.room_co2"][0].state, "900");
  panel.isConnected = false;
  panel.disconnectedCallback();
});

test("an expired off override does not preload Off over a fresh running state", () => {
  const panel = new Panel();
  panel.t = locales.es;
  panel._hass = { language: "es" };
  panel.automatic = {
    actual_speed: 4,
    sensors: { co2: [], tvoc: [], humidity: [], aqi: [] },
    candidates: {},
    settings: {},
  };
  panel.view = {
    building: { manual_speed: 0, manual_active: false },
    units: [{ name: "Test unit", values: { pwr: 1, spe: 4 } }],
    ready: true,
    duration: 30,
  };
  let html = panel.manualControls();
  assert.equal(html.match(/<input id="speed"[^>]*value="([^"]*)"/)?.[1], "4");
  panel.automatic.actual_speed = 0;
  panel.view.units[0].values.pwr = 0;
  html = panel.manualControls();
  assert.equal(
    html.match(/<output id="speed-value"[^>]*>([^<]*)<\/output>/)?.[1],
    "Apagado",
  );
});

test("an active off command stays distinct from the device's reported running speed", () => {
  const panel = new Panel();
  panel.t = locales.es;
  panel._hass = { language: "es" };
  panel.automatic = {
    actual_speed: 4,
    sensors: { co2: [], tvoc: [], humidity: [], aqi: [] },
    candidates: {},
    settings: {},
  };
  panel.view = {
    building: { manual_active: true, manual_speed: 0 },
    units: [{ name: "Test unit", values: { pwr: 1, spe: 4 } }],
    ready: true,
    duration: 30,
  };
  const html = panel.manualControls() + panel.content();
  assert.equal(html.match(/<input id="speed"[^>]*value="([^"]*)"/)?.[1], "0");
  assert.equal(html.match(/<dt>Velocidad<\/dt><dd>([^<]*)<\/dd>/)?.[1], "4");
});

test("an off unit card does not display the retained running speed", () => {
  const panel = new Panel();
  panel.t = locales.es;
  panel._hass = { language: "es" };
  panel.view = {
    building: { manual_active: false, manual_speed: 4 },
    units: [{ name: "Test unit", values: { pwr: 0, spe: 4 } }],
    ready: true,
    duration: 30,
  };
  const html = panel.content();
  assert.equal(
    html.match(/<dt>Velocidad<\/dt><dd>([^<]*)<\/dd>/)?.[1],
    "Apagado",
  );
});

function controlPanel(mode = 'manual') {
  const p = new Panel();
  p.t = locales.es;
  p._hass = {language:'es'};
  p.view = {building:{manual_speed:4,manual_mode:'manual',manual_bypass:true}, units:[{id:2,name:'Demo',values:{fil:3227,pwr:1,spe:4}}], ready:true,duration:30};
  const names=['min_speed','max_speed','co2_target','co2_full','tvoc_target','tvoc_full','humidity_target','humidity_full','aqi_target','aqi_full'];
  p.automatic={mode,enabled:mode==='automatic',status:mode,actual_speed:4,manual_speed:4,parameters:Object.fromEntries(names.map(k=>[k,[1,0,5000,1]])),settings:{},sensors:{co2:[],tvoc:[],humidity:[],aqi:[]},candidates:{},connection:{available:true,device_ready:true}};
  p.shadowRoot.querySelectorAll=()=>[];
  return p;
}

test('Manual controls belong to the initial control panel before sensor charts',()=>{
  const p=controlPanel();
  p.render();
  const html=p.shadowRoot.innerHTML;
  const center=html.match(/<section class="regulation"[\s\S]*?<\/section>/)?.[0]||'';
  assert.match(center,/id="speed"/);
  assert.match(center,/id="return-to"/);
  assert.match(center,/data-action="apply"/);
  assert.ok(html.indexOf('id="speed"')<html.indexOf('id="zone-cards"'));
  assert.equal((html.match(/id="regulation-bypass"/g)||[]).length,1);
  assert.doesNotMatch(html,/id="bypass"/);
});

test('Manual editor is visible only in Manual, with no duplicated controls',()=>{
  for(const mode of ['manual','automatic','schedule']){
    const p=controlPanel(mode);p.render();
    const tag=p.shadowRoot.innerHTML.match(/<div id="manual-controls"[^>]*>/)?.[0]||'';
    assert.ok(tag);
    assert.equal(/\bhidden\b/.test(tag),mode!=='manual');
    assert.equal((p.shadowRoot.innerHTML.match(/id="speed"/g)||[]).length,1);
  }
});

test('machine maintenance reports remaining days and keeps invalid counters unknown',()=>{
  const p=controlPanel();
  assert.match(p.content(),/134/);
  assert.match(p.content(),/días restantes/);
  p.view.units[0].values.fil=-1;
  assert.doesNotMatch(p.content(),/-1|134/);
  assert.match(p.content(),/Desconocido/);
});

test('changing independent bypass preserves an unapplied speed and timed return draft',async()=>{
  const p=controlPanel();
  p.entryId='demo';
  p.manualDraft={speed:3,mode:'manual',return_to:'automatic',duration:'2',unit:'60'};
  p._hass.callWS=async msg=>{
    if(msg.operation==='bypass')return {};
    if(msg.operation==='automatic')return p.automatic;
    if(msg.operation==='view')return p.view;
    throw Error('Unexpected operation');
  };
  p._hass.callApi=async()=>[];
  await p.mutate('bypass',{enabled:true});
  assert.deepEqual(p.manualDraft,{speed:3,mode:'manual',return_to:'automatic',duration:'2',unit:'60'});
  const html=p.manualControls();
  assert.match(html,/<input id="speed"[^>]*value="3"/);
  assert.match(html,/<option value="automatic" selected/);
  assert.match(html,/<option value="60" selected/);
});
