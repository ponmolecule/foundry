const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');let response,alerts=[],downloads=0,clears=0,revokes=0;
const ctx={console,Uint8Array,AbortController,Blob,alert:x=>alerts.push(x),refresh(){},_engSlug:()=> 'test',setTimeout(fn,ms){if(ms===1000)fn();return 1;},clearTimeout(){clears++;},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){revokes++;}},document:{createElement(){return {click(){downloads++;}};}},fetch:async()=>{if(response instanceof Error)throw response;return response;}};
vm.createContext(ctx);vm.runInContext(html.slice(html.indexOf('async function _auditFailureMessage'),html.indexOf('async function _calculationAuditSnapshot')),ctx);vm.runInContext(html.slice(html.indexOf('async function exportCalculationAudit()'),html.indexOf('window.exportCalculationAudit')),ctx);
ctx._calculationAuditSnapshot=async()=>({config:{},result:{config_hash:'c',run_hash:'r'}});
function res(status,j,mime='application/json',bytes=[80,75,3,4,1]){return {status,ok:status===200,json:async()=>{if(j==='bad')throw Error();return j;},headers:{get:()=>mime},blob:async()=>new Blob([new Uint8Array(bytes)])};}
(async()=>{
 for(const [status,j,word] of [[422,{errors:['Check Source sign']},'Source sign'],[401,{},'session'],[403,{},'permissions'],[409,{},'snapshot'],[429,{},'too many'],[500,'bad','server'],[500,{detail:'Workbook generation failed. Reference abc'},'Reference abc'],[502,'bad','server'],[400,{detail:'Bad request'},'Bad request']]){response=res(status,j);alerts=[];const n=downloads;await ctx.exportCalculationAudit();assert(alerts[0].includes(word),alerts[0]);assert.equal(downloads,n);assert(!alerts[0].includes('complete the open questions'));}
 for(const err of [new Error('network'),Object.assign(new Error(),{name:'AbortError'})]){response=err;alerts=[];await ctx.exportCalculationAudit();assert(alerts[0].includes(err.name==='AbortError'?'timed out':'interrupted'));}
 response=res(200,{},'text/html');alerts=[];await ctx.exportCalculationAudit();assert(alerts[0].includes('not an Excel file'));
 response=res(200,{},'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',[]);alerts=[];await ctx.exportCalculationAudit();assert(alerts[0].includes('empty or incomplete'));
 response=res(200,{},'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');alerts=[];await ctx.exportCalculationAudit();assert.equal(alerts.length,0);assert.equal(downloads,1);assert.equal(revokes,1);assert.equal(clears,14);
 ctx._calculationAuditSnapshot=async()=>({invalid:true,error:'specific validation'});await ctx.exportCalculationAudit();assert.equal(alerts.at(-1),'specific validation');
 console.log('PASS audit validation/session/permissions/mismatch/rate-limit/server/network/timeout/invalid-file paths, no false download, success and cleanup');
})().catch(e=>{console.error(e);process.exit(1);});
