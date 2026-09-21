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
    ck("switching engagements closes transient paste editors instead of restoring visual clutter",
       "function _resetTransientAuthoringUi(c)" in html
       and "window._structuredPasteOpen={};" in html
       and "window._pasteSurfaceDefaultClosed=true" in html
       and "window._pasteSurfaceCloseAllOnNextRender=true" in html
       and "cfg = normalizeCfg(cfg2);\n    _resetTransientAuthoringUi(cfg);" in html
       and "cfg = buildEmptyTemplate();\n    _resetTransientAuthoringUi(cfg);" in html)

    ck("superfluous HTM-designation counter is removed",
       "HTM designated" not in html and "Books included" not in html)

    ck("long-horizon Summary Ratios freezes the Ratio column",
       "fin freeze-metric' + (V21 ? ' has-ref' : '')" in html
       and "table.fin.freeze-metric.has-ref td.ref + td" in html)
    ck("long-horizon Standardized Capital freezes the Measure column",
       '<table class="fin freeze-metric"><tr><th>Measure</th>' in html
       and "table.fin.freeze-metric:not(.has-ref) td:first-child" in html)

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

    ck("Product cards expose persistent drag handles with insertion markers and keyboard movement",
       'class="product-drag-handle" draggable="true"' in html
       and 'productDragStart(event' in html and 'productDrop(event' in html
       and '.product-card.drop-before:before,.product-card.drop-after:after' in html
       and "event.key==='ArrowUp'" in html and "event.key==='ArrowDown'" in html)
    ck("Product reorder is family-scoped and canonicalizes legacy managed-notional references first",
       "String(d.fam)!==String(fam)" in html
       and "_canonicalizeLegacyWorkforceAucTriggers" in html[html.index("function _productReorder"):html.index("function delProduct", html.index("function _productReorder"))])

    # Execute the shipped reorder controller: the actual product objects move in the saved arrays,
    # expanded/collapsed state follows those objects, and a drag cannot reclassify a product across families.
    pa=html.index("function toggleOpen(key)")
    pb=html.index("function v31ModalBody()", pa)
    product_js=html[pa:pb]
    node_prefix = r'''
const window=globalThis;
const document={querySelectorAll:()=>[]};
const ARR_OF={lending:'lending_products',deposit:'deposit_products',obs:'obs_exposures'};
let cfg={assumptions:{
 lending_products:[{name:'Loan A',marker:'A'},{name:'Loan B',marker:'B'}],
 deposit_products:[{name:'Deposit A',marker:'D'}],
 obs_exposures:[{name:'Fee A',marker:'F'}]
}};
let openMap={lending_0:false,lending_1:true,deposit_0:false};
function famArr(fam){return cfg.assumptions[ARR_OF[fam]];}
function renderContent(){} function refresh(){}
let canonicalized=0;function _canonicalizeLegacyWorkforceAucTriggers(){canonicalized++;}
'''
    node_suffix = r'''
const loanA=cfg.assumptions.lending_products[0], loanB=cfg.assumptions.lending_products[1];
const moved=_productReorder('lending',0,1,true);
const afterDown={names:cfg.assumptions.lending_products.map(x=>x.name),sameA:cfg.assumptions.lending_products[1]===loanA,sameB:cfg.assumptions.lending_products[0]===loanB,open0:openMap.lending_0,open1:openMap.lending_1};
window.productMove('lending',1,-1);
const afterKeyboard={names:cfg.assumptions.lending_products.map(x=>x.name),sameA:cfg.assumptions.lending_products[0]===loanA,open0:openMap.lending_0};
window._productDrag={fam:'lending',index:0};
window.productDrop({preventDefault(){},currentTarget:{dataset:{dropAfter:'1'}}},'deposit',0);
const crossGuard={loans:cfg.assumptions.lending_products.map(x=>x.name),deposits:cfg.assumptions.deposit_products.map(x=>x.name)};
console.log(JSON.stringify({moved,afterDown,afterKeyboard,crossGuard,canonicalized}));
'''
    rr2=subprocess.run(["node","-e",node_prefix+product_js+node_suffix],text=True,capture_output=True)
    pj={}
    if rr2.returncode==0 and rr2.stdout.strip():
        try: pj=json.loads(rr2.stdout.strip().splitlines()[-1])
        except Exception: pass
    ad=pj.get("afterDown") or {}; ak=pj.get("afterKeyboard") or {}; cg=pj.get("crossGuard") or {}
    ck("drag reorder moves the actual product objects and carries open state with them",
       rr2.returncode==0 and pj.get("moved") is True and ad.get("names")==["Loan B","Loan A"]
       and ad.get("sameA") is True and ad.get("sameB") is True and ad.get("open0") is True and ad.get("open1") is False, rr2.stderr.strip())
    ck("keyboard reorder uses the same persistent array order",
       ak.get("names")==["Loan A","Loan B"] and ak.get("sameA") is True and ak.get("open0") is False)
    ck("dragging across product families cannot silently reclassify a product",
       cg.get("loans")==["Loan A","Loan B"] and cg.get("deposits")==["Deposit A"] and pj.get("canonicalized",0)>=2)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
