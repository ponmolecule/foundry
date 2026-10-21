const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const m of H.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
let copied=[],mounted;const status={textContent:''},box={hidden:true,focus(){this.focused=true},select(){this.selected=true}};
const ctx={PPY:()=>12,esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),navigator:{clipboard:{async writeText(s){copied.push(s)}}},document:{getElementById:()=>null,createElement:()=>({setAttribute(){},addEventListener(){},showModal(){this.open=true},querySelector:s=>s==='textarea'?box:status}),body:{appendChild:d=>mounted=d}}};vm.createContext(ctx);vm.runInContext(H.slice(H.indexOf('// Numeric inspection stays'),H.indexOf('function _lfxRoHtml(')),ctx);
(async()=>{
 const p={co:[1,2],alll:[3,4],interest:[5,6],rateQ:[11,10.7],detailExact:{co:[1.12345678912345,2],alll:[3,4],interest:[5.123456789,6]}};
 const original=JSON.stringify(p),rows=ctx._resultPanelSeries(p,'credit','','lending');assert.equal(rows[0].name,'Charge-offs');assert.equal(rows[1].name,'Allowance (ALLL)');assert.equal(rows[0].values[0],1.12345678912345);assert.equal(JSON.stringify(p),original);
 const link=ctx._resultNumbersLink(rows,false);assert(link.includes('>Numbers</button>'));assert(!link.includes('<table'));assert(!link.includes('<textarea'));assert(!link.includes('Copy table'));
 ctx.resultNumbersOpen({getAttribute:()=>JSON.stringify({rows,quarter:false,stale:false})});assert(mounted.open);assert(mounted.innerHTML.includes('M1'));assert(mounted.innerHTML.includes('1.12345678912345'));assert(mounted.innerHTML.includes('Copy values'));
 const button={closest:()=>mounted};await ctx.resultNumbersCopy(button,0);assert.equal(copied.at(-1),'1.12345678912345\t2');await ctx.resultNumbersCopy(button,null);assert(copied.at(-1).startsWith('Series\tUnits\tM1\tM2\nCharge-offs\t$000s\t1.12345678912345\t2'));
 ctx.navigator.clipboard=null;await ctx.resultNumbersCopy(button,1);assert.equal(box.value,'3\t4');assert(!box.hidden&&box.selected);assert(status.textContent.includes('Ctrl+C'));
 const q=ctx._resultNumbersTsv([{name:'Zero',unit:'count',values:[0,null,3]}],true);assert(q.includes('Q1\tQ2\tQ3'));assert(q.endsWith('0\t\t3'));
 assert.equal(ctx._resultPanelSeries(p,'pricing','','lending').find(x=>x.name==='Yield').unit,'%');assert.equal(ctx._resultPanelSeries({fees:[8]},'balance','Fee income','obs')[0].values[0],8);
 const z=ctx._resultNumbersLink([{name:'Zero',unit:'$000s',values:[0,0]}],true);assert(z.includes('Numbers'));assert(z.includes('stale'));
 console.log('PASS discreet closed state, separate credit series, exact precision, monthly/quarterly TSV, zero/missing observations, clipboard success/fallback, and no result mutations');
})().catch(e=>{console.error(e);process.exitCode=1});
