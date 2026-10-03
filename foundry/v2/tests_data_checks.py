"""r247 regression gate: Governance & QA data checks (read-only)."""
import copy, json, sys


def main():
    sys.path.insert(0, ".")
    from foundry.v2.data_checks import run_checks
    from foundry.v2.run_q import run_v2
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))
    tpl = json.load(open("foundry/fixtures/universal_template_bank.json"))
    ck("a sound template produces no findings", run_checks(copy.deepcopy(tpl)) == [])
    att = [0.015] * 6 + [0.17, 0.1313, 0.0925, 0.0538] + [0.015] * 26
    cfg = {"assumptions": {"cac_feeds": {"SKN": {"driver_specs": {"attrition_rate": {"trajectory": "explicit", "period": "month", "values": att}},
                                                  "channels": [{"name": "Direct", "driver_specs": {"cac": {"value": {"trajectory": "explicit", "values": [16000.0] * 6 + [32000.0] + [16000.0] * 29}}}}]}}}}
    F = run_checks(cfg)
    a = [x for x in F if "attrition" in x["detail"]]
    c = [x for x in F if "CAC" in x["detail"]]
    ck("the incident's attrition spike is Needs review, months 7-10, with the annual-rate hint",
       len(a) == 1 and a[0]["severity"] == "review" and a[0]["start"] == 6 and a[0]["end"] == 9 and "annual rate" in a[0]["hint"])
    ck("a 2x CAC jump in the same month is flagged as a companion and cross-referenced",
       len(c) == 1 and c[0].get("companion") and c[0]["severity"] == "review" and c[0]["same_period_as"] == ["attrition rate"])
    ck("a steady 2x step change (not isolated) is not flagged",
       run_checks({"assumptions": {"x": {"trajectory": "explicit", "values": [1.0] * 10 + [2.0] * 26}}}) == [])
    t2 = copy.deepcopy(tpl); paths = []
    def find(o, pth=()):
        if isinstance(o, dict):
            if o.get("trajectory") == "explicit" and isinstance(o.get("values"), list) and len(o["values"]) >= 8: paths.append(pth)
            for k, v in o.items(): find(v, pth + (k,))
        elif isinstance(o, list):
            for i, v in enumerate(o): find(v, pth + (i,))
    find(t2); node = t2
    for k in paths[0]: node = node[k]
    node["values"][6] *= 10
    before = json.dumps(t2, sort_keys=True)
    G = run_checks(t2, runner=run_v2)
    ck("effects are estimated by running the model on copies", G and G[0]["severity"] == "review" and len(G[0]["effects"] or []) > 0)
    ck("the configuration passed in is left untouched", json.dumps(t2, sort_keys=True) == before)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
