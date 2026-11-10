const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/console_v2.html','utf8');
const spec={source:'entered',trajectory:'explicit',cadence:'month',values:Array(60).fill(1)},f={kind:'entered',periodized:false,spec};
const c={factors:[f]},sandbox={window:{},_ensureNieFormulaDriver:()=>c,_seriesCadenceOptions:()=>['year','quarter','month'],_seriesResolutionUseful:v=>v!=='month',esc:String,renderContent:()=>{},refresh:()=>{},_resizeSeriesValues:s=>{const n={year:5,quarter:20,month:60}[s.cadence];s.values=s.values.slice(0,n);while(s.values.length<n)s.values.push(s.values.at(-1)||0);}};
// r480: a cadence change seeds an empty schedule but never pads or cuts entered values (the mismatch is flagged in the preview).
sandbox._seedSeriesIfEmpty=(sp,fill)=>{sp.values=sp.values||[];if(!sp.values.length)sandbox._resizeSeriesValues(sp,fill);};
vm.createContext(sandbox);
vm.runInContext(html.slice(html.indexOf('window.nieCatFormulaScheduleCadence='),html.indexOf('window.nieCatFormulaExplicitClear=')),sandbox);
const before=JSON.stringify(f);let markup=sandbox._opexFormulaScheduleControls(0,0,0,f,'month');assert.equal(JSON.stringify(f),before);assert(markup.includes('Formula factor schedule cadence'));assert(!markup.includes('Between source points'));
sandbox.window.nieCatFormulaScheduleCadence(0,0,0,'year');assert.equal(spec.cadence,'year');assert.equal(spec.values.length,60,'r480: entered values are kept, not cut to 5');assert.equal(spec.resolution,'step');assert.equal(f.periodized,false);
markup=sandbox._opexFormulaScheduleControls(0,0,0,f,'year');assert(markup.includes('Between source points'));assert(markup.includes('Hold'));assert(markup.includes('Interpolate'));
sandbox.window.nieCatFormulaScheduleResolution(0,0,0,'smooth');assert.equal(spec.resolution,'smooth');sandbox.window.nieCatFormulaScheduleResolution(0,0,0,'step');
const entered=JSON.stringify(f);sandbox.window.nieCatFormulaScheduleCadence(0,0,0,'bad');assert.equal(JSON.stringify(f),entered);
f.periodized=true;const periodized=JSON.stringify(f);sandbox.window.nieCatFormulaScheduleCadence(0,0,0,'quarter');assert.equal(JSON.stringify(f),periodized);assert(!sandbox._opexFormulaScheduleControls(0,0,0,f,'year').includes('<select'));
// Both editor paths use the common control; whole inline scripts remain syntactically valid.
assert.equal((html.match(/\$\{_opexFormulaScheduleControls\(i,j,k,f,cad\)\}/g)||[]).length,2);
for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))if(match[1].trim())new vm.Script(match[1]);
console.log('PASS r474 editor handlers, cadence change keeps values (r480), Hold default, interpolation, periodized guard, inert rendering, both editor paths and inline script syntax');
