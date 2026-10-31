const fs=require('fs'),vm=require('vm'),assert=require('assert');
const h=fs.readFileSync('web/console_v2.html','utf8');
const st=(id,basis='account',ref)=>({name:id,quantity_series_id:id,basis,driver:ref?{source:'fee_stream_quantity',ref}:{source:'constant'}});
const a={obs_exposures:[{name:'Population',fee_streams:[st('count')]}],deposit_products:[{name:'Savings',fee_streams:[st('service','account','count'),st('balance','balance')]}],lending_products:[{name:'Loan',fee_streams:[st('loan-count','account','service'),st('flow','transaction')]}]};
let refreshes=0;
const ctx={cfg:{assumptions:a},catalogSources:()=>null,renderContent(){},refresh(){refreshes++},_seriesId:()=> 'new-id',_stOwner(i){return i>=2000?a.deposit_products[i-2000]:i>=1000?a.lending_products[i-1000]:a.obs_exposures[i]}};
vm.createContext(ctx);
vm.runInContext(h.slice(h.indexOf('function _feeQuantityOwners('),h.indexOf('function feeDeletionConsumers')),ctx);
vm.runInContext(h.slice(h.indexOf('function feeQuantityCandidates('),h.indexOf('function _feePctSemantics(')),ctx);
const before=JSON.stringify(a);
assert(ctx.feeQuantityCandidates(2000,0).some(x=>x.value==='count'));
assert(!ctx.feeQuantityCandidates(2000,0).some(x=>x.value==='loan-count')); // indirect cycle
assert(!ctx.feeQuantityCandidates(2000,0).some(x=>x.value==='balance')); // incompatible units
assert(ctx.feeQuantityCandidates(0,0).length===0); // all count candidates depend on this node
assert(ctx.feeQuantityLabel('loan-count').startsWith('Lending › Loan'));
assert.equal(JSON.stringify(a),before); // browsing is read-only
ctx.feeQuantitySelect(1000,0,'count');assert.equal(a.lending_products[0].fee_streams[0].driver.ref,'count');
ctx.feeQuantitySelect(2000,0,'loan-count');assert.equal(a.deposit_products[0].fee_streams[0].driver.ref,'loan-count');
assert.equal(refreshes,2);
assert(h.includes('if(_fi>=0&&["balance","transaction","account"].includes(basis))_drvOpts.push(["fee_stream_quantity"'));
console.log('PASS all-family picker, stable IDs, type filters, transitive cycle exclusion and read-only browsing');
