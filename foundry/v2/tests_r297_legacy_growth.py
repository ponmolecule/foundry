"""r297: converting legacy per-period growth to a flow spec is exact (step at the model period), and the guard compares
against the saved copy's converted view so a format conversion is not listed as user changes."""
import copy
import sys
from pathlib import Path

from foundry.v2.income_modules import nie_category_series, simple_overhead_series


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond, d=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, d)
    ck("the console converts legacy growth as step at the model period (not smooth)",
       'return {rate:+(legacyRate||0),period:p,method:"step",anchor:"model_period"};' in html
       and 'return {rate:+(legacyRate||0),period:p,method:"smooth",anchor:"model_period"};' not in html)
    for ppy, Q, per, base, g in ((4, 12, "quarter", 1800000.0, 0.01), (12, 36, "month", 600000.0, 0.0033)):
        a = {"overhead_per_period": base, "overhead_growth_per_period": g}
        b = {"overhead_flow_spec": {"trajectory": "growth", "value": base, "period": per,
                                    "growth_spec": {"rate": g, "period": per, "method": "step", "anchor": "model_period"}}}
        x, y = simple_overhead_series(a, Q, ppy), simple_overhead_series(b, Q, ppy)
        ck(f"overhead: converted spec equals the legacy path exactly ({per}ly model)", max(abs(i - j) for i, j in zip(x, y)) < 1e-6)
        c = {"name": "Rent", "trajectory": "growth", "per_period": base / 4, "growth_per_period": g}
        d = {"name": "Rent", "flow_spec": {"trajectory": "growth", "value": base / 4, "period": per,
                                           "growth_spec": {"rate": g, "period": per, "method": "step", "anchor": "model_period"}}}
        x, y = nie_category_series(c, Q, ppy), nie_category_series(d, Q, ppy)
        ck(f"category: converted spec equals the legacy path exactly ({per}ly model)", max(abs(i - j) for i, j in zip(x, y)) < 1e-6)
    ck("the guard compares against the saved copy's converted view (overhead and categories)",
       "_upgradeLegacyViews(orig, cur);" in html and "oa.overhead_flow_spec=_viewSimpleOpexFlow();" in html
       and "ct.flow_spec=_viewNieCatFlow(ct);" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
