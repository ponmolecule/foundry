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
    # r436: r388 (d3313274d, "isolate recovery copies") deliberately removed boot-time draft retirement/prompting.
    # r436: Boot now only discovers recovery candidates (no "Recover unsaved work" prompt), and a browser draft whose
    # r436: content is identical to a confirmed save is retired by exact content in sessionSafety.saved(), called by both save paths.
    ck("boot retires an identical recovery draft whatever its name",
       "// Discover recovery candidates only. Selection and freshness checks happen in one recovery UI." in html  # r436: boot no longer prompts
       and "Recover unsaved work from your last session?" not in html  # r436: no false recovery alarm at boot
       and "if(d&&JSON.stringify(d.config)===snapshot)localStorage.removeItem(key());" in html  # r436: identical draft retired by content
       and "sessionSafety.saved(guardSnapshot);" in html and "sessionSafety.saved(saveSnapshot);" in html)  # r436: on both save paths
    ck("the guard explains itself (changed fields listed, or never saved); no bare '(changes present)'",
       "(changes present)" not in html and "These fields changed since the last save:" in html
       and "This engagement has not been saved yet (it was recovered from your last session or newly created)." in html)
    ck("one save window: the guard's Save as opens the version dialog and continues the switch",
       "window._verSaveFromGuard=true; openVersionSave(); return;" in html
       and "document.getElementById('guard-name').value=v; guardSaveAsConfirm(); return; }" in html)
    # r436: r373 (16c9e04bc) renamed engMenuSave's parsed response from _j to savedInfo; same marker update.
    ck("the current-version marker follows saves", "if(savedInfo.slug)window._openSlug=savedInfo.slug;" in html and "if(j && j.slug) window._openSlug = j.slug;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
