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

    ck("login hero content is shifted materially upward from its prior centered position",
       'min-height:calc(100vh - 190px);transform:translateY(-9rem)' in html)
    ck("superfluous HTM-designation counter is removed",
       "HTM designated" not in html and "Books included" not in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
