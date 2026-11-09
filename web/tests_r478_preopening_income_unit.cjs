const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('web/console_v2.html','utf8');
const s={window:{},cfg:{},esc:String,fmtComma:String,renderContent:()=>{},refresh:()=>{}};vm.createContext(s);
vm.runInContext(h.slice(h.indexOf('function _preopeningIncomeHtml()'),h.indexOf('window.poAdd',h.indexOf('function _preopeningIncomeHtml()'))),s);
s.window.poIncomeAdd();assert.deepEqual(JSON.parse(JSON.stringify(s.cfg.pre_opening.incomes)),[{category:'',total:0}]);
s.cfg.pre_opening.incomes[0]={category:'Earned interest',total:10470365.1};let html=s._preopeningIncomeHtml();assert(Math.abs(+html.match(/aria-label="Pre-opening income total" value="([^"]+)/)[1]-10470.3651)<1e-8);assert(html.includes('_pf(this.value)*1000'));assert(html.includes('excluded from forecast income'));s.window.poIncomeRemove(0);assert.equal(s.cfg.pre_opening.incomes.length,0);
for(const m of h.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))if(m[1].trim())new vm.Script(m[1]);console.log('PASS r478 income add/remove, dollar scaling, authoring markup and complete inline syntax');
