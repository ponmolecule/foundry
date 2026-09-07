"""FIW round-trip regression gate for growth/workforce assumptions."""
from __future__ import annotations
import copy, io, json, sys
from pathlib import Path
import openpyxl
from .fiw import build_fiw, diff_import


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond:
            p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    cfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    cfg["assumptions"]["periods_per_year"]=12
    cfg["assumptions"]["nie_detail"]={
        "categories":[{"name":"Occupancy","per_period":30000,"trajectory":"growth",
                       "growth_spec":{"rate":.03,"period":"year","method":"step","anchor":"model_year"}}],
        "other_gross_up_rate":0,
        "workforce":{"mode":"roles","default_payroll_load_rate":.25,
                     "default_salary_growth_spec":{"rate":.04,"period":"year","method":"step","anchor":"hire_anniversary"},
                     "roles":[{"role":"Analyst","count":2,"annual_comp":95000,"hire_period":17,
                               "count_spec":{"source":"entered","trajectory":"explicit","cadence":"year",
                                             "resolution":"step","values":[2,3,4]},
                               "salary_growth_spec":{"rate":.05}},
                              {"role":"Custody Ops","count":1,"annual_comp":120000,
                               "activation":{"type":"metric","metric":"managed_notional_end","source":"Custody",
                                             "operator":">=","reference":"fixed","value":500000000,
                                             "timing":"same_period"}}]}}
    data,_=build_fiw(cfg)
    wb=openpyxl.load_workbook(io.BytesIO(data)); ws=wb["ASSM_NIE"]
    keys={str(r[0].value):r for r in ws.iter_rows(min_row=2)}
    need={"nie_detail.workforce.roles.0.hire_period","nie_detail.workforce.roles.0.annual_comp",
          "nie_detail.workforce.roles.1.activation.metric","nie_detail.workforce.roles.1.activation.source",
          "nie_detail.workforce.roles.1.activation.value","nie_detail.workforce.roles.1.activation.timing",
          "nie_detail.workforce.default_salary_growth_spec.anchor","nie_detail.categories.0.growth_spec.rate",
          "nie_detail.workforce.roles.0.count_spec.trajectory","nie_detail.workforce.roles.0.count_spec.values.1"}
    ck("ASSM_NIE exposes workforce + growth leaves", need.issubset(keys), str(sorted(need-set(keys))))
    keys["nie_detail.workforce.roles.0.hire_period"][3].value=19
    keys["nie_detail.categories.0.growth_spec.rate"][3].value=.05
    keys["nie_detail.workforce.roles.1.activation.value"][3].value=750000000
    keys["nie_detail.workforce.roles.0.count_spec.values.1"][3].value=5
    buf=io.BytesIO(); wb.save(buf)
    merged,rep=diff_import(buf.getvalue(), copy.deepcopy(cfg))
    nd=merged["assumptions"]["nie_detail"]
    ck("FIW workforce hire-period edit lands", nd["workforce"]["roles"][0]["hire_period"]==19)
    ck("FIW category growth-rate edit lands", abs(nd["categories"][0]["growth_spec"]["rate"]-.05)<1e-12)
    ck("FIW workforce Count schedule edit lands", nd["workforce"]["roles"][0]["count_spec"]["values"][1]==5)
    act=nd["workforce"]["roles"][1]["activation"]
    ck("FIW metric-trigger fields round-trip as structured workforce activation",
       act.get("metric")=="managed_notional_end" and act.get("source")=="Custody"
       and abs(act.get("value",0)-750000000)<1 and act.get("timing")=="same_period")
    ck("FIW reports only the four intended edits", rep.get("edit_count")==4, str(rep.get("edit_count")))
    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
