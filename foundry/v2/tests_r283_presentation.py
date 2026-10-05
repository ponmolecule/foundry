"""r283 regression gate: quiet canvas, centred analysis sheets, collapsible Securities & balances page."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("canvas on every page except Balance Sheet, Income Statement and Welcome",
       "document.body.classList.toggle('fd-canvas',!['bs','is','welcome'].includes(currentTab));" in html and "document.body&&document.body.classList" in html
       and "body.fd-canvas,body.fd-canvas #content,body.fd-canvas main{background:#f0efeb!important}" in html)
    ck("centred white sheet on the analysis and record pages (nine tabs since r290)",
       "const _FD_SHEET_TABS=['detail','ratios','stress','overview','peer','examiner','notes','lab','gov'];" in html and "max-width:1440px;margin:0 auto 40px;background:#fff" in html)
    i_band = html.find("band.classList.add('pg-band');")
    i_wrap = html.find("if(typeof _fdWrapSheet==='function') _fdWrapSheet(c, tab);   // r283")   # the generic path (Governance has its own header path since r290)
    ck("the sheet is wrapped only after the title band is chosen (never painted as the band)", 0 < i_band < i_wrap)
    ck("no r282-style pre-band workspace wrapper", "workspace-sheet" not in html)
    ck("Securities presenter builds five sections and moves the existing wired blocks",
       "function _presentSecuritiesPage()" in html and html.count("['s") >= 5 and "body('s5').appendChild(B.mp)" in html
       and "if(tst) tst.remove(); if(fp) fp.remove();" in html)
    ck("sections start closed (open state only from explicit user toggles)",
       "window._fsxOpen=window._fsxOpen||{};" in html and "class=\"fsx-sec${window._fsxOpen[k]?' open':''}\"" in html)
    ck("section-level controls work on the closed header (moved, not re-created)",
       "ctl('s2').appendChild(lab)" in html and "ctl('s3').appendChild(mode)" in html and "onclick=\"event.stopPropagation()\"" in html)
    ck("summaries follow edits", "document.addEventListener('change',e=>{ const sec=e.target&&e.target.closest&&e.target.closest('.fsx-sec');" in html)
    ck("include switch sized above the #content checkbox rule", "#content .fsx-ctl .fsx-include input[type=checkbox]{width:30px!important;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
