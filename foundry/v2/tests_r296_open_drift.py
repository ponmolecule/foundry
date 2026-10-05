"""r296: changes after opening an engagement with no user interaction are drift, never unsaved work."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("the deferred engine run is covered, and never heals when the user interacted during it",
       "_wasClean=_h?_lcCleanNow():false, _seq=_w._userActSeq; try{ return await _previewInner.apply(this,arguments); } finally { if(_h&&_w._userActSeq===_seq) _lcHealDrift(_wasClean,'run'); } }" in html)
    ck("trusted user interactions are counted (input, change, paste, drop, keydown, mousedown, touchstart)",
       "['input','change','paste','drop','keydown','mousedown','touchstart'].forEach(t=>document.addEventListener(t,e=>{ if(e.isTrusted) window._userActSeq++; },true));" in html)
    ck("a settle check after every open heals changes made with no interaction since the open",
       "_lcSettleAfterOpen();   /* r296 */" in html and "if(window._userActSeq!==seq0) return;" in html and "if(LC.baseline!==base0) return;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
