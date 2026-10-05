"""r294: no guard for nothing; the guard says why; one save window; the current marker follows saves."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("a never-saved configuration identical to a saved engagement raises no guard (re-marked clean)",
       'if(hasUnsavedWork() && LC.state()==="NEW-UNSAVED" && await _identicalToSaved())' in html
       and "async function _identicalToSaved(){" in html and "LC.land('open', e.name||e.slug); window._openSlug=e.slug;" in html)
    ck("boot retires an identical recovery draft whatever its name",
       'const candidates = (js.engagements||[]).filter(e => !_isRecoverySlug(e.slug)).slice(0,40)' in html)
    ck("the guard explains itself (changed fields listed, or never saved); no bare '(changes present)'",
       "(changes present)" not in html and "These fields changed since the last save:" in html
       and "This engagement has not been saved yet (it was recovered from your last session or newly created)." in html)
    ck("one save window: the guard's Save as opens the version dialog and continues the switch",
       "window._verSaveFromGuard=true; openVersionSave(); return;" in html
       and "document.getElementById('guard-name').value=v; guardSaveAsConfirm(); return; }" in html)
    ck("the current-version marker follows saves", "if(_j && _j.slug) window._openSlug = _j.slug;" in html and "if(j && j.slug) window._openSlug = j.slug;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
