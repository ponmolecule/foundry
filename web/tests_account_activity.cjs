const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const block=html.slice(html.indexOf('function _activityPath('),html.indexOf('var CAC_METHODS'));
let ids=0,renders=0,previews=0;
const ctx={cfg:{assumptions:{cac_feeds:{'Feed A':{customer_count_series_id:'customers',channels:[{name:'Channel'}]}}}},window:null,_seriesId:()=>`stable-${++ids}`,renderContent:()=>renders++,refresh:()=>previews++,esc:x=>String(x),_numInput:x=>String(x),_faSeriesEditor:(path,spec,label)=>`<div>${label}</div>`,lastRes:null};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(block,ctx);
// r436: _accountActivityOptions now calls _ensureLinkableSeriesIds (b887a61a8), defined outside the sliced block; load the real one and its helper.
const fnSrc=name=>{const i=html.indexOf('function '+name+'(');let d=0,j=html.indexOf('{',i);for(;j<html.length;j++){if(html[j]==='{')d++;else if(html[j]==='}'&&!--d)break;}return html.slice(i,j+1);};
vm.runInContext(fnSrc('_ensureLinkableSeriesIds')+'\n'+fnSrc('_cacEnsureDerivedIds'),ctx);
assert.equal(ctx._accountActivityOptions('account').length,1);
assert.equal(ctx._accountActivityOptions('account')[0].series_id,'customers::cumulative_gross_acquisitions');
// r436: the "Publish customer flows" button was removed in b887a61a8 (flows are available automatically) and r399 (77236a5ba)
// derives flow IDs without persisting activity_series_ids. Same behaviour proven: IDs are stable across reads and reads do not edit.
let f=ctx.cfg.assumptions.cac_feeds['Feed A'];const before=JSON.stringify(ctx._accountActivityOptions('transaction'));assert.equal(JSON.stringify(ctx._accountActivityOptions('transaction')),before);assert.equal(f.activity_series_ids,undefined);
assert.equal(JSON.stringify(ctx._accountActivityOptions('transaction').filter(x=>!x.label.includes('Channel')).map(x=>x.series_id)),JSON.stringify(['customers::new_customers','customers::lost_customers']));
assert.equal(ctx._accountActivityOptions('transaction').length,4);
ctx.addAccountAdoption('Feed A');const a=ctx.cfg.assumptions.account_adoption[0];assert.equal(a.opening_subscribers,0);assert.equal(a.exit_assumption,'proportional_customer_attrition');assert.equal(Object.keys(a.series_ids).length,4);assert.equal(ctx._accountActivityOptions('account').length,2);
const stable=JSON.stringify(a.series_ids);ctx.accountAdoptionMode(0,'gross_flows');assert(!a.target_share);assert(a.new_customer_adoption&&a.existing_customer_adoption&&a.closure_probability);assert.equal(a.closure_probability.period,'month');assert.equal(JSON.stringify(a.series_ids),stable);
a.name='Renamed population';assert(ctx._accountActivityOptions('transaction').some(x=>x.label.includes('Renamed population › Gross openings')));
ctx.accountAdoptionMode(0,'target_share');assert(a.target_share);assert(!a.closure_probability&&!a.new_customer_adoption);
assert(ctx._accountAdoptionHtml('Feed A').includes('Reconciling')||ctx._accountAdoptionHtml('Feed A').includes('reconcile'));
const costs=html.slice(html.indexOf('function _feeCostFactorSetKind('),html.indexOf('function _feeCostFactorTrajectory('));
ctx._stOwner=()=>({fee_streams:ctx.streams});ctx.streams=[{cost:{kind:'none',params:{}}}];ctx.setTimeout=fn=>fn();vm.runInContext(costs,ctx);ctx._feeCostFactorSetKind(0,0,'per_account');assert.equal(ctx.streams[0].cost.params.period,'month');assert.equal(ctx.streams[0].cost.params.cost_per_account,0);
assert(html.includes('<label>Billed per</label>')&&html.includes("setPath('${sb}.cost.params.period'")); // r436: 8c47b4ba3 (r346) relabelled 'Cost billing period' to 'Billed per'; same period select
assert(html.includes('Cost per account'));assert(html.includes('account-adoption-card .sec-managed-series-row>input{width:110px'));assert(html.includes('Customer flows / account adoption'));
assert(/^foundry-r(?:31[4-9]|3[2-9]\d|[4-9]\d{2}|\d{4,})-[a-z0-9-]+$/.test(fs.readFileSync(__dirname+'/../BUILD_STAMP','utf8').trim()));
console.log('PASS optional publishers, stable IDs, exclusive method switch, opening state, source choices, cost period and bounded controls');
