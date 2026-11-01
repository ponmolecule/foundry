const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync('web/console_v2.html','utf8');
const st={driver:{source:'fee_stream_quantity',trajectory:'derived',params:{}}},ctx={_stOwner:()=>({fee_streams:[st]}),renderContent(){},refresh(){}};vm.createContext(ctx);
vm.runInContext(H.slice(H.indexOf('function feeCountActivityChange('),H.indexOf('function _stOwner(')),ctx);
ctx.feeCountActivityChange(2000,0,'positive_monthly_change');assert.equal(st.driver.quantity_transform,'positive_monthly_change');assert.equal(st.driver.trajectory,'flat');assert.equal(st.driver.opening_count,undefined);
st.driver.opening_count=7;ctx.feeCountActivityChange(2000,0,'');assert(!('quantity_transform' in st.driver));assert(!('opening_count' in st.driver));
assert(H.includes('Positive monthly increase · account count'));assert(H.includes('Opening source accounts'));assert(H.includes('Monthly increase = max(0, month-end source count − prior month-end)'));
console.log('PASS compact explicit activity selection, opening input required, no inferred opening and clean opt-out');
