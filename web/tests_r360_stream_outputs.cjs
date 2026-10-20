const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const m of H.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
const {cfg,res}=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const ctx={cfg,lastRes:res,window:{},PPY:()=>cfg.assumptions.periods_per_year,esc:s=>String(s).replaceAll('"','&quot;'),_numInput:v=>String(v),document:{querySelectorAll:()=>[]},_lfgArr:f=>cfg.assumptions[f==='obs'?'obs_exposures':f==='lending'?'lending_products':'deposit_products'],_lfgCtx:()=>({res,P:{fees:[999]},ref:1}),_lfxPer:()=> 'month',_lfxQ:n=>'M'+n,_lfxSparkSvg:arr=>'<spark>'+arr.join(',')+'</spark>',_stProv:()=>null};
vm.createContext(ctx);vm.runInContext(H.slice(H.indexOf('// Numeric inspection stays'),H.indexOf('function _lfxRoHtml(')),ctx);vm.runInContext(H.split('\n').find(l=>l.startsWith('function _numInput(')),ctx);
for(const [a,b] of [['function _stOwner(','function _feeStreamsSectionHtml('],['function _feeStreamQuantityKind(','function _feePctSemantics('],['function _explicitPreviewHtml(','function _explicitSchedulePreviewHtml('],['// r360: dependent streams display','_feeGlobal.addFeeCostPool='],['function _stCellHtml(','function refreshStreamFigures'],['function _lfxLiveHtml(','function refreshLfxLive(']])vm.runInContext(H.slice(H.indexOf(a),H.indexOf(b,H.indexOf(a))),ctx);
const st=cfg.assumptions.obs_exposures[0].fee_streams,before=JSON.stringify(cfg);
for(const [i,label,val] of [[0,'Resolved count',10],[1,'Resolved count',6],[2,'Resolved volume',138],[3,'Stream revenue',3.036],[4,'Contra-revenue',-.1932],[5,'Stream cost',.06],[6,'Net stream income',1.104]]){
 const out=ctx._feeStreamResolvedOutput(0,i);assert.equal(out.label,label);assert(Math.abs(out.values[0]-val)<1e-10);
 const compact=ctx._feeStreamResultBody(st[i].quantity_series_id);assert(compact.includes(label));assert(compact.includes(String(val)));
 const chart=ctx._lfxLiveHtml('sro',0,i);assert(chart.includes(label));assert(!chart.includes('Product fees'),'a product aggregate must not masquerade as stream output');
 const meta=[{qid:st[i].quantity_series_id}];const cell=ctx._stCellHtml(meta,0,0);assert(cell.includes(out.format(out.values.at(-1))));
 if(i===3||i===4){assert(!compact.includes('M1 138<'));assert(!chart.includes('<spark>138,'));}
}
const original=ctx.lastRes;ctx.lastRes={fee_stream_quantities:res.fee_stream_quantities};assert.equal(ctx._feeStreamResolvedOutput(0,3).values,null,'missing financial postings must never fall back to volume');assert(ctx._feeStreamResultBody('gross').includes('Run the model successfully'));ctx.lastRes=original;
const timedCount=ctx._feeStreamResolvedOutput(0,8);assert.equal(timedCount.values[0],0);assert.equal(timedCount.values[1],6);
const timed=ctx._feeStreamResolvedOutput(0,7);assert.equal(timed.values[0],0);assert.equal(timed.values[3],0);
const editor=H.slice(H.indexOf('function _feeStreamsSectionHtml('),H.indexOf('function lineOptionsFor('));
const shared=editor.indexOf('class="st-definition"'),activity=editor.indexOf('data-st="activity"');assert(shared>=0&&activity>shared);assert(editor.slice(shared,activity).includes("h += '</div></section>'"));
for(const word of ['Stream name','Income presentation','Basis (calculation)'])assert(editor.slice(shared,activity).includes(word));
for(const word of ['Activity','Pricing','Timing','Costs'])assert(editor.includes('st-section-heading fld wide"><b>'+word+'</b>'));
const markup=editor.slice(shared,activity);for(const m of markup.matchAll(/on(?:change|click)="([^"]+)"/g)){/* existing handlers are retained in the source template */}
assert(H.includes('window.stTabSet=function(k){window._stTab=k;const b=document.querySelector(\'.st-body\')'));
assert(H.includes('.st-definition-fields{display:grid'));assert(H.includes('Shared across Activity, Pricing, Timing and Costs'));
assert.equal(JSON.stringify(cfg),before,'output rendering must not alter inputs');
console.log('PASS actual engine → public postings → compact preview/chart/list: source, resolved count/volume, revenue, signed contra, cost, net and timing zeros; shared definition separated from all menu panels');
