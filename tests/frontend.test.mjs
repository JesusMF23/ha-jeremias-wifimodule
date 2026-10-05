import test from 'node:test';
import assert from 'node:assert/strict';
import {historySegments,historyCharts,zoneCards} from '../custom_components/wifimodule/frontend/dashboard.js';
import {automaticCard,automaticInputs,automaticStatus} from '../custom_components/wifimodule/frontend/automatic.js';
import {regulationLocales as locales} from '../custom_components/wifimodule/frontend/regulation-locales.js';
const at = n => new Date(n*1000).toISOString();
const row = (n,state) => ({last_changed:at(n),state});
test('history preserves reported steps, bounds and unavailable gaps',()=>{
 assert.deepEqual(historySegments([row(-1,'600'),row(2,'700'),row(4,'unavailable'),row(7,'800')],0,10000,'co2'),[[[0,600],[2000,600],[2000,700],[4000,700]],[[7000,800],[10000,800]]]);
 assert.deepEqual(historySegments([row(0,'unknown'),row(1,''),row(2,null),row(3,'NaN'),row(4,'0')],0,10000,'co2'),[]);
 assert.deepEqual(historySegments([row(0,'0')],0,10000,'tvoc'),[[[0,0],[10000,0]]]);
});
const a = {enabled:false,status:'manual',actual_speed:0,target_speed:null,settings:{min_speed:0,co2_target:800,co2_full:1500},parameters:{min_speed:[1,0,7,1],max_speed:[7,1,7,1],co2_target:[800,300,5000,10],co2_full:[1500,400,10000,10],tvoc_target:[300,0,5000,10],tvoc_full:[1000,1,10000,10],humidity_target:[60,20,95,1],humidity_full:[75,21,100,1],aqi_target:[50,0,499,1],aqi_full:[200,1,500,1]},sensors:{co2:['sensor.demo'],tvoc:[],humidity:[],aqi:[]},candidates:{co2:[{entity_id:'sensor.demo',name:'<script>bad</script>',zone:'<room>',zone_id:'demo',valid:true,value:650,unit:'ppm'}]},connection:{available:true,device_ready:true},source:{name:'OLD',kind:'co2',value:1200},invalid_sensors:[]};
test('cards escape registry names, keep zero and do not show old manual demand',()=>{
 assert.match(zoneCards(a,locales.es),/&lt;room&gt;/);
 const status=automaticStatus(a,locales.es);
 assert.match(status,/Apagado/); assert.doesNotMatch(status,/OLD/);
 const form=automaticCard(a,locales.es,false);
 assert.match(form,/type="checkbox"/);assert.doesNotMatch(form,/<select multiple/);
 assert.match(form,/data-auto-setting="min_speed"[^>]+min="0"[^>]+value="0"/);
});
test('empty history is honest and numeric history exposes accessible data',()=>{
 assert.match(historyCharts(a,{series:{},start:0,end:10000},locales.es,'es'),/No hay mediciones/);
 const html=historyCharts(a,{series:{'sensor.demo':[row(0,'650'),row(5,'700')]},start:0,end:10000},locales.es,'es');
 assert.match(html,/<svg/); assert.match(html,/<table>/);assert.doesNotMatch(html,/<script>/);assert.match(html,/&lt;script&gt;/);
});
test('large retained histories do not exceed JavaScript argument limits',()=>{
 const samples=Array.from({length:140000},(_,i)=>row(i,i%2?'600':'700'));
 assert.match(historyCharts(a,{series:{'sensor.demo':samples},start:0,end:140000000},locales.es,'es'),/<svg/);
});
test('checkbox input persists empty groups and numeric zero',()=>{
 const group={dataset:{sensorGroup:'co2'},querySelectorAll:()=>[{value:'sensor.demo'}]};
 const empty={dataset:{sensorGroup:'tvoc'},querySelectorAll:()=>[]};
 const root={querySelectorAll:s=>s==='[data-auto-setting]'?[{dataset:{autoSetting:'min_speed'},value:'0'}]:[group,empty]};
 assert.deepEqual(automaticInputs(root),{settings:{min_speed:0},sensors:{co2:['sensor.demo'],tvoc:[]}});
});
test('English and Spanish UI keys remain in parity',()=>{
 const keys=o=>Object.entries(o).flatMap(([k,v])=>typeof v==='object'?keys(v).map(s=>k+'.'+s):[k]).sort();
 assert.deepEqual(keys(locales.en),keys(locales.es));
});


test("zone names can be edited only for registered devices and stay escaped", () => {
  const a = {sensors:{co2:["sensor.a", "sensor.b"]}, candidates:{co2:[
    {entity_id:"sensor.a", device_id:"device-a", zone_id:"device-a", zone:'Room <one>', valid:true, value:800},
    {entity_id:"sensor.b", zone_id:"sensor.b", zone:"Standalone", valid:true, value:700}
  ]}};
  const html = zoneCards(a, locales.en);
  assert.match(html, /data-rename-device="device-a"/);
  assert.equal((html.match(/data-rename-device=/g)||[]).length,1);
  assert.match(html, /Room &lt;one&gt;/);
  assert.doesNotMatch(html, /Room <one>/);
});

test('manual target and schedule selection are distinct from sensor pause',()=>{
 const manual={...a,mode:'manual',manual_speed:0,actual_speed:4,status:'manual_pending'};
 assert.match(automaticCard(manual,locales.es,false),/data-action="automatic-manual" aria-pressed="true"/);
 assert.match(automaticStatus(manual,locales.es),/Apagado/);
 const scheduled={...manual,mode:'schedule',manual_speed:null,status:'schedule'};
 const html=automaticCard(scheduled,locales.es,false);
 assert.match(html,/data-action="automatic-manual" aria-pressed="false"/);
 assert.match(html,/data-action="automatic-schedule" aria-pressed="true"/);
 assert.match(html,/Horario Jeremias/);
});
