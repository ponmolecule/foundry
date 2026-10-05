"""r300: expense categories are reported with their components (cost pool, formula, tiered); reporting only."""
import copy
import json
import sys
from pathlib import Path

from foundry.v2.run_q import run_v2


def main():
    p = f = 0
    def ck(name, cond, d=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, d)
    base = json.load(open("foundry/fixtures/universal_template_bank.json"))
    flow = lambda v: {"trajectory": "growth", "value": v, "period": "year",
                      "growth_spec": {"rate": 0.03, "period": "year", "method": "step", "anchor": "model_year"}}
    c = copy.deepcopy(base); a = c["assumptions"]
    a["cost_pools"].append({"name": "Test pool", "owner_module": "cost_pool", "series_id": "pool-test-r300",
                            "components": [{"kind": "assumption_cost_base", "name": "Entered base", "series_id": "cost-base-test-r300",
                                            "allocation_pct": 1.0, "flow_spec": flow(450000.0)}]})
    a["nie_detail"]["categories"].append({"name": "T", "flow_spec": flow(0.0), "linked_components": [
        {"driver": "cost_pool_charge", "ref": "pool-test-r300", "recovery_pct": 1.0, "markup": {"trajectory": "flat", "value": 0.05}}]})
    idx = str(len(a["nie_detail"]["categories"]) - 1)
    nd = run_v2(c)["nie_detail_series"]
    ck("new series present", all(k in nd for k in ("components", "components_by_category", "categories_total")))
    ck("categories total = base paths + components, every period",
       all(abs(t - (b + x)) < 0.011 for t, b, x in zip(nd["categories_total"], nd["categories"], nd["components"])))
    ck("per-category component charges sum to the components total",
       all(abs(sum(v[i] for v in nd["components_by_category"].values()) - nd["components"][i]) < 0.05 for i in range(len(nd["components"]))))
    ck("a cost-pool charge is attributed to its own category ($000s: 450/12 x 1.05 = 39.375)",
       abs(nd["components_by_category"].get(idx, [0])[0] - 39.38) < 0.011, str(nd["components_by_category"].get(idx, [None])[:1]))
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    ck("the expense-categories KPI shows the full total with its breakdown",
       "_v(_ns&&(_ns.categories_total||_ns.categories))" in html and "base paths ${fmtComma(+_ns.categories[0])} + components ${fmtComma(+_ns.components[0])}" in html)
    ck("each category editor shows its component charge", "${_catCompRunHtml(i)}" in html and "function _catCompRunHtml(i){" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
