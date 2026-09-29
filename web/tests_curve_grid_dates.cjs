const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync(__dirname + '/console_v2.html', 'utf8');
function source(name) {
  const start = html.indexOf('function ' + name + '(');
  assert.ok(start >= 0, name);
  const open = html.indexOf('{', start);
  let depth = 1, end = open + 1;
  while (depth) {
    if (html[end] === '{') depth++;
    if (html[end] === '}') depth--;
    end++;
  }
  return html.slice(start, end);
}
const cfg = {assumptions:{rate_curves:{
  sofr:{path_q:Array(12).fill(.04),longer_run:.0325,edited:true},
  fomc:{anchors:{'2027-12-31':.04}},
  current_policy:{mid:.04,observation_date:'2026-09-28'}, offsets:{sofr:.0005}
},rate_path_q:[]}};
const context = {cfg,CURVE_OFFSET_DEFAULT:{sofr:.0005},HALF_BAND_DEFAULT:.00125,
  _isoUTC:d=>d.toISOString().slice(0,10),
  _modelQuarterEnd:q=>new Date(Date.UTC(2028,3*q,0)),
  scheduleAutosave:()=>{},refresh:()=>{}};
vm.createContext(context);
for (const name of ['_policyMidAnchors','_curveDatedAnchors','_syncCurveGridDated','setCurveCell'])
  vm.runInContext(source(name),context);
// An r194 saved manual path has no dated_anchors. Editing one cell restores
// every grid point at its displayed date, not at the old ordinal month.
context.setCurveCell('sofr',8,'3.12');
context.setCurveCell('sofr',11,'3.12');
assert.ok(Math.abs(cfg.assumptions.rate_curves.sofr.dated_anchors['2030-03-31']-.0312)<1e-12);
assert.ok(Math.abs(cfg.assumptions.rate_curves.sofr.dated_anchors['2030-12-31']-.0312)<1e-12);
assert.equal(cfg.assumptions.rate_curves.sofr.dated_anchors['2030-10-31'],undefined);
console.log('Manual curve edits retain calendar quarter-end dates.');
