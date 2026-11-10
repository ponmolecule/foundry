const fs=require('fs'),vm=require('vm'),assert=require('assert');
const H=fs.readFileSync('web/console_v2.html','utf8');
const path='assumptions.obs_exposures.0.fee_streams.0.driver.params.share_spec',id='fasp_'+path.replace(/[^a-zA-Z0-9]/g,'_');
const ta={value:'0.2777777777777778%\t0.5555555555555556%',dispatchEvent(){ctx._seriesExplicitPasteInput(id)}},btn={disabled:false,classList:{toggle(){}}};
const sp={trajectory:'explicit',cadence:'month',values:[.1]},other={values:[.7]};let renders=0,runs=0;
const ctx={window:null,document:{getElementById:k=>k===id?ta:k===id+'_load'?btn:null},Event:function(){},_faSeriesEnsure:()=>sp,_nativeFlowPeriod:()=> 'month',_resizeSeriesValues(){},_seriesPasteLengthOk:()=>true/* r480: length guard covered by tests_r480; this test checks precision and Clear */,appStatus(){},renderContent(){assert.equal(ta.value,'');renders++},refresh(){runs++}};ctx.window=ctx;ctx._faSeriesExplicitOpen={};vm.createContext(ctx);
vm.runInContext(H.slice(H.indexOf('function _seriesExplicitValues('),H.indexOf('function _feeParseExplicitValues(')),ctx);
vm.runInContext(H.slice(H.indexOf('function _clearPasteDraft('),H.indexOf('function _feeClearCoeffSchedule(')),ctx);
vm.runInContext(H.slice(H.indexOf('window.faSeriesPaste='),H.indexOf('function _faSeriesFmt(')),ctx);
// Parsing stores all supplied digits; display formatting never rewrites them.
const render=ctx.renderContent;ctx.renderContent=()=>{};ctx.faSeriesPaste(path,id,'rate');assert.equal(sp.values[0],Number('0.2777777777777778')/100);assert.equal(sp.values[1],Number('0.5555555555555556')/100);
ctx.renderContent=render;ctx.faSeriesClear(path);assert.equal(sp.values.length,0);assert.equal(ta.value,'');assert(btn.disabled);assert(ctx._faSeriesExplicitOpen[path]);assert.equal(other.values[0],.7);assert.equal(renders,1);
console.log('PASS full-precision rate paste and clear removes loaded schedule plus stale draft before render; editor stays open and Load disabled');
