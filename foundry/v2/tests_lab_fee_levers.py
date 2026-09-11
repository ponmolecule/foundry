"""Focused regressions for Fee Product integration into Bank Design Lab."""
from __future__ import annotations
import copy, json, subprocess, sys
from pathlib import Path


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond:
            p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html=Path("web/console_v2.html").read_text(encoding="utf-8")
    a=html.index("function labLeverCatalog(){")
    b=html.index("const LAB_METRICS_UNITS", a)
    cat_js=html[a:b]
    fa=html.index("function _labStoredToDisplay(")
    fb=html.index("function renderGoalSeekResult", fa)
    fmt_js=html[fa:fb]

    cfg={"assumptions":{"lending_products":[],"deposit_products":[],"obs_exposures":[
        {"name":"Custody","_fee_product":True,
         "managed_notional":{"day1":100_000_000,"target":1_000_000_000,"ramp_periods":24,"trajectory":"ramp_to_target"},
         "fee_streams":[{"name":"Custody fees","basis":"balance",
                         "driver":{"source":"managed_notional","trajectory":"flat","params":{}},
                         "rate":{"behavior":"annual_change","params":{"rate":0.0012,"annual_delta":-0.02}},
                         "timing":{"start_period":1,"end_period":60,"ramp_in_periods":3},
                         "cost":{"kind":"pct_of_revenue","params":{"pct":0.10}}},
                        {"name":"Settlement","basis":"transaction",
                         "driver":{"source":"managed_notional","trajectory":"derived","params":{"coefficient":{"kind":"multiple","value":4.0,"period":"year","trajectory":"flat"}}},
                         "rate":{"behavior":"flat","params":{"per_unit":0.0005}},"timing":{"start_period":1},"cost":{"kind":"none","params":{}}},
                        {"name":"Retainer","basis":"account",
                         "driver":{"source":"constant","trajectory":"flat","params":{"base":10}},
                         "rate":{"behavior":"flat","params":{"unit_fee":{"value":12000,"period":"year"}}},"timing":{"start_period":1},"cost":{"kind":"none","params":{}}},
                        {"name":"Escrow","basis":"flat",
                         "driver":{"source":"constant","trajectory":"flat","params":{}},
                         "rate":{"behavior":"flat","params":{"flat_amount":{"value":120000,"period":"year"}}},"timing":{"start_period":1},"cost":{"kind":"none","params":{}}}]},
        {"name":"Payments","_fee_product":True,
         "managed_notional":{"day1":0,"trajectory":"flat"},
         "fee_streams":[{"name":"Interchange","basis":"transaction",
                         "driver":{"source":"constant","trajectory":"proportional","params":{"base":100000,"growth_spec":{"rate":0.05,"period":"year","method":"smooth"}}},
                         "rate":{"behavior":"durbin_capped","params":{"rate":0.0125,"avg_ticket":50,"per_unit":0.40}},
                         "timing":{"start_period":1},
                         "cost":{"kind":"per_unit","params":{"cost_per_unit":0.10}}}]}
    ]},"target_state":{"initial_capital":100_000_000}}
    prefix="""
const K=1000, window=globalThis;
let cfg=__CFG__;
function PLAB(){return 'Mth';}
function getPath(p){return p.split('.').reduce((o,k)=>o==null?o:o[isNaN(+k)?k:+k],cfg);}
""".replace("__CFG__",json.dumps(cfg))
    suffix="""
const L=labLeverCatalog();
console.log(JSON.stringify({paths:L.map(x=>x.path), labels:L.map(x=>x.label), units:Object.fromEntries(L.map(x=>[x.path,x.unit])), money:_labStoredToDisplay(10000000,'k'), moneyBack:_labInputToStored(10000,'k'), bp:_labStoredToDisplay(.0012,'bps'), bpBack:_labInputToStored(12,'bps')}));
"""
    r=subprocess.run(["node","-e",prefix+cat_js+fmt_js+suffix],text=True,capture_output=True)
    j={}
    if r.returncode==0 and r.stdout.strip():
        try:j=json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:pass
    paths=set(j.get("paths") or [])
    ck("Lab catalog discovers first-class Fee Product AUC and balance-fee levers",
       {"assumptions.obs_exposures.0.managed_notional.day1",
        "assumptions.obs_exposures.0.managed_notional.target",
        "assumptions.obs_exposures.0.fee_streams.0.rate.params.rate",
        "assumptions.obs_exposures.0.fee_streams.0.rate.params.annual_delta",
        "assumptions.obs_exposures.0.fee_streams.0.cost.params.pct"}.issubset(paths), r.stderr.strip())
    ck("Lab catalog discovers natural-period fee coefficient/account/flat levers",
       {"assumptions.obs_exposures.0.fee_streams.1.driver.params.coefficient.value",
        "assumptions.obs_exposures.0.fee_streams.1.rate.params.per_unit",
        "assumptions.obs_exposures.0.fee_streams.2.rate.params.unit_fee.value",
        "assumptions.obs_exposures.0.fee_streams.3.rate.params.flat_amount.value"}.issubset(paths))
    ck("Lab catalog discovers transaction driver/rate/cost levers",
       {"assumptions.obs_exposures.1.fee_streams.0.driver.params.base",
        "assumptions.obs_exposures.1.fee_streams.0.driver.params.growth_spec.rate",
        "assumptions.obs_exposures.1.fee_streams.0.rate.params.rate",
        "assumptions.obs_exposures.1.fee_streams.0.rate.params.avg_ticket",
        "assumptions.obs_exposures.1.fee_streams.0.rate.params.per_unit",
        "assumptions.obs_exposures.1.fee_streams.0.cost.params.cost_per_unit"}.issubset(paths))
    ck("Lab deliberately excludes discrete Fee Product timing/ramp/tier controls from numerical levers",
       not any(x.endswith(("ramp_periods","start_period","end_period","ramp_in_periods")) or ".tiers" in x for x in paths))
    units=j.get("units") or {}
    ck("balance fee rate is expressed in bp and Lab $000s/bp display conversions mirror Product inputs",
       units.get("assumptions.obs_exposures.0.fee_streams.0.rate.params.rate")=="bps"
       and abs(j.get("money",0)-10000)<1e-9 and abs(j.get("moneyBack",0)-10_000_000)<1e-9
       and abs(j.get("bp",0)-12)<1e-9 and abs(j.get("bpBack",0)-.0012)<1e-12
       and units.get("assumptions.obs_exposures.0.fee_streams.1.rate.params.per_unit")=="pct"
       and units.get("assumptions.obs_exposures.0.fee_streams.2.rate.params.unit_fee.value")=="k"
       and units.get("assumptions.obs_exposures.0.fee_streams.3.rate.params.flat_amount.value")=="k")
    ck("Fee-only models are no longer blocked by a lending-product prerequisite",
       "!labLeverCatalog().length" in html and "!((cfg.assumptions||{}).lending_products||[]).length" not in html[html.index("function renderLab()") : html.index("window.renderLab = renderLab")])
    ck("Sensitivity tornado keeps long lever names readable outside a fixed SVG label gutter",
       'class="lab-tornado-row"' in html and 'class="lab-tornado-label"' in html
       and '.lab-tornado-label' in html and 'overflow-wrap:anywhere' in html
       and 'const W=820, rowH=30, padL=250' not in html)

    # Backend proof: the generic dotted-path Lab core already handles Fee Product paths and the
    # real engine responds economically to a changed fee rate.
    from foundry.v2 import lab_core, run_q
    base=json.load(open("foundry/fixtures/universal_template_bank.json"))
    test=copy.deepcopy(base)
    test["assumptions"].setdefault("obs_exposures",[]).append({
        "name":"Lab Custody","_fee_product":True,
        "managed_notional":{"day1":500_000_000.0,"trajectory":"flat"},
        "fee_streams":[{"name":"Custody fee","basis":"balance",
                        "driver":{"source":"managed_notional","trajectory":"flat","params":{}},
                        "rate":{"behavior":"flat","params":{"rate":0.0010}},
                        "timing":{"start_period":1},"cost":{"kind":"none","params":{}}}]})
    path=f"assumptions.obs_exposures.{len(test['assumptions']['obs_exposures'])-1}.fee_streams.0.rate.params.rate"
    low=lab_core.metric_value(run_q.run_v2(lab_core.set_path(test,path,0.0010)),"ni")
    high=lab_core.metric_value(run_q.run_v2(lab_core.set_path(test,path,0.0020)),"ni")
    ck("Lab core can vary a Fee Product dotted path and the real engine responds",
       isinstance(low,(int,float)) and isinstance(high,(int,float)) and high>low, f"low={low}, high={high}")

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
