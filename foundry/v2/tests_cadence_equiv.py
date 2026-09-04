"""Cross-cadence economic-equivalence harness (audit Phase 0, the master gate).

Runs ONE simple deterministic bank quarterly (ppy=4) and monthly (ppy=12) with the SAME economics,
and asserts agreement at year-ends within tolerance. This is the test that would have caught the
x4-ratio / FTP / duration bugs. It is EXPECTED to fail on known-broken items until they are fixed.

Run: python3 -m foundry.v2.tests_cadence_equiv
"""
import sys, json, copy
sys.path.insert(0, ".")
from foundry.v2 import run_q

def _base():
    c = json.load(open("foundry/fixtures/universal_template_bank.json"))
    return c

def _run(ppy, years):
    c = _base()
    a = c["assumptions"]
    a["periods_per_year"] = ppy
    a["n_periods"] = years * ppy
    # convert per-period rates to the cadence: growth/runoff are per-period; to keep the SAME annual
    # economics, a quarterly g_q maps to a monthly g_m with (1+g_m)^3 = (1+g_q).
    def _map(o):
        if isinstance(o, dict):
            for k in ("growth_per_period", "runoff_per_period", "orig_growth_per_period"):
                if k in o and o[k] is not None:
                    gq = o[k]
                    if ppy == 12:
                        o[k] = (1.0 + gq) ** (1.0/3.0) - 1.0   # quarterly -> monthly equivalent
            for v in o.values(): _map(v)
        elif isinstance(o, list):
            for v in o: _map(v)
    if ppy == 12:
        _map(a)
    return run_q.run_v2(c)

def _year_ends(series, ppy):
    # value at each year-end period (index ppy-1, 2*ppy-1, ...)
    return [series[i] for i in range(ppy-1, len(series), ppy)]

def _annual_sums(series, ppy):
    # sum each year's periods (series is 1-based with [0] placeholder or 0-based? engine 'is' arrays
    # are 1-based with index0 placeholder for some; handle both by trimming leading None)
    s = series[1:] if (series and series[0] is None) else series
    return [sum(x for x in s[y*ppy:(y+1)*ppy] if x is not None) for y in range(len(s)//ppy)]

def main():
    P = F = 0
    def ck(name, cond, detail=""):
        nonlocal P, F
        tag = "PASS" if cond else "FAIL"
        if cond: P += 1
        else: F += 1
        print(f"  {tag}  {name}" + (f" — {detail}" if detail else ""))

    YEARS = 3
    q = _run(4, YEARS)["financials"]
    m = _run(12, YEARS)["financials"]
    TOL = 0.01  # 1% relative tolerance for legitimate compounding-frequency differences

    def rel(a, b):
        if a is None or b is None: return None
        if abs(a) < 1e-9: return abs(b) < 1.0
        return abs(a-b)/abs(a) <= TOL

    # 1. year-end total assets agree
    qa = _year_ends(q["bs"]["totalAssets"], 4)
    ma = _year_ends(m["bs"]["totalAssets"], 12)
    ck("year-end total assets agree (q vs m)", all(rel(x,y) for x,y in zip(qa,ma)),
       f"q={[round(x) for x in qa]} m={[round(x) for x in ma]}")

    # 2. annual net income agrees
    qni = _annual_sums(q["is"]["ni"], 4)
    mni = _annual_sums(m["is"]["ni"], 12)
    ck("annual net income agrees", all(rel(x,y) for x,y in zip(qni,mni)),
       f"q={[round(x) for x in qni]} m={[round(x) for x in mni]}")

    # 3. annual net interest income agrees
    qnii = _annual_sums(q["is"]["nii"], 4)
    mnii = _annual_sums(m["is"]["nii"], 12)
    ck("annual net interest income agrees", all(rel(x,y) for x,y in zip(qnii,mnii)),
       f"q={[round(x) for x in qnii]} m={[round(x) for x in mnii]}")

    # 4. year-end ROA agrees (THIS is the x4-vs-x12 bug — expected FAIL until Phase 2.1)
    qroa = _year_ends(q["ratios"]["roa"], 4)
    mroa = _year_ends(m["ratios"]["roa"], 12)
    ck("year-end ROA agrees (x4 bug gate)", all(rel(x,y) for x,y in zip(qroa,mroa)),
       f"q={[round(x,2) for x in qroa]} m={[round(x,2) for x in mroa]}")

    # 5. year-end NIM agrees (x4 bug)
    qnim = _year_ends(q["ratios"]["nim"], 4)
    mnim = _year_ends(m["ratios"]["nim"], 12)
    ck("year-end NIM agrees (x4 bug gate)", all(rel(x,y) for x,y in zip(qnim,mnim)),
       f"q={[round(x,2) for x in qnim]} m={[round(x,2) for x in mnim]}")

    # 6. year-end CET1 / leverage agree
    for key in ("cet1_ratio","leverage_ratio"):
        if key in q["ratios"] and key in m["ratios"]:
            qk = _year_ends(q["ratios"][key], 4); mk = _year_ends(m["ratios"][key], 12)
            ck(f"year-end {key} agrees", all(rel(x,y) for x,y in zip(qk,mk)),
               f"q={[round(x,2) if x else x for x in qk]} m={[round(x,2) if x else x for x in mk]}")

    print(f"\n{P} passed, {F} failed")
    return 0 if F == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
