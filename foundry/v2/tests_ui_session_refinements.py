"""Focused UI/session regressions for operating-expense mode, save recovery, login, securities."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond:
            p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html=Path("web/console_v2.html").read_text(encoding="utf-8")

    # Execute the actual operating-expense mode helpers and mode-switch functions.
    a=html.index("function _operatingExpenseMode(")
    b=html.index("function structuresSectionsHtml()", a)
    helpers=html[a:b]
    c=html.index("window.nieOff = function(){")
    d=html.index("// Static mirror", c)
    switches=html[c:d]
    js=r'''
const window=globalThis;
let cfg={assumptions:{overhead_per_period:0,overhead_growth_per_period:0}};
function renderContent(){} function refresh(){}
function _newNieDetail(){return {categories:[{name:'kept'}],workforce:{roles:[]}};}
''' + helpers + switches + r'''
const initial=_operatingExpenseMode(cfg.assumptions);
window.nieOff(); const simple=_operatingExpenseMode(cfg.assumptions);
window.nieOn(); const detailed=_operatingExpenseMode(cfg.assumptions);
window.nieOff(); const preserved=!!cfg.assumptions._nie_detail_draft;
window.opexToggle(); const off=_operatingExpenseMode(cfg.assumptions);
window.opexToggle(); const reactivated=_operatingExpenseMode(cfg.assumptions);
console.log(JSON.stringify({initial,simple,detailed,preserved,off,reactivated}));
'''
    r=subprocess.run(["node","-e",js],text=True,capture_output=True)
    j={}
    if r.returncode==0 and r.stdout.strip():
        try:j=json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:pass
    ck("Simple mode is an active Operating Expense mode, not the module-off state",
       r.returncode==0 and j.get("initial")=="off" and j.get("simple")=="simple"
       and j.get("detailed")=="detailed" and j.get("preserved") is True
       and j.get("off")=="off" and j.get("reactivated")=="detailed", r.stderr.strip())
    ck("Operating Expense module strip derives on/off from explicit Simple or Detailed mode",
       '_opexModeTile !== "off"' in html and 'else if(act==="nie"){ opexToggle(); }' in html)

    # Explicit saves must retire crash recovery; boot must also suppress stale duplicates from older builds.
    ck("both explicit save paths purge crash-recovery drafts after successful save",
       html.count("await _purgeRecoveryDrafts();") >= 2
       and '"unsaved-engagement-crash-recovery", "working-session-autosaved"' in html)
    ck("boot suppresses an already-saved duplicate recovery draft instead of warning",
       "_duplicateOfSaved" in html and "LC._ser(savedCfg) === LC._ser(draftCfg)" in html)

    ck("login hero lift is responsive: airy on tall displays without colliding on laptop-height viewports",
       'class="welcome-main"' in html
       and '.welcome-main{transform:translateY(calc(-1 * clamp(3rem, 8vh, 8rem)))}' in html
       and 'translateY(-9rem)' not in html)
    ck("superfluous HTM-designation counter is removed",
       "HTM designated" not in html and "Books included" not in html)

    # Product Details is both presentation-facing and a reconciliation surface. Presentation
    # stays at 3 decimals; the explicit toggle exposes the SAME value at up to 15 significant digits.
    a=html.index("function fmtProductK(")
    b=html.index("function cellNum(", a)
    fmt_fn=html[a:b]
    fmt_js='let productDetailHighPrecision=false;\n' + fmt_fn + '''
const vals=[
  0.385651040655852,
  2.02032978720981,
  0.019282552032793,
  0.101016489360491,
  257.100693770568,
  1346.88652480654,
  0
];
const presentation=vals.map(fmtProductK);
productDetailHighPrecision=true;
const high=vals.map(fmtProductK);
const auditSum=0.019282552032793+0.019282552032793+0.000214247150107;
console.log(JSON.stringify({presentation,high,auditSum,auditSumShown:fmtProductK(auditSum)}));
'''
    rr=subprocess.run(["node","-e",fmt_js],text=True,capture_output=True)
    vals={}
    if rr.returncode==0 and rr.stdout.strip():
        try: vals=json.loads(rr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Product Details presentation mode uses fixed three-decimal $000s precision",
       rr.returncode==0 and vals.get("presentation")==["0.386","2.020","0.019","0.101","257.101","1,346.887","0.000"], rr.stderr.strip())
    ck("Product Details high-precision mode exposes underlying values without display rounding",
       rr.returncode==0
       and vals.get("high")==["0.385651040655852","2.02032978720981","0.019282552032793","0.101016489360491","257.100693770568","1,346.88652480654","0"]
       and abs(vals.get("auditSum",0)-0.038779351215693)<1e-15
       and vals.get("auditSumShown")=="0.038779351215693", rr.stderr.strip())
    ck("Product Details exposes an explicit presentation/high-precision reconciliation toggle",
       "function setProductDetailPrecision(v)" in html
       and "productDetailHighPrecision = !!v" in html
       and 'data-product-detail-precision="1"' in html
       and "High precision <span" in html
       and "productDetailPrecisionToggleHtml()" in html)
    ck("per-product detail table uses the unrounded diagnostic series and precision-aware formatter",
       "function productDetailSeries(p, key)" in html
       and "p.detailExact && p.detailExact[key]" in html
       and "rowBSProduct('Fee income', productDetailSeries(p, 'fees'))" in html
       and "rowBSProduct('Operating costs', productDetailSeries(p, 'opex'))" in html
       and "const _pc=productDetailSeries(p, 'passCost')" in html
       and "Math.abs(+x)>1e-9" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
