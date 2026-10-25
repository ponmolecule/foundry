// r399: reproduce the reported browse-only publication metadata drift, even
// when another authored edit has already made the engagement dirty.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{execFileSync}=require('node:child_process');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
function declaration(name){const start=html.indexOf('function '+name+'(');assert(start>=0,name);let p=html.indexOf('{',start),n=1;for(let i=p+1;i<html.length;i++){if(html[i]==='{')n++;if(html[i]==='}'&&!--n)return html.slice(start,i+1);}throw Error(name);}
const ch={name:'Channel',derived_series_ids:{new_customers:'channel-new',new_auc:'channel-auc'}};
const f={series_id:'feed-auc',customer_count_series_id:'feed-customers',owner_module:'customer_acquisition',channels:[ch]};
const ctx={cfg:{assumptions:{cac_feeds:{Practices:f}}},_seriesId:()=>{throw Error('Unexpected identity creation while browsing')}};ctx.window=ctx;vm.createContext(ctx);
for(const n of ['_cacEnsureDerivedIds','_cacFlowIds','_ensureLinkableSeriesIds','_accountActivityOptions','_cacrmIds'])vm.runInContext(declaration(n),ctx);
const json=()=>JSON.stringify(ctx.cfg);
function read(){ctx._ensureLinkableSeriesIds();return JSON.parse(JSON.stringify(ctx._accountActivityOptions('transaction')));}
const original=json();const opts=read();assert.equal(json(),original,'Browsing must not add activity maps');
assert.deepEqual(opts.map(x=>x.series_id),['feed-customers::new_customers','feed-customers::lost_customers','channel-new::new_customers','channel-new::lost_customers']);
assert.equal(opts.filter(x=>x.flow_kind==='new_customers').length,2,'Loan production still sees gross acquisitions');
assert(ctx._cacrmIds(f).includes('channel-new::new_customers'),'Remove-feed dependency checks see virtual flows');
assert.equal(json(),original,'Dependency browsing must remain read-only');
f.beginning_customers=42;const edited=json();for(let i=0;i<5;i++)read();assert.equal(json(),edited,'Browsing after a real edit must add no hidden changes');assert.notEqual(json(),original,'Authored input remains changed');
const server=JSON.parse(execFileSync('python3',['-c',`import json,sys
from foundry.v2.account_activity import ensure_flow_ids
c=json.load(sys.stdin);ensure_flow_ids(c['assumptions']);print(json.dumps(c))`],{input:json(),encoding:'utf8'}));
const sf=server.assumptions.cac_feeds.Practices;assert.equal(sf.activity_series_ids.new_customers,opts[0].series_id);assert.equal(sf.channels[0].activity_series_ids.new_customers,opts[2].series_id,'Virtual channel IDs match engine publishers');
f.activity_series_ids={new_customers:'existing-custom-new',lost_customers:'existing-custom-lost'};ch.activity_series_ids={new_customers:'existing-channel-new',lost_customers:'existing-channel-lost'};const custom=json();assert.equal(read()[0].series_id,'existing-custom-new');assert.equal(read()[2].series_id,'existing-channel-new');assert.equal(json(),custom,'Authored IDs remain untouched');
f.intra_period_path='straight_line';assert.equal(read().length,0,'No fabricated gross flow for straight-line interpolation');
console.log('PASS browse-only and already-dirty states, exact engine IDs, custom IDs, gross-flow eligibility and linked-feed removal detection');
