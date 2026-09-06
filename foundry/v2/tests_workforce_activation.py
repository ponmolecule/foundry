"""Focused regression gate for workforce activation and observable managed-notional paths."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from .activation import validate_activation_rule
from .workforce import WorkforceRuntime, workforce_comp_series


def main():
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond:
            p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    # Engagement testcase: count N periods below the EOP-AUC breakpoint, hire in N+1.
    auc = [100.0, 200.0, 299.0, 300.0, 450.0]
    wf_auc = {"roles":[{"role":"Custody ops","count":1,"annual_comp":120000,
                         "activation":{"type":"metric","metric":"managed_notional_end",
                                       "source":"Custody","operator":">=","reference":"fixed",
                                       "value":300.0,"timing":"same_period"}}]}
    comp = workforce_comp_series(wf_auc, len(auc), 12,
                                 metric_series={("managed_notional_end","Custody"):auc})
    ck("EOP AUC breakpoint hires in N+1 where N periods are below threshold",
       comp[:3] == [0.0,0.0,0.0] and abs(comp[3]-10000.0)<1e-9,
       f"comp={comp}")

    # Fixed-period activation remains the compact path for 'hire by M36 irrespective'.
    wf_m36={"roles":[{"role":"Controller","count":1,"annual_comp":144000,"hire_period":36}]}
    m36=workforce_comp_series(wf_m36, 40, 12)
    ck("fixed M36 hire remains simple and activates exactly at M36",
       all(x==0 for x in m36[:35]) and abs(m36[35]-12000.0)<1e-9)

    # Endogenous metrics use completed history, then activate in the following period.
    eff=[.62,.49,.47,.46]
    wf_eff={"roles":[{"role":"Ops analyst","count":1,"annual_comp":96000,
                      "activation":{"type":"metric","metric":"efficiency_ratio",
                                    "operator":"<","reference":"fixed","value":.50,
                                    "timing":"next_period"}}]}
    e=workforce_comp_series(wf_eff,4,12,metric_series={("efficiency_ratio",None):eff})
    ck("efficiency-ratio trigger uses completed history and activates next period",
       e[:2]==[0.0,0.0] and abs(e[2]-8000.0)<1e-9, f"comp={e}")

    # Prior-year reference is same native period one model year earlier. The observation
    # itself is completed history, so a qualifying M13 observation hires at M14.
    ni=[100.0]+[120.0]*11+[210.0]+[220.0]*3
    wf_ni={"roles":[{"role":"Finance manager","count":1,"annual_comp":120000,
                     "activation":{"type":"metric","metric":"net_income",
                                   "operator":">=","reference":"prior_year","multiplier":2.0,
                                   "timing":"next_period"}}]}
    n=workforce_comp_series(wf_ni,len(ni),12,metric_series={("net_income",None):ni})
    ck("prior-year NI multiple can trigger a contingent role without circular solving",
       all(x==0 for x in n[:13]) and abs(n[13]-10000.0)<1e-9, f"M13={n[12]} M14={n[13]}")

    bad=False
    try:
        validate_activation_rule({"metric":"efficiency_ratio","operator":"<","reference":"fixed",
                                  "value":.5,"timing":"same_period"})
    except ValueError:
        bad=True
    ck("same-period activation on workforce-dependent metrics fails closed", bad)

    dup=False
    try:
        validate_activation_rule({"metric":"managed_notional_end","source":"Custody","operator":">=",
                                  "reference":"fixed","value":1,"timing":"same_period"},
                                 available_sources=["Custody","Custody"])
    except ValueError:
        dup=True
    ck("ambiguous duplicate managed-notional source names fail closed", dup)

    # End-to-end engine/API case on the actual named managed-notional product.
    from .run_q import run_v2
    cfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    a=cfg["assumptions"]
    a["periods_per_year"]=12; a["n_periods"]=12
    a["obs_exposures"]=[{
        "name":"Custody","call_report_line":"obs","_fee_product":True,
        "managed_notional":{"day1":0.0,"target":600_000_000.0,"ramp_periods":6,"trajectory":"ramp_to_target"},
        "fee_streams":[{"basis":"balance","driver":{"source":"managed_notional"},
                        "rate":{"params":{"rate":.001}},"timing":{"start_period":1}}]
    }]
    a["nie_detail"]={"categories":[],"other_gross_up_rate":0,
        "workforce":{"mode":"roles","default_payroll_load_rate":0,
                     "default_salary_growth_spec":{"rate":0,"period":"year","method":"step","anchor":"hire_anniversary"},
                     "roles":[{"role":"Custody ops","count":1,"annual_comp":120000,
                               "activation":{"type":"metric","metric":"managed_notional_end","source":"Custody",
                                             "operator":">=","reference":"fixed","value":300_000_000.0,
                                             "timing":"same_period"}}]}}
    rr=run_v2(cfg)
    prod=next(x for x in rr["products"] if x.get("name")=="Custody")
    end=prod.get("managedNotionalEnd") or []
    ck("EOP managed notional is a first-class native-cadence named product output",
       len(end)==12 and abs(end[0]-100_000.0)<1 and abs(end[2]-300_000.0)<1
       and prod.get("managedNotionalUnits")=="$000s", str(end[:4]))
    hires=(rr.get("workforce") or {}).get("resolved_hire_periods") or []
    ck("end-to-end EOP-AUC trigger resolves the engagement hire to M3",
       hires==[3], str(hires))
    # Compare with the same configuration absent the role; only M3+ should pick up payroll.
    cfg0=copy.deepcopy(cfg); cfg0["assumptions"]["nie_detail"]["workforce"]["roles"]=[]
    rr0=run_v2(cfg0)
    overhead=rr["financials"]["is"]["overhead"]; overhead0=rr0["financials"]["is"]["overhead"]
    delta=[round(overhead[i]-overhead0[i],6) for i in range(4)]
    ck("triggered workforce expense begins in the resolved same period",
       abs(delta[0])<1e-9 and abs(delta[1])<1e-9 and delta[2]>0 and delta[3]>0, str(delta))
    ndcomp=(rr.get("nie_detail_series") or {}).get("comp") or []
    ck("public NIE detail compensation reflects resolved contingent workforce, not a zero placeholder",
       len(ndcomp)>=4 and ndcomp[:2]==[0.0,0.0] and abs(ndcomp[2]-10.0)<1e-9, str(ndcomp[:4]))

    # CAC retains its legacy key but also exposes a cadence-neutral EOP alias.
    from .cac_feeder import cac_auc_rollforward
    feed={"attrition_rate":0,"beginning_auc":0,"beginning_customers":0,"intra_year_shape":"stepped",
          "channels":[{"method":"spend_cac","params":{"spend":1200,"cac":100},"avg_auc_per_customer":1000}]}
    cr=cac_auc_rollforward(feed,12,12)
    ck("CAC exposes cadence-neutral auc_end_by_period while retaining legacy auc_levels_q alias",
       cr.get("auc_end_by_period")==cr.get("auc_levels_q") and len(cr.get("auc_end_by_period") or [])==12)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1


if __name__ == "__main__":
    sys.exit(main())
