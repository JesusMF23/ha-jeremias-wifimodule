import test from 'node:test';
import assert from 'node:assert/strict';
import { timerInputs, timerSummary } from '../custom_components/wifimodule/frontend/control-options.js';
import { regulationLocales } from '../custom_components/wifimodule/frontend/regulation-locales.js';

test('hours convert to minutes with explicit return destination',()=>{
 const values={'#return-to':'automatic','#duration':'2','#duration-unit':'60','#speed':'3','#control-mode':'manual'};
 const root={querySelector:s=>({value:values[s]})};
 assert.deepEqual(timerInputs(root),{duration:120,return_to:'automatic'});
 values['#return-to']='none';
 assert.deepEqual(timerInputs(root),{duration:0,return_to:'none'});
 values['#return-to']='schedule';values['#duration']='0';
 assert.throws(()=>timerInputs(root));
});
test('countdown uses an absolute deadline and names the return target',()=>{
 const a={manual_timer:{return_to:'automatic',expires_at:'2026-10-07T12:30:00Z'}};
 assert.match(timerSummary(a,regulationLocales.es,Date.parse('2026-10-07T12:00:00Z')),/30/);
 assert.match(timerSummary(a,regulationLocales.es,Date.parse('2026-10-07T12:00:00Z')),/Automático/);
});

import { historySegments } from '../custom_components/wifimodule/frontend/dashboard.js';
test('VOC history uses each recorded unit when converting ppm to ppb',()=>{
 const rows=[{last_changed:'2026-10-07T12:00:00Z',state:'0.3',attributes:{unit_of_measurement:'ppm'}},{last_changed:'2026-10-07T12:01:00Z',state:'400',attributes:{unit_of_measurement:'ppb'}}];
 const start=Date.parse('2026-10-07T12:00:00Z'),end=start+120000;
 assert.deepEqual(historySegments(rows,start,end,'tvoc','ppb'),[[[start,300],[start+60000,300],[start+60000,400],[end,400]]]);
});
