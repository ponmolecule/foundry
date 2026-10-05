"""r295: the guard's change list is visible and capped; render/run drift is never unsaved work; compact window."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("change rows are light text on the dark list (they were dark-on-dark, invisible)",
       "color:#2B2B2B;margin:2px 0\">\\u2022" not in html and "#guard-list .gd-row{color:#e3e3e0;" in html)
    ck("the list is capped at 8 rows with 'and N more'", "list.slice(0,8).map(" in html and "and ${list.length-8} more" in html)
    ck("a render or engine run that changes the configuration on its own re-baselines (and is logged)",
       "function renderContent(){ const _wasClean=_lcCleanNow(); const _r=_renderContentInner.apply(this,arguments); _lcHealDrift(_wasClean," in html
       and "function refresh(){ const _wasClean=_lcCleanNow(); const _r=_refreshInner.apply(this,arguments);" in html
       and "window.__renderDrift=window.__renderDrift||[]" in html and "LC.baseline=LC._ser(cfg);" in html)
    ck("compact window with four evenly sized choices",
       "#guard-dlg{width:min(520px,94vw)!important;" in html and "#guard-actions{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
