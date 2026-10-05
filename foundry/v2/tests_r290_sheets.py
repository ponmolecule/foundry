"""r290: centred sheets on Examiner Book, Assumption Book, Bank Design Lab and Governance; chapter notation centred
only above a sheet; wide tables scroll inside the sheet."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("Examiner Book, Assumption Book, Bank Design Lab and Governance get the centred sheet",
       "const _FD_SHEET_TABS=['detail','ratios','stress','overview','peer','examiner','notes','lab','gov'];" in html)
    ck("Governance's own header path wraps the sheet too",
       "<b>Governance &amp; QA</b></div>'); if(typeof _fdWrapSheet==='function') _fdWrapSheet(c, tab); return; } }" in html)
    ck("the chapter notation is centred only above a centred sheet (never floating over left-aligned content)",
       "body.fd-canvas #content:has(>.fd-sheet)>.pg-crumb{max-width:1440px;margin-left:auto;margin-right:auto}" in html
       and "body.fd-canvas #content>.pg-crumb{max-width:1440px" not in html)
    ck("tables not already in a scrolling container scroll within the sheet",
       "w.className='fd-scroll'" in html and "body.fd-canvas .fd-sheet .fd-scroll{overflow-x:auto;max-width:100%}" in html)
    i_band = html.find("band.classList.add('pg-band');"); i_wrap = html.find("if(typeof _fdWrapSheet==='function') _fdWrapSheet(c, tab);   // r283")
    ck("the sheet is still wrapped only after the title band is chosen", 0 < i_band < i_wrap)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
