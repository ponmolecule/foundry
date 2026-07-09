// P0 fixture generator — freezes predecessor engine outputs as golden expectations.
// Predecessor A: quarterly balance-driven HTML engine ("pf_a")
// Predecessor B: quarterly balance-driven JSX engine  ("pf_b")
const fs = require('fs'), crypto = require('crypto');
const { loadApp } = require('/home/claude/harness');

function sha(o){ return crypto.createHash('sha256').update(JSON.stringify(o)).digest('hex').slice(0,12); }
function r2(x){ return (x===null||x===undefined||!isFinite(x)) ? null : Math.round(x*100)/100; }
function arr(a, from){ return a.slice(from).map(r2); }

// ---------- Predecessor A (HTML engine) ----------
const A = loadApp('/mnt/user-data/uploads/klaros-pro-forma-modeler.html');
function snapA(m){
  return {
    bs: { cash: arr(m.bs.cash,0), sec: arr(m.bs.sec,0), netLoans: arr(m.bs.netLoans,0),
          grossLoans: arr(m.grossLoans,0), alll: arr(m.alllTot,0), hfs: arr(m.hfsTot,0),
          msr: arr(m.msrTot,0), borrow: arr(m.bs.borrow,0), deposits: arr(m.totalDeps,0),
          equity: arr(m.bs.equity,0), re: arr(m.bs.re,0), totalAssets: arr(m.bs.totalAssets,0) },
    is: { loanInt: arr(m.is_.loanInt,1), secInt: arr(m.is_.secInt,1), cashInt: arr(m.is_.cashInt,1),
          depExp: arr(m.is_.depExp,1), borrExp: arr(m.is_.borrExp,1), nii: arr(m.is_.nii,1),
          prov: arr(m.is_.prov,1), fees: arr(m.is_.fees,1), gos: arr(m.is_.gos,1),
          servNet: arr(m.is_.servNet,1), fvPnl: arr(m.is_.fvPnl,1), prodOpex: arr(m.is_.prodOpex,1),
          overhead: arr(m.is_.overhead,1), pretax: arr(m.is_.pretax,1), tax: arr(m.is_.tax,1),
          ni: arr(m.is_.ni,1), nco: arr(m.is_.nco,1), nol: arr(m.is_.nolEnd,1) },
    ratios: { roa: arr(m.ratios.roa,1), roe: arr(m.ratios.roe,1), nim: arr(m.ratios.nim,1),
              lev: arr(m.ratios.lev,1), alllPct: arr(m.ratios.alllPct,1) },
    advisories: { count: m.warnings.length, severe: m.warnings.filter(w=>w.sev==='severe').length }
  };
}
const aDefaults = () => JSON.parse(JSON.stringify(A.products));
const aG = () => JSON.parse(JSON.stringify(A.globals));

const fixturesA = {};
// A1 base
fixturesA['pf_a_base'] = { inputs: { products: aDefaults(), globals: aG(), stress: null },
  expected: snapA(A.computeModel(aDefaults(), aG())) };
// A2 combined stress + overlays
const stress = { coMult:2.5, resMult:1.5, shockBp:300, volHaircut:40, gosComp:40, msrShock:20, saleShift:25 };
fixturesA['pf_a_combined_stress'] = { inputs: { products: aDefaults(), globals: aG(), stress },
  expected: snapA(A.computeModel(aDefaults(), aG(), stress)) };
// A3 warning-heavy (bands + hot money + usury-adjacent)
const pw = aDefaults();
pw.find(p=>p.name==='Credit Cards').chargeOff = 12; pw.find(p=>p.name==='Credit Cards').yld = 27;
const sv = pw.find(p=>p.name==='Savings'); sv.rateType='fixed'; sv.ratePaid = 6.0;
fixturesA['pf_a_warning_heavy'] = { inputs: { products: pw, globals: aG(), stress: null },
  expected: snapA(A.computeModel(JSON.parse(JSON.stringify(pw)), aG())) };
// A4 originate-to-sell / MSR emphasis (bigger sold share, longer warehouse)
const po = aDefaults();
const mg = po.find(p=>p.name==='Mortgages'); mg.salePct=80; mg.holdQtrs=2; mg.orig=9000; mg.servRetained=100;
fixturesA['pf_a_ots_msr'] = { inputs: { products: po, globals: aG(), stress: null },
  expected: snapA(A.computeModel(JSON.parse(JSON.stringify(po)), aG())) };
// A5 fair-value election
const pf = aDefaults();
const pl = pf.find(p=>p.name==='Personal Loans'); pl.measurement='fairvalue'; pl.discountSpread=13;
fixturesA['pf_a_fv_election'] = { inputs: { products: pf, globals: aG(), stress: null },
  expected: snapA(A.computeModel(JSON.parse(JSON.stringify(pf)), aG())) };

// ---------- Predecessor B (JSX engine) ----------
const src = fs.readFileSync('/mnt/user-data/outputs/bank-proforma-modeler.jsx','utf8');
const core = src.slice(src.indexOf('const QUARTERS'), src.indexOf('/* ---------------- UI ATOMS'))
  + '\nreturn {PRESETS, INITIAL, DEFAULT_GLOBALS, runModel, nid};';
const B = new Function(core)();
const bDefaults = () => B.INITIAL.map(p => Object.assign({overrides:{}}, JSON.parse(JSON.stringify(p)), {id: B.nid()}));
function snapB(m){
  const qs = m.quarters;
  const g = k => qs.map(q => r2(q[k]));
  return {
    bs: { cash: g('cash'), afs: g('afs'), htm: g('htm'), grossLoans: g('grossLoans'),
          alll: g('alll'), netLoans: g('netLoans'), deposits: g('deposits'),
          borrowings: g('borrowings'), equity: g('equity'), retained: g('retained'),
          totalAssets: g('totalAssets') },
    is: { intLoans: g('intLoans'), intSec: g('intSec'), intCash: g('intCash'),
          intDep: g('intDep'), intBorrow: g('intBorrow'), nii: g('nii'),
          provision: g('provision'), fees: g('fees'), opexProd: g('opexProd'),
          fixedOpex: g('fixedOpex'), pretax: g('pretax'), tax: g('tax'),
          ni: g('ni'), chargeoffs: g('chargeoffs') },
    ratios: { roa: qs.map(q=>r2(q.roa*100)), roe: qs.map(q=>r2(q.roe*100)),
              nim: qs.map(q=>r2(q.nim*100)), leverage: qs.map(q=>r2(q.leverage*100)) }
  };
}
const fixturesB = {};
fixturesB['pf_b_base'] = { inputs: { products: bDefaults(), globals: {...B.DEFAULT_GLOBALS} },
  expected: snapB(B.runModel(bDefaults(), B.DEFAULT_GLOBALS)) };
// B2 per-quarter overrides (rate + chargeoff)
const pb2 = bDefaults();
pb2.find(p=>p.name==='Commercial Loans').overrides = { rate: {4:'9.0',5:'9.0',6:'9.0',7:'9.0'} };
pb2.find(p=>p.name==='Personal Loans').overrides = { chargeoff: {2:'8'} };
fixturesB['pf_b_overrides'] = { inputs: { products: pb2, globals: {...B.DEFAULT_GLOBALS} },
  expected: snapB(B.runModel(JSON.parse(JSON.stringify(pb2)), B.DEFAULT_GLOBALS)) };
// B3 HTM via securities products (AFS + HTM presets added)
const pb3 = B.PRESETS.map(p => Object.assign({overrides:{}}, JSON.parse(JSON.stringify(p)), {id: B.nid()}));
fixturesB['pf_b_htm_securities'] = { inputs: { products: pb3, globals: {...B.DEFAULT_GLOBALS} },
  expected: snapB(B.runModel(JSON.parse(JSON.stringify(pb3)), B.DEFAULT_GLOBALS)) };
// B4 reserve build: provisioning above charge-offs
const pb4 = bDefaults();
const cre = pb4.find(p=>p.name==='Commercial Loans'); cre.chargeoff = 1.0; cre.loss = 2.5;
fixturesB['pf_b_reserve_build'] = { inputs: { products: pb4, globals: {...B.DEFAULT_GLOBALS} },
  expected: snapB(B.runModel(JSON.parse(JSON.stringify(pb4)), B.DEFAULT_GLOBALS)) };

// ---------- write, hash-stamped ----------
const out = { generated: '2026-07-08', tolerance_per_line_per_quarter_usd_000: 1.0,
  profiles: { pf_a: 'quarterly balance-driven predecessor A', pf_b: 'quarterly balance-driven predecessor B' },
  fixtures: {} };
for (const [k,v] of Object.entries({...fixturesA, ...fixturesB})) {
  out.fixtures[k] = { ...v, fixture_hash: sha(v) };
}
fs.writeFileSync('/home/claude/p0/parity_fixtures.json', JSON.stringify(out, null, 1));
console.log('fixtures frozen:', Object.keys(out.fixtures).length);
for (const [k,v] of Object.entries(out.fixtures)) console.log(' ', k, v.fixture_hash,
  '| Q12 NI', (v.expected.is.ni ?? v.expected.is.ni)[11]);
// determinism: regenerate A base and compare
const again = snapA(A.computeModel(aDefaults(), aG()));
console.log('determinism check (pf_a_base):', sha({inputs:{products:aDefaults(),globals:aG(),stress:null},expected:again})===out.fixtures['pf_a_base'].fixture_hash ? 'REPRODUCIBLE' : 'NON-DETERMINISTIC');
