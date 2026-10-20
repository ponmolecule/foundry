const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
const ctx={window:{},cfg:{assumptions:{cac_feeds:{Acquisition:{}}}},lastRes:null,NP:()=>6,PPY:()=>12,renderContent(){},refresh(){},_seriesId:()=> 'id',esc:s=>String(s),_ensureWorkforce:()=>({roles:[role]})};
vm.createContext(ctx);
for(const name of ['_pf','_numInput','_cacMode'])vm.runInContext(html.split('\n').find(l=>l.startsWith('function '+name+'(')),ctx);
vm.runInContext(html.slice(html.indexOf('function _cacFeedSpec('),html.indexOf('function _cacEnsureDerivedIds(')),ctx);
vm.runInContext(html.split('\n').find(l=>l.startsWith('window.cacFeedValue=')),ctx);ctx.cacFeedValue=ctx.window.cacFeedValue;
const attr=html.slice(html.indexOf('// Attrition is a feed-level primitive,'),html.indexOf('      const _chCards=',html.indexOf('// Attrition is a feed-level primitive,')));
const renderFlat=attr.split('\n').find(l=>l.trim().startsWith('else h+='));assert(renderFlat);
ctx.fn='Acquisition';let last;
for(const typed of ['0.83333','0.833333333333333','12.3456789012345','0.000000123456789','0']){
 ctx.window.cacFeedValue('Acquisition',typed,'flat');
 const expected=Number(typed)/100;
 assert.equal(ctx.cfg.assumptions.cac_feeds.Acquisition.driver_specs.attrition_rate.value,expected);
 // Save/load then re-render and submit what the actual field displays.
 ctx.cfg=JSON.parse(JSON.stringify(ctx.cfg));ctx.asp=ctx.cfg.assumptions.cac_feeds.Acquisition.driver_specs.attrition_rate;ctx.h='';
 vm.runInContext(renderFlat.trim().replace(/^else /,''),ctx);
 const display=ctx.h.match(/<input[^>]*value="([^"]+)"/)[1];assert(ctx.h.includes('step="any"'));
 const handler=ctx.h.match(/<input[^>]*onchange="([^"]+)"/)[1];ctx.el={value:display};
 vm.runInContext('(function(){'+handler+'}).call(el)',ctx);
 const stored=ctx.cfg.assumptions.cac_feeds.Acquisition.driver_specs.attrition_rate.value;
 assert(Math.abs(stored-expected)<=Math.max(1e-24,Math.abs(expected)*1e-14),`${typed} -> ${display}`);
 if(typed==='0.83333'){assert.equal(display,'0.83333');last=stored;}
}
assert(!attr.includes('.toFixed(2)')); // flat, growth base, growth rate and explicit preview
const start=html.indexOf('// r357: read engine-owned FTE paths;'),end=html.indexOf('function _workforceCapacityOptions()',start);
vm.runInContext(html.slice(start,end),ctx);
const role={series_id:'ops',capacity_count:{}};
assert(ctx._workforceCapacityPreview(0,role).includes('Run the model successfully'));
ctx.lastRes={workforce:{series_ids:['other','ops'],counts:[[99,99,99,99,99,99],[0,0,1,1.5,2,3]]}};
assert.equal(ctx._workforceCapacityView(role).value,3);
assert(ctx._workforceCapacityCountHtml(role).includes('M6'));
const path=ctx._workforceCapacityPreview(0,role);assert(path.includes('1.5'));assert(path.includes('Calculated staffing period'));
const before=JSON.stringify(ctx.cfg);ctx.window.nieWorkforceCapacityPeriod(0,4);
assert.equal(ctx._workforceCapacityView(role).value,1.5);assert(ctx._workforceCapacityCountHtml(role).includes('M4'));
assert.equal(JSON.stringify(ctx.cfg),before,'period selection must not edit model inputs');
ctx.PPY=()=>4;assert(ctx._workforceCapacityPreview(0,role).includes('Average monthly active FTE'));
ctx.lastRes.workforce.series_ids=['other','removed'];assert.equal(ctx._workforceCapacityView(role).value,null);
ctx.lastRes.workforce.series_ids=['other','ops'];ctx.lastRes.workforce.counts[1]=[0,0,0,0,0,0];assert.equal(ctx._workforceCapacityView(role).value,0);
assert(html.includes('data-engine-preview="wf-capacity-count-'));assert(html.includes('data-engine-preview=\\"wf-capacity-row-')||html.includes('data-engine-preview="wf-capacity-row-'));
console.log(JSON.stringify({ok:true,typed_percent:'0.83333',stored_rate:last,checks:'actual attrition edit/save/reload/render/re-edit; staffing stable-ID results, fractional/zero FTE, period selection, missing results, quarterly units and script syntax'}));
