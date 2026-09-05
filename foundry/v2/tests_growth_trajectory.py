"""Focused regression gate for canonical growth/workforce trajectories."""
from __future__ import annotations

import math
import sys

from .growth import resolve_growth_series, growth_multiplier
from .workforce import workforce_comp_series


def main():
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond:
            p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    annual_step = {"rate": .03, "period": "year", "method": "step", "anchor": "model_year"}
    s = resolve_growth_series(30000, annual_step, 24, 12)
    ck("annual step is flat M1-M12 then +3% at M13",
       all(abs(x-30000)<1e-9 for x in s[:12]) and all(abs(x-30900)<1e-9 for x in s[12:]), str(s[:14]))

    annual_smooth = {"rate": .03, "period": "year", "method": "smooth"}
    sm = resolve_growth_series(30000, annual_smooth, 13, 12)
    ck("annual smooth reaches +3% at M13", abs(sm[12]-30900)<1e-8,
       f"M2={sm[1]:.4f} M13={sm[12]:.4f}")
    ck("annual smooth native monthly rate is equivalent CAGR",
       abs(sm[1]/sm[0] - (1.03**(1/12))) < 1e-12)

    annual_internal = resolve_growth_series(100, annual_step, 3, 1)
    ck("annual-only internal cadence supports CAC model-year growth",
       all(abs(x-y)<1e-12 for x,y in zip(annual_internal,[100.0,103.0,106.09])), str(annual_internal))

    qstep = {"rate": .05, "period": "quarter", "method": "step", "anchor": "model_period"}
    qs = resolve_growth_series(100, qstep, 7, 12)
    ck("quarter step in monthly model steps at M4/M7", qs == [100,100,100,105,105,105,110.25], str(qs))

    bad = False
    try:
        resolve_growth_series(100, {"rate": .01, "period":"month", "method":"step"}, 4, 4)
    except ValueError:
        bad = True
    ck("unrepresentable monthly step in quarterly model fails closed", bad)

    bad_fiscal = False
    try:
        resolve_growth_series(100, {"rate": .03, "period":"year", "method":"step",
                                    "anchor":"fiscal_year", "anchor_month":2},
                              8, 4, context={"start_year":2027,"start_month":1})
    except ValueError:
        bad_fiscal = True
    ck("quarterly fiscal step on a non-quarter month fails closed", bad_fiscal)

    cctx = {"start_year": 2027, "start_month": 5}
    cal = {"rate": .10, "period":"year", "method":"step", "anchor":"calendar_year"}
    cs = resolve_growth_series(100, cal, 12, 12, context=cctx)
    ck("calendar-year step from May opening lands in January",
       all(abs(x-100)<1e-9 for x in cs[:8]) and all(abs(x-110)<1e-9 for x in cs[8:]), str(cs))
    fis = {"rate": .10, "period":"year", "method":"step", "anchor":"fiscal_year", "anchor_month":7}
    fs = resolve_growth_series(100, fis, 6, 12, context=cctx)
    ck("fiscal-year July step from May opening lands in July", all(abs(x-y)<1e-9 for x,y in zip(fs,[100,100,110,110,110,110])), str(fs))

    hire = {"rate": .04, "period":"year", "method":"step", "anchor":"hire_anniversary"}
    hs = resolve_growth_series(95000, hire, 31, 12, start_period=17)
    ck("hire-anniversary salary starts M17 and steps M29",
       all(x==0 for x in hs[:16]) and all(abs(x-95000)<1e-9 for x in hs[16:28])
       and all(abs(x-98800)<1e-9 for x in hs[28:]), str(hs[15:30]))

    modelyr = {"rate": .04, "period":"year", "method":"step", "anchor":"model_year"}
    ms = resolve_growth_series(95000, modelyr, 26, 12, start_period=17)
    ck("late hire with model-year anchor first steps at next model year",
       all(abs(x-95000)<1e-9 for x in ms[16:24]) and abs(ms[24]-98800)<1e-9)

    opening_smooth = {"rate": .12, "period":"quarter", "method":"smooth"}
    om = [1000*growth_multiplier(opening_smooth, current_period=q, start_period=1,
                                 ppy=12, base_position="opening") for q in range(1,4)]
    ck("opening-stock smooth growth preserves +12% over first quarter", abs(om[-1]-1120)<1e-9, str(om))

    wf = {"default_payroll_load_rate": .25,
          "default_salary_growth_spec": hire,
          "roles":[
              {"role":"CEO","count":1,"annual_comp":240000,"hire_period":1,"salary_growth_spec":{"rate":0,"period":"year","method":"step","anchor":"hire_anniversary"}},
              {"role":"Analyst cohort","count":2,"annual_comp":95000,"hire_period":17,"salary_growth_spec":hire,"payroll_load_rate":.28},
              {"role":"Late role","count":1,"annual_comp":120000,"hire_period":57,"salary_growth_spec":hire},
          ]}
    wp = workforce_comp_series(wf, 60, 12)
    ck("workforce monthly CEO expense includes default payroll load", abs(wp[0]-25000)<1e-9, f"M1={wp[0]}")
    analyst_m17 = 2*95000*1.28/12
    ck("cohort hire begins exactly at M17", abs(wp[15]-25000)<1e-9 and abs(wp[16]-(25000+analyst_m17))<1e-9)
    analyst_m29 = 2*95000*1.04*1.28/12
    ck("cohort salary escalation is independent of CEO trajectory", abs(wp[28]-(25000+analyst_m29))<1e-9)
    ck("M57 hire is naturally supported", wp[55] < wp[56] and abs((wp[56]-wp[55])-12500)<1e-9,
       f"M56={wp[55]:.2f} M57={wp[56]:.2f}")

    # 48 heterogeneous roles: compact rows, late hires, heterogeneous escalations.
    roles=[]
    for i in range(48):
        roles.append({"role":f"Role {i+1}", "count":1, "annual_comp":60000+i*1000,
                      "hire_period":1+(i*7)%57,
                      "salary_growth_spec":{"rate":.02+(i%4)*.01, "period":"year",
                                            "method":"step", "anchor":"hire_anniversary"}})
    big = workforce_comp_series({"roles":roles,"default_payroll_load_rate":.20}, 60, 12)
    ck("48-role heterogeneous workforce resolves to one compact native series",
       len(big)==60 and all(math.isfinite(x) and x>=0 for x in big) and big[-1]>0,
       f"M1={big[0]:.2f} M60={big[-1]:.2f}")

    from .income_modules import managed_notional_series, fee_stream_q
    _avg,_end = managed_notional_series({"day1":30000,"trajectory":"proportional","growth_spec":annual_step}, 13, 12)
    ck("managed-notional proportional growth shares annual-step semantics",
       _end[:12] == [30000.0]*12 and abs(_end[12]-30900.0)<1e-9)
    _stream={"name":"Accounts","basis":"account",
             "driver":{"source":"constant","trajectory":"proportional","params":{"base":1000,"growth_spec":annual_step}},
             "rate":{"behavior":"flat","params":{"fee_per_period":1.0}},
             "timing":{"start_period":1},"cost":{"kind":"none","params":{}}}
    _f1,_=fee_stream_q(_stream,1,{"growth_context":None},12)
    _f12,_=fee_stream_q(_stream,12,{"growth_context":None},12)
    _f13,_=fee_stream_q(_stream,13,{"growth_context":None},12)
    ck("fee-stream proportional driver shares annual-step semantics",
       abs(_f1-1000)<1e-9 and abs(_f12-1000)<1e-9 and abs(_f13-1030)<1e-9,
       f"M1={_f1:.2f} M12={_f12:.2f} M13={_f13:.2f}")

    import json
    from pathlib import Path
    from .run_q import run_v2
    _cfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    _a=_cfg["assumptions"]; _a["periods_per_year"]=12; _a["n_periods"]=24
    _a["nie_detail"]=None; _a.pop("overhead_q",None); _a["overhead_per_period"]=30000
    _a["overhead_growth_spec"]=annual_step
    _rr=run_v2(_cfg); _oh=_rr["financials"]["is"]["overhead"]
    ck("simple corporate overhead consumes the canonical growth resolver",
       _oh[:12]==[30.0]*12 and _oh[12:24]==[30.9]*12)

    from .validate_q import validate_config_v2, ConfigErrorV2
    _bad_cfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    _bad_cfg["assumptions"]["periods_per_year"]=4
    _bad_cfg["assumptions"]["n_periods"]=12
    _bad_cfg["assumptions"]["nie_detail"]={
        "categories":[],
        "workforce":{
            "mode":"roles",
            "default_salary_growth_spec":{
                "rate":.01,"period":"month","method":"step","anchor":"model_period"},
            "roles":[{"role":"Analyst","count":1,"annual_comp":90000,"hire_period":1}]
        }
    }
    _rejected=False
    try:
        validate_config_v2(_bad_cfg)
    except ConfigErrorV2:
        _rejected=True
    ck("config validation rejects workforce step cadence the engine cannot represent", _rejected)

    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
