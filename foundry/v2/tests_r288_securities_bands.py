"""r288: expanded Securities sections as bands; r287's layout layer retired; collapsed on arrival; no overlap risks."""
import re
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, detail)
    ck("r287's layout layer is fully retired (presenter and its grid rules)",
       "_layoutExpandedSecurities" not in html and "/* r287: bounded fields and deliberate product groups" not in html)
    ck("the band layout runs after every Securities render", "try{ _fsxBands(card); }catch(e)" in html and "function _fsxBands(card){" in html)
    ck("bands: funding (Policy; Rates, floors & other assets), numbered products, liability components, security detail bands",
       "_fsxBand('Policy'" in html and "'PRODUCT '+(n+1)" in html and "COMPONENT ${n+1}" in html and "_fsxBand('Holding')" in html and "_fsxBand('Yield')" in html)
    ck("one line per assumption: schedule summary as first -> last with its point count; Edit keeps the full title",
       "sum.innerHTML=`${esc(m[2])} \\u2192 ${esc(m[3])} <small>${esc(m[1])}</small>`" in html and "btn.textContent='Edit'" in html)
    ck("the linked-series row is recognised by its handler and its caption sits beneath (static)",
       "select[onchange*=\"ibMabLink\"]" in html and ".fsx-row.fsx-link>.cu{grid-column:2;display:block;" in html and "position:static!important" in html)
    ck("only the layout sizes these dropdowns (fitControls opt-out, inline minimums cleared)",
       "card.querySelectorAll('.fsx-b select').forEach(el=>{ el.setAttribute('data-nofit',''); el.style.removeProperty('min-width'); });" in html)
    ck("labels use their own class (no collision with r283's .fsx-n section numbers)",
       "'fsx-lab'" in html and ".fsx-row>.fsx-lab{" in html)
    i = html.find("/* r288: r287 layout layer retired."); j = html.find("</style>", i)
    blk = html[i:j]
    ck("r288 styles use no absolute or fixed positioning (no overlapping boxes)",
       i > 0 and not re.search(r"position:\s*(absolute|fixed)", blk))
    ck("narrow stages stack bands and keep summaries whole",
       "@container stage (max-width:1000px){" in html and "@container stage (max-width:1180px){" in html)
    ck("every section collapses when the user arrives (by tab or by module), not on re-renders",
       "if(t==='config'&&typeof currentTab!=='undefined'&&currentTab!=='config') window._fsxOpen={};" in html
       and "if(key==='sec'&&was!=='sec'&&typeof fsxAll==='function') fsxAll(false);" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
