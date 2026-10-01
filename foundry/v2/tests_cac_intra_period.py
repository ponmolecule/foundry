"""r221 regression gate: customer-acquisition intra-period path options.

Options (feed level; absent keys = historical behaviour):
  intra_period_path: monthly_flows (default) | straight_line
  path_anchor:       year (default) | quarter          (straight_line only)
  attrition_timing:  period_end (default) | spread | period_start   (monthly_flows only)

Guarantees checked here:
  * defaults are byte-identical to explicitly-stated defaults;
  * every option leaves attrition-period and anchor balances and annual totals unchanged;
  * each option's monthly path equals its closed-form definition;
  * Engagement B (monthly 1.5% attrition, spend ÷ CAC) reproduces its source sheet in all 36 months
    under every timing option; Engagement A (annual attrition, straight-line source) reproduces its
    source's monthly averages with straight_line/year;
  * invalid values are rejected;
  * run output carries no comparison data (removed in r223: not a user need).
"""
from __future__ import annotations
import copy, json, math, sys


def main():
    sys.path.insert(0, ".")
    from foundry.v2.cac_feeder import cac_auc_rollforward as roll
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))
    E = lambda k, v, cad, **kw: dict({"source": "entered", "mode": "explicit", "trajectory": "explicit", "cadence": cad,
                                       "extend": "hold", "resolution": "step", "owner_module": "customer_acquisition",
                                       "semantic_type": k, "values": v}, **kw)
    F = lambda k, v, **kw: dict({"source": "entered", "mode": "flat", "trajectory": "flat", "value": v,
                                  "owner_module": "customer_acquisition", "semantic_type": k}, **kw)
    B = {"beginning_customers": 1200, "beginning_auc": 0, "owner_module": "customer_acquisition",
         "driver_specs": {"attrition_rate": F("attrition_rate", 0.015, period="month")},
         "channels": [{"name": "Paid", "method": "spend_cac", "driver_specs": {
             "spend": E("spend", [10e6, 15e6, 22e6], "year", period="year"),
             "cac": E("cac", [16000.0, 20000.0, 22000.0], "year", period="year"),
             "avg_auc_per_customer": F("avg_auc_per_customer", 0.0)}}]}
    SRC_B = [1234, 1268, 1301, 1333, 1365, 1397, 1428, 1459, 1489, 1519, 1548, 1577, 1616, 1654, 1692, 1729, 1765,
             1801, 1837, 1872, 1906, 1940, 1974, 2006, 2060, 2112, 2164, 2215, 2265, 2314, 2363, 2411, 2458, 2504,
             2550, 2595]
    new_auc = [1008000, 1705304, 2726591, 3846656, 5073150, 6257351, 7586276]
    newc = [38, 68, 108, 148, 185, 220, 253]
    A = {"beginning_customers": 0, "beginning_auc": 0, "owner_module": "customer_acquisition",
         "driver_specs": {"attrition_rate": E("attrition_rate", [0.0, 0.04, 0.03, 0.03, 0.025, 0.025, 0.02], "year", period="year")},
         "channels": [{"name": "Explicit", "method": "explicit", "driver_specs": {
             "new_customers": E("new_customers", [float(x) for x in newc], "year", period="year"),
             "avg_auc_per_customer": E("avg_auc_per_customer", [a / c for a, c in zip(new_auc, newc)], "year", period="year")}}]}
    SRC_A_Y1 = [42000, 126000, 210000, 294000, 378000, 462000, 546000, 630000, 714000, 798000, 882000, 966000]
    SRC_A_Y7 = [x / 1000 for x in [20065061696, 20664308976, 21263556256, 21862803536, 22462050815, 23061298095,
                                   23660545375, 24259792654, 24859039934, 25458287214, 26057534494, 26656781773]]
    Q = lambda attr_period_cfg: attr_period_cfg
    def with_(cfg, **kw):
        c = copy.deepcopy(cfg); c.update(kw); return c
    avgA = lambda r: [(m["beg_auc"] + m["end_auc"]) / 2 for m in r["monthly"]]

    # 1. defaults: explicit defaults are byte-identical to absent keys
    for nm, cfg, n in (("B", B, 36), ("A", A, 84)):
        d0 = roll(cfg, n, 12); d1 = roll(with_(cfg, intra_period_path="monthly_flows", path_anchor="year",
                                               attrition_timing="period_end"), n, 12)
        ck(f"{nm}: stating the defaults explicitly gives byte-identical output",
           json.dumps(d0, sort_keys=True, default=str) == json.dumps(d1, sort_keys=True, default=str))

    # 2. engagement B acceptance: monthly attrition is unaffected by timing
    for t in ("period_end", "spread", "period_start"):
        v = [m["end_cust"] for m in roll(with_(B, attrition_timing=t), 36, 12)["monthly"]]
        ck(f"B: timing '{t}' reproduces the source sheet in all 36 months",
           all(round(x) == y for x, y in zip(v, SRC_B)), f"M36 {v[-1]:.3f}")
    vsl = [m["end_cust"] for m in roll(with_(B, intra_period_path="straight_line"), 36, 12)["monthly"]]
    ck("B: a straight line is not equivalent for B (the reason the setting is per feed)",
       sum(round(x) == y for x, y in zip(vsl, SRC_B)) < 36)

    # 3. engagement A acceptance: straight line between year-ends reproduces the source's monthly averages
    ra = roll(with_(A, intra_period_path="straight_line", path_anchor="year"), 84, 12); va = avgA(ra)
    ck("A: straight line (year anchors) matches the source's Year 1 monthly averages exactly",
       max(abs(a - b) for a, b in zip(va[:12], SRC_A_Y1)) < 1e-6)
    ck("A: straight line matches the source's Year 7 monthly averages (within input rounding, < 0.5 $000s)",
       max(abs(a - b) for a, b in zip(va[72:84], SRC_A_Y7)) < 0.5)

    # 4. invariants and closed forms, across attrition periods month / quarter / year
    def feed(period, cad_vals):
        c = copy.deepcopy(A); c["driver_specs"]["attrition_rate"] = E("attrition_rate", cad_vals, period, period=period); return c
    cases = {"year": feed("year", [0.0, 0.04, 0.03, 0.03, 0.025, 0.025, 0.02]),
             "quarter": feed("quarter", [0.01 + 0.0005 * i for i in range(28)]),
             "month": feed("month", [0.004] * 84)}
    W = {"year": 12, "quarter": 3, "month": 1}
    for per, cfg in cases.items():
        base = roll(cfg, 84, 12)
        for opt in ({"attrition_timing": "spread"}, {"attrition_timing": "period_start"},
                    {"intra_period_path": "straight_line", "path_anchor": "year"},
                    {"intra_period_path": "straight_line", "path_anchor": "quarter"}):
            r = roll(with_(cfg, **opt), 84, 12); lbl = f"{per} attrition, {opt}"
            w = W[per] if "attrition_timing" in opt else (12 if opt.get("path_anchor") == "year" else 3)
            ends_ok = all(abs(r["monthly"][i]["end_auc"] - base["monthly"][i]["end_auc"]) < 1e-6
                          and abs(r["monthly"][i]["end_cust"] - base["monthly"][i]["end_cust"]) < 1e-9
                          for i in range(w - 1, 84, w))
            ck(f"invariant · {lbl}: balances at every {'attrition-period' if 'attrition_timing' in opt else 'anchor'} end unchanged", ends_ok)
            tot_ok = all(abs(a["auc_lost"] - b["auc_lost"]) < 1e-6 and abs(a["new_auc"] - b["new_auc"]) < 1e-6
                         for a, b in zip(r["annual"], base["annual"]))
            ck(f"invariant · {lbl}: annual new and lost totals unchanged", tot_ok)
            roll_ok = all(abs(m["beg_auc"] + m["new_auc"] - m["auc_lost"] - m["end_auc"]) < 1e-6 for m in r["monthly"])
            ck(f"invariant · {lbl}: beginning + new − lost = end in every month", roll_ok)
            if opt.get("attrition_timing") == "spread" and per != "month":
                tl = [sum(base["monthly"][i]["auc_lost"] for i in range(k, k + w)) for k in range(0, 84, w)]
                cf = all(abs(r["monthly"][i]["auc_lost"] - tl[i // w] / w) < 1e-6 for i in range(84))
                ck(f"closed form · {lbl}: each month carries 1/{w} of its period's loss", cf)
            if opt.get("attrition_timing") == "period_start" and per != "month":
                tl = [sum(base["monthly"][i]["auc_lost"] for i in range(k, k + w)) for k in range(0, 84, w)]
                cf = all(abs(r["monthly"][i]["auc_lost"] - (tl[i // w] if i % w == 0 else 0.0)) < 1e-6 for i in range(84))
                ck(f"closed form · {lbl}: the whole period's loss lands in its first month", cf)
            if opt.get("intra_period_path") == "straight_line":
                prev = 0.0; lin = True
                for a0 in range(0, 84, w):
                    e = base["monthly"][a0 + w - 1]["end_auc"]
                    for k in range(w):
                        lin &= abs(r["monthly"][a0 + k]["end_auc"] - (prev + (e - prev) * (k + 1) / w)) < 1e-6
                    prev = e
                ck(f"closed form · {lbl}: months between anchors move in equal steps", lin)
            if per == "month" and "attrition_timing" in opt:
                ck(f"monthly attrition · {lbl}: identical to the default (timing has nothing to move)",
                   all(abs(a["end_auc"] - b["end_auc"]) < 1e-9 for a, b in zip(r["monthly"], base["monthly"])))

    # 5. quarterly engine cadence uses the same monthly grid
    rq = roll(with_(A, attrition_timing="spread"), 28, 4)
    ck("quarterly engine cadence: options apply on the monthly grid and quarter-end balances are published",
       len(rq["auc_end_by_period"]) == 28 and abs(rq["auc_end_by_period"][-1] - roll(A, 28, 4)["auc_end_by_period"][-1]) < 1e-6)

    # 7. end to end: AUC-driven fee streams consume the chosen path
    from foundry.v2.run_q import run_v2
    fx = json.load(open("foundry/fixtures/universal_template_bank.json"))
    fn = "Universal Customer Build"
    def mn(cfg):
        R = run_v2(cfg); R = R.get("public", R)
        pr = [x for x in R["products"] if isinstance(x, dict) and x.get("name") == "Stream and pricing mechanics"][0]
        return R, pr["managedNotionalAvg"]
    R0, a0 = mn(fx)
    fx2 = copy.deepcopy(fx); fx2["assumptions"]["cac_feeds"][fn].update({"intra_period_path": "straight_line", "path_anchor": "year"})
    R1, a1 = mn(fx2)
    ends = R1["customer_acquisition"][fn]["aucEndByMonth"]
    ck("end to end: product average AUC follows the straight-line feed path",
       abs(a1[-1] - (ends[-2] + ends[-1]) / 2) < 0.01 and abs(a1[-1] - a0[-1]) > 1.0, f"M36 average {a0[-1]:,.2f} → {a1[-1]:,.2f}")
    ck("end to end: year-end AUC published by the feed is unchanged",
       [round(x, 6) for x in R1["customer_acquisition"][fn]["yearEndAUC"]] == [round(x, 6) for x in R0["customer_acquisition"][fn]["yearEndAUC"]])

    ck("run output carries no option-comparison block", all("pathComparison" not in v for v in R1["customer_acquisition"].values()))

    # 6. invalid values are rejected
    for bad in ({"intra_period_path": "bogus"}, {"path_anchor": "month"}, {"attrition_timing": "later"}):
        try: roll(with_(B, **bad), 36, 12); ok = False
        except ValueError: ok = True
        ck(f"invalid option rejected: {bad}", ok)

    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__": sys.exit(main())
