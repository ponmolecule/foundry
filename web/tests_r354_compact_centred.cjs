// r354: compact sections, vertical centring and one-row figures. Checks the shipped rule and styles,
// and that the one-row rule classifies sections by the columns their inputs occupy.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const s of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(s[1]);
const css=[...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
// the rule as shipped
const m=html.match(/const span=fl\.reduce\(([\s\S]*?)\);\s*\n\s*if\(ro&&fl\.length&&span<=4&&!lg\.length\)b\.classList\.add\('compact'\);/);
assert(m,'one-row compact rule present');
const spanOf=new vm.Script('(fl)=>fl.reduce('+m[1]+')').runInNewContext({});
const f=(...c)=>({classList:{contains:k=>c.includes(k)}});
assert.equal(spanOf([f('s2'),f(),f()]),4,'deposit pricing: toggle + two inputs fill one row');
assert.equal(spanOf([f()]),1,'timing: one input');
assert.equal(spanOf([f('s4'),f(),f(),f(),f()]),8,'balance: method selector + four inputs need two rows');
assert.equal(spanOf([f('s2'),f('s2'),f()]),5,'two toggles + an input spill to a second row');
// centring and figures
assert(/\.lfx-b\.has-ro>\.lfx-rail,\.lfx-b\.has-ro>\.lfx-body\{display:flex;flex-direction:column;justify-content:center\}/.test(css),'rail and inputs centre');
assert(/\.lfx-b\.has-ro>\.lfx-ro\{display:flex;flex-direction:column;justify-content:center\}/.test(css),'chart column centres');
assert(!/\.tall>/.test(css),'no top-align exception');
assert(/@container \(min-width:1320px\)\{[\s\S]*?\.lfx-ro \.ro-k\{grid-template-columns:repeat\(4,minmax\(0,1fr\)\)\}/.test(css),'figures in one row of four');
assert(css.includes('grid-template-columns:288px minmax(520px,900px) minmax(440px,1fr)'),'chart column keeps at least 440px');
assert(/\.lfx-b\.compact \.lfx-ro \.ro-pl,\.lfx-b\.compact \.lfx-ro \.ro-pl svg\{height:64px\}/.test(css),'compact chart strip is 64px');
console.log('PASS r354 compact sections, vertical centring, one-row figures');
