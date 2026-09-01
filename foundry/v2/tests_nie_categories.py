"""Golden tests for the extended NIE category trajectories (flat | linear | explicit).
Back-compat invariant: a category with only per_quarter behaves byte-identically to the legacy
flat-repeated model. Run: python3 -m foundry.v2.tests_nie_categories"""
import sys
sys.path.insert(0, ".")
from foundry.v2.income_modules import nie_detail_series

def _cats(nd, Q=12):
    nd = dict(nd); nd["n_periods"] = Q
    return nie_detail_series({"nie_detail": nd, "n_periods": Q})["categories"]

def main():
    P = F = 0
    def ck(n, c):
        nonlocal P, F
        if c: P += 1; print(f"  PASS  {n}")
        else: F += 1; print(f"  FAIL  {n}")
    ck("flat (legacy) sums per_quarter repeated",
       _cats({"categories":[{"per_quarter":100},{"per_quarter":50}]}) == [150.0]*12)
    lin = _cats({"categories":[{"per_quarter":100,"trajectory":"linear","growth_q":0.10}]})
    ck("linear q1=base, q2=base*1.1, q3=base*1.21",
       abs(lin[0]-100)<1e-9 and abs(lin[1]-110)<1e-9 and abs(lin[2]-121)<1e-9)
    exp = _cats({"categories":[{"trajectory":"explicit","schedule":[10,20,30]}]})
    ck("explicit follows schedule, pads 0", exp[:3]==[10.0,20.0,30.0] and exp[3]==0.0 and exp[11]==0.0)
    mix = _cats({"categories":[
        {"per_quarter":100},
        {"per_quarter":10,"trajectory":"linear","growth_q":1.0},
        {"trajectory":"explicit","schedule":[5,5,5]}]})
    ck("mixed categories sum per quarter",
       abs(mix[0]-115)<1e-9 and abs(mix[1]-125)<1e-9 and abs(mix[3]-180)<1e-9)
    ck("empty categories -> zeros", _cats({"categories":[]}) == [0.0]*12)
    print(f"\n{P} passed, {F} failed")
    return 0 if F==0 else 1

if __name__ == "__main__":
    sys.exit(main())
