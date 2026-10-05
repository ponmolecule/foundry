"""r293: a saved engagement is a bank plus a version; names stay bank-qualified so storage keys are unchanged."""
import sys
from pathlib import Path

from foundry.store import slugify


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    store = Path("foundry/store.py").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("old and new naming styles map to the same storage key (re-saving updates, never duplicates)",
       slugify("Bank 1 \u00b7 Aggressive") == slugify("Bank 1-Aggressive") == "bank-1-aggressive")
    ck("the header shows the version as a chip; the slash separator is retired",
       'id="versionChip" class="ver-chip base"' in html and "#scenSep{display:none!important}" in html)
    ck("names are composed bank-qualified and displayed as the version (duplicate bank prefix stripped)",
       "function _engNameFor(version){ const b=_engBank(), v=_versionOf(version, b); return v ? (b ? `${b} \\u00b7 ${v}` : v) : \"\"; }" in html
       and "function _versionOf(name, bank){" in html)
    ck("Save as asks for the version in an in-app dialog (no browser prompt)",
       "function openVersionSave(){" in html and 'window.prompt("Name this engagement:"' not in html
       and "closeVersionSave(); engMenuSave(_engNameFor(v));" in html)
    ck("the unsaved-changes guard saves bank \u00b7 version",
       'const nm = _engNameFor((document.getElementById("guard-name").value || "").trim());' in html)
    ck("the saved list groups versions under their bank and marks the current one by storage key",
       "named.forEach(e=>{ const b=(e.bank_display||e.bank||'').trim()||'Other';" in html
       and "const active = window._openSlug ? e.slug === window._openSlug" in html
       and '"bank_display": cfg.get("proposed_bank") or cfg.get("client_legal_name") or ""' in store)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
