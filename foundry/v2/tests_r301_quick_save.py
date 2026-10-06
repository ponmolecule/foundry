"""r301: a plain Save in the header (and Ctrl/Cmd+S) saves the open version without a dialog."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("a Save button sits in the header beside the engagement status",
       '<button id="saveBtn" type="button" class="hdr-save" style="display:none" onclick="quickSave()">Save</button>' in html)
    ck("its state follows the lifecycle (hidden empty; Save\u2026 never saved; Save when modified; Saved when clean)",
       "function _syncSaveBtn(){" in html and "if(typeof _syncSaveBtn===\"function\") _syncSaveBtn();   // r301" in html
       and "b.textContent='Saved \\u2713'; b.disabled=true;" in html)
    ck("Save writes the open bank \u00b7 version through the existing save path; never-saved opens the version dialog",
       "try{ await engMenuSave(nm); } finally { _syncSaveBtn(); }" in html
       and "if(!LC.saved || !nm || st==='NEW-UNSAVED'){ if(typeof openVersionSave==='function') openVersionSave(); return; }" in html)
    ck("Ctrl/Cmd+S saves instead of the browser's save-page",
       "if((e.ctrlKey||e.metaKey) && !e.shiftKey && !e.altKey && (e.key==='s'||e.key==='S')){ e.preventDefault(); quickSave(); }" in html)
    ck("after a save, changes are counted 'since save' (not 'since upload')",
       'const since = (!this.saved && (this.origin === "upload" || this.origin === "workbook")) ? "upload" : "save";' in html)
    ck("r302: the button refreshes on every lifecycle change (open, save, clear), not only after an edit",
       html.count('try{ if(typeof _syncSaveBtn === "function") _syncSaveBtn(); }catch(e){}') == 3)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
