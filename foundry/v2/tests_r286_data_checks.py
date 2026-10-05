"""r286: Governance data checks catch digit and unit slips in every schedule (incl. level schedules), check
edits against the last save, and the change diff ignores float noise. The user's own fat-finger is pinned."""
import copy
import glob
import json
import math
import random
import sys

from foundry.v2 import data_checks as dc
from foundry.v2.config_diff import diff

ORIG = [123, 634, 1106, 1200, 1297, 1397, 1428, 1459, 1489, 1519, 1548, 1577, 1616, 1654, 1692, 1729, 1765, 1801,
        1837, 1872, 1906, 1940, 1974, 2006, 2060, 2112, 2164, 2215, 2265, 2314, 2363, 2411, 2458, 2504, 2550, 2595]


def main():
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, detail)

    def why(vals):
        return [((b["signature"] or {}).get("why"), b["i"]) for b in dc._trend_breaks(vals)]

    fat = list(ORIG); fat[1] = 1634
    ck("the user's fat-finger (634 typed as 1,634 in M2) is caught as an extra leading 1",
       why(fat) == [("an extra 1 at the start", 1)], str(why(fat)))
    ck("the unmodified series (steep start, year-start bumps) is not flagged", why(ORIG) == [])
    for name, i, v, want in (("x1,000 slip", 19, 1872000, "1,000x too large"), ("swapped digits", 8, 1849, "digits 84 swapped"),
                             ("dropped digit", 12, 166, "a missing 1"), ("slip in the final period", 35, 25950, "an extra 0")):
        x = list(ORIG); x[i] = v; w = why(x)
        ck(f"{name} is caught with the right explanation", len(w) == 1 and w[0][1] == i and (w[0][0] or "").startswith(want), str(w))
    x = list(ORIG); x[29] = 2341
    ck("a wrong but on-trend value is not flagged (documented limit)", why(x) == [])
    random.seed(7)
    named = [[100 + 12 * i for i in range(36)], [1000 * 1.02 ** i for i in range(36)], [1000 + 250 * math.sin(2 * math.pi * i / 12) for i in range(36)],
             [500] * 18 + [800] * 18, [1000 * (1 + 0.05 * random.gauss(0, 1)) for i in range(36)], [3000 / (1 + math.exp(-(i - 18) / 3)) for i in range(36)],
             [100 * (1 + i // 3) for i in range(36)]]
    fp = sum(len(dc._trend_breaks(v)) for v in named)
    random.seed(11)
    for _ in range(300):
        base = random.uniform(50, 5000); drift = random.uniform(-0.02, 0.04); noise = random.uniform(0, 0.03)
        v = [base]
        for _ in range(35):
            v.append(v[-1] * (1 + drift + noise * random.gauss(0, 1)))
        fp += len(dc._trend_breaks(v))
    ck("no false positives across 7 named shapes and 300 randomized clean series", fp == 0, f"fp={fp}")
    tot = 0
    for path in sorted(glob.glob("foundry/fixtures/*.json")) + sorted(glob.glob("foundry/fixtures/parity/configs/*.json")):
        c = json.load(open(path))
        if "assumptions" in c:
            tot += len(dc.trend_findings(c))
    ck("no trend findings on any shipped fixture", tot == 0, f"findings={tot}")
    saved = json.load(open("foundry/fixtures/universal_template_bank.json"))
    ls = saved["assumptions"]["obs_exposures"][2]["fee_streams"][0]["driver"]["params"]["level_schedule"]
    ck("level schedules are scanned (previously skipped)",
       any(s["kind"] == "level schedule" for s in dc._all_series(saved)))
    ls["period"] = "month"; ls["schedule"] = {str(i + 1): float(v) for i, v in enumerate(ORIG)}
    live = copy.deepcopy(saved)
    live["assumptions"]["obs_exposures"][2]["fee_streams"][0]["driver"]["params"]["level_schedule"]["schedule"]["2"] = 1634.0
    F = dc.run_checks(live, saved=saved)
    ck("end to end: one Needs-review finding on the level schedule, with the saved value",
       len(F) == 1 and F[0]["severity"] == "review" and F[0]["label"] == "2" and F[0].get("changed_from") == "634"
       and "extra 1 at the start" in F[0]["signature"] and F[0]["field"] == "Count", str(F))
    live2 = copy.deepcopy(saved)
    live2["assumptions"]["obs_exposures"][2]["fee_streams"][0]["driver"]["params"]["level_schedule"]["schedule"]["1"] = 1230.0
    E = [g for g in dc.run_checks(live2, saved=saved) if g["kind"] == "edit"]
    ck("an edge slip is named by the edited-since-save check", len(E) == 1 and E[0]["label"] == "1" and "extra 0" in E[0]["signature"], str(E))
    mk = lambda sch: {"assumptions": {"obs_exposures": [{"name": "FedWire Direct Fees", "fee_streams": [{"name": "Migrated MAB FedWire",
                      "driver": {"params": {"level_schedule": {"period": "month", "schedule": sch}}}}]}]}}
    noise = {str(i + 1): float(v) * (1 + 1e-13) for i, v in enumerate(ORIG)}
    edit = {str(i + 1): float(v) for i, v in enumerate(ORIG)}; edit["2"] = 1634.0
    d = diff(mk(noise), mk(edit))
    ck("change tracking ignores float noise: one real change, not 36", len(d) == 1 and d[0]["field"].endswith("M2")
       and d[0]["before"] == "634" and d[0]["after"] == "1,634", str(d))
    sub = {str(i + 1): float(v) + 0.4 for i, v in enumerate(ORIG)}
    d = diff(mk(sub), mk(edit))
    ck("real sub-unit changes are shown with decimals and merged into one range",
       len(d) == 1 and d[0]["field"].endswith("M1 to M36") and d[0]["before"].startswith("123.4"), str(d)[:200])
    ck("the catalogue lists the checks and their limits", len(dc.CATALOG) >= 8 and len(dc.LIMITS) >= 5
       and any("Digit slip" in c["check"] for c in dc.CATALOG))
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
