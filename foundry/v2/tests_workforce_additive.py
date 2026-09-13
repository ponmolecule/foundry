"""Focused r87 gate for additive/tiered Workforce compensation components."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2
from .validate_q import validate_config_v2
from .workforce import (normalize_workforce_additive_component,
                        workforce_additive_component_amount)


def _component(first_period: int):
    return {
        "driver": "piecewise_linked",
        "component_id": "wf-component-performance",
        "name": "Executive performance pool",
        "terms": [{"source": "income_statement_flow", "metric": "total_operating_revenue",
                   "aggregation": "model_year_to_date", "weight": 1.0}],
        "bands": [
            {"lower_bound": 0.0, "upper_bound": 10_000_000.0,
             "base_amount": 0.0, "marginal_rate": 0.0},
            {"lower_bound": 10_000_000.0, "upper_bound": None,
             "base_amount": 0.0, "marginal_rate": 0.02},
        ],
        "timing": {"mode": "annual", "first_period": first_period},
        "observation_lag": {"value": 0, "period": "model_period"},
    }


def _cfg(ppy=12):
    cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    a = cfg["assumptions"]
    a["periods_per_year"] = ppy
    a["n_periods"] = ppy * 2
    a["nie_detail"] = {
        "categories": [], "other_gross_up_rate": 0.0,
        "workforce": {"mode": "roles", "roles": [], "default_payroll_load_rate": 0.0,
                      "default_salary_growth_spec": {"rate": 0.0, "period": "year",
                                                     "method": "step", "anchor": "hire_anniversary"},
                      "additive_components": [_component(ppy)]},
    }
    return cfg


def main():
    passed = failed = 0

    def ck(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            failed += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    c = normalize_workforce_additive_component(_component(12), 12)
    hist = [1_000_000.0] * 11 + [2_000_000.0]
    amount = workforce_additive_component_amount(c, 11, {
        "periods_per_year": 12,
        "income_statement_flow_history": {"total_operating_revenue": hist},
    })
    ck("band arithmetic reuses literal hurdle grammar: 2% of FY revenue above $10M",
       abs(amount - 60_000.0) < 1e-9, f"amount={amount}")
    ck("annual component is zero before its M12 event",
       workforce_additive_component_amount(c, 10, {
           "periods_per_year": 12,
           "income_statement_flow_history": {"total_operating_revenue": hist[:11]},
       }) == 0.0)

    cfg = _cfg(12)
    validate_config_v2(copy.deepcopy(cfg))
    raw = run_pf_a(copy.deepcopy(cfg))
    is_ = raw["is"]
    for year in (0, 1):
        lo, hi = year * 12, (year + 1) * 12
        fy_rev = sum(float(is_["nii"][i] or 0.0) + float(is_["fees"][i] or 0.0)
                     + float(is_["gos"][i] or 0.0) + float(is_["servNet"][i] or 0.0)
                     for i in range(lo, hi))
        expected = 0.02 * max(0.0, fy_rev - 10_000_000.0)
        actual = float(is_["workforceComp"][hi - 1] or 0.0)
        ck(f"Y{year+1} performance pool reconciles to final modeled FY revenue",
           abs(actual - expected) < 1e-3, f"FY revenue={fy_rev:.6f}, bonus={actual:.6f}, expected={expected:.6f}")
        ck(f"Y{year+1} pool recognizes only in final model month",
           all(abs(float(is_["workforceComp"][i] or 0.0)) < 1e-9 for i in range(lo, hi - 1)))
    ck("additive compensation posts to Workforce compensation rather than Other Opex",
       abs(raw["workforce"]["additive_comp"][11] - raw["is"]["workforceComp"][11]) < 1e-6)

    public = run_v2(copy.deepcopy(cfg))
    w = public.get("workforce") or {}
    ck("public Workforce diagnostics convert additive monetary paths to $000s",
       len(w.get("additive_comp") or []) == 24 and
       abs((w.get("additive_components") or [])[0]["amounts"][11] - w["additive_comp"][11]) < 1e-9)
    from .audit_workbook import calculation_audit_workbook
    wb = calculation_audit_workbook(cfg, public)
    ck("audit workbook adds Workforce Component Detail", "Workforce Component Detail" in wb.sheetnames)
    rows = list(wb["Workforce Component Detail"].iter_rows(values_only=True))
    detail = [r for r in rows if len(r) > 19 and r[0] == "Executive performance pool" and r[4] is True]
    ck("audit detail exposes FY driver, active band, marginal rate, and calculated compensation",
       bool(detail) and any(r[8] == "income_statement_flow" and r[9] == "total_operating_revenue"
                            and abs(float(r[18] or 0.0) - 0.02) < 1e-12 and float(r[19] or 0.0) > 0
                            for r in detail))

    qcfg = _cfg(4)
    # Use a lower hurdle here so both annual event periods carry a positive amount;
    # the monthly test above preserves the source-case $10MM hurdle itself.
    qbands = qcfg["assumptions"]["nie_detail"]["workforce"]["additive_components"][0]["bands"]
    qbands[0]["upper_bound"] = 1_000_000.0
    qbands[1]["lower_bound"] = 1_000_000.0
    qr = run_pf_a(copy.deepcopy(qcfg))
    ck("quarterly presentation preserves annual event at Q4/Q8",
       all(abs(float(qr["is"]["workforceComp"][i] or 0.0)) < 1e-9 for i in (0, 1, 2, 4, 5, 6))
       and qr["is"]["workforceComp"][3] > 0 and qr["is"]["workforceComp"][7] > 0)

    bcfg = json.loads(Path("foundry/fixtures/parity/configs/pf_b_base.json").read_text())
    bcomp = _component(4)
    bcomp["bands"][0]["upper_bound"] = 1_000_000.0
    bcomp["bands"][1]["lower_bound"] = 1_000_000.0
    bcfg["assumptions"]["nie_detail"] = {
        "categories": [], "other_gross_up_rate": 0.0,
        "workforce": {"mode": "roles", "roles": [], "default_payroll_load_rate": 0.0,
                      "default_salary_growth_spec": {"rate": 0.0, "period": "year",
                                                     "method": "step", "anchor": "hire_anniversary"},
                      "additive_components": [bcomp]},
    }
    br = run_pf_b(copy.deepcopy(bcfg))
    b_ok = True
    for year in range(3):
        lo, hi = year * 4, (year + 1) * 4
        rev = sum(float(br["is"]["nii"][i] or 0.0) + float(br["is"]["fees"][i] or 0.0)
                  for i in range(lo, hi))
        expected = 0.02 * max(0.0, rev - 1_000_000.0)
        b_ok = b_ok and all(abs(float(br["is"]["workforceComp"][i] or 0.0)) < 1e-9
                            for i in range(lo, hi - 1))
        b_ok = b_ok and abs(float(br["is"]["workforceComp"][hi - 1] or 0.0) - expected) < 1e-6
    ck("Profile B honors the same annual Workforce hurdle contract", b_ok)

    html = Path("web/console_v2.html").read_text()
    ck("Workforce UI authors additive tiered/banded compensation against explicit FY metrics",
       "+ Tiered / banded compensation component" in html
       and "FY Total operating revenue · NII + fee income + gain on sale + net servicing" in html
       and "Posts directly to <b>Workforce compensation</b>" in html
       and "nieWorkforcePiecewiseAddBand" in html)

    bad = _cfg(12)
    bad["assumptions"]["nie_detail"]["workforce"]["additive_components"][0]["terms"][0]["metric"] = "mystery_revenue"
    rejected = False
    try:
        validate_config_v2(bad)
    except Exception as exc:
        rejected = "unsupported income-statement metric" in str(exc)
    ck("unsupported Workforce performance metric fails closed", rejected)

    print(f"\nWorkforce additive components: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
