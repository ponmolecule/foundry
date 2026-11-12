// r488: a shared assumption is edited in a visible, labelled panel that names every product using it.
// Replaces the "Edit shared assumption · changes affect every consumer" disclosure line. UI only.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
assert(!H.includes('<summary>Edit shared assumption'),'the disclosure line is gone');
let seq=0;const ctx={cfg:{assumptions:{lending_products:[{name:'Receivable Advances',balance_driver:{average_balance_per_customer_spec:{source:'entered',trajectory:'flat',value:17}}},{name:'Business Card',balance_driver:{average_balance_per_customer_spec:{source:'entered',trajectory:'flat',value:5}}}]}},window:{},renderContent(){ctx.renders++;},renders:0,refresh(){},esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),_seriesId:()=>`stable-${++seq}`,lastRes:null,PPY:()=>12,_nativeFlowPeriod:()=>'month',_numInput:v=>String(v),fmtComma:v=>String(v),fmtField(){},_seriesSourcePeriods:()=>[]};
vm.createContext(ctx);vm.runInContext(H.slice(H.indexOf('// Reusable shared assumptions'),H.indexOf('function _loanBalanceMode(')),ctx);
for(const name of ['_faSeriesEnsure','faSeriesTrajectory','faSeriesValue']){const line=H.split('\n').find(l=>l.startsWith((name.startsWith('_')?'function ':'window.')+name+(name.startsWith('_')?'(':'=')));vm.runInContext(line,ctx);}
ctx._faSeriesExplicitIsOpen=()=>false;const a=H.indexOf('function _faSeriesEditor('),b=H.indexOf('// ===== r340:',a);vm.runInContext(H.slice(a,b),ctx);
ctx.loanAmountMode(0,'shared');ctx.loanSharedStart(0);vm.runInContext("_loanSharedDraft.get(cfg.assumptions.lending_products[0]).name='Annual TPV per practice'",ctx);ctx.loanSharedCreate(0);
const sid=ctx.cfg.assumptions.balance_components_model.inputs[0].id,P=ctx.cfg.assumptions.lending_products;
const render=i=>ctx._loanAmountEditor(i,P[i],'assumptions.lending_products.'+i);
// Closed: the panel, its name, summary, usage and a real button are all visible; the editor is not.
let h=render(0);
assert(h.includes('class="shared-panel"'),'panel rendered');assert(h.includes('<span class="shared-tag">Shared assumption</span>'));
assert(h.includes('<b>Annual TPV per practice</b>'));assert(/Weighted average · 1 component · /.test(h),'summary');
assert(h.includes('Used by 1 product<'),'usage count');assert(h.includes('Receivable Advances <span class="shared-use-fam">Lending · this product</span>'));
assert(/<button type="button" class="shared-edit-btn" aria-expanded="false"[^>]*>Edit shared assumption<\/button>/.test(h),'real button, collapsed');
assert(!h.includes('shared-weighted-editor')&&!h.includes('shared-impact'),'editor hidden until asked for');
assert(h.includes('This product only'),'product-only settings labelled');
// Open: impact note before the editor.
const r0=ctx.renders;ctx.sharedPanelToggle(sid);assert.equal(ctx.renders,r0+1,'toggle re-renders');h=render(0);
assert(h.includes('class="shared-panel open"')&&/aria-expanded="true"[^>]*>Done editing</.test(h));
assert(h.indexOf('shared-impact')<h.indexOf('shared-weighted-editor'),'impact note precedes editor');
assert(h.includes('Only this product uses it today.'));
// A second product selects it: both are named, and the impact note says so.
ctx.loanAmountMode(1,'shared');ctx.loanSharedSelect(1,sid);h=render(0);
assert(h.includes('Used by 2 products<'));assert(h.includes('Business Card <span class="shared-use-fam">Lending</span>'));
assert(h.includes('<b>Changes apply everywhere.</b> Edits here change 2 products: Receivable Advances, Business Card.'));
const h1=render(1);assert(h1.includes('Business Card <span class="shared-use-fam">Lending · this product</span>'),'this product marked per view');
assert(h1.includes('class="shared-panel open"'),'open state is per assumption, shared across its consumers');
ctx.sharedPanelToggle(sid);assert(!render(0).includes('shared-weighted-editor'),'Done editing closes it');
console.log('PASS r488 shared-assumption panel: visible name, summary, consumers and edit button; impact note names every product before the editor; product-only settings labelled');
