"""r292: the FDIC assessment defaults to 0 bp everywhere, including the universal template."""
import copy
import json
import sys

from foundry.v2.regparams import REG_PARAMS
from foundry.v2.run_q import run_v2


def main():
    p = f = 0
    def ck(name, cond, d=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, d)
    t = json.load(open("foundry/fixtures/universal_template_bank.json"))
    ck("the universal template stores 0 bp", t["assumptions"]["nie_detail"].get("fdic_bp_ann") == 0.0)
    ck("the engine fallback is 0 bp", REG_PARAMS["assessments"]["fdic_bp_ann"] == 0.0)
    html = open("web/console_v2.html", encoding="utf-8").read()
    ck("a new engagement starts at 0 bp and an unset rate displays as 0",
       "fdic_bp_ann:0, occ_simplified_enabled:false" in html and "const _fdic=(nd.fdic_bp_ann!=null?+nd.fdic_bp_ann:0);" in html)
    unset = copy.deepcopy(t); unset["assumptions"]["nie_detail"].pop("fdic_bp_ann", None)
    explicit = copy.deepcopy(t); explicit["assumptions"]["nie_detail"]["fdic_bp_ann"] = 5.0
    ni = lambda c: sum(x or 0 for x in run_v2(c)["financials"]["is"]["ni"])
    a, b, c = ni(t), ni(unset), ni(explicit)
    ck("0 bp and unset give identical results", abs(a - b) < 1e-6, f"{a} vs {b}")
    ck("an explicit rate is still honoured (5 bp lowers net income)", c < a - 1.0, f"{c} vs {a}")
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
