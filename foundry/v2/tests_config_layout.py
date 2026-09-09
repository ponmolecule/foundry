"""Focused configuration layout regression gate."""
from __future__ import annotations
import re, sys
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
    m=re.search(r"\.cfggrid\{[^}]*grid-template-columns:([0-9.]+)fr\s+([0-9.]+)fr\s+([0-9.]+)fr", html)
    vals=tuple(map(float,m.groups())) if m else ()
    ck("Config left column is squeezed to relieve the Securities/Tax middle column",
       bool(vals) and vals[0] <= 1.10 and vals[1] >= .86 and vals[2] >= vals[1], str(vals))
    ck("Config column proportions preserve a full-width right authoring column",
       bool(vals) and abs(sum(vals)-3.0) < 1e-9 and vals[2] >= 1.0, str(vals))
    ck("Securities books use a two-tier field editor",
       '.sec-book-line-top{' in html and '.sec-book-line-bottom{' in html
       and html.count('class="sec-book-line sec-book-line-top"') == 2
       and html.count('class="sec-book-line sec-book-line-bottom"') == 2)
    ck("Both AFS and HTM use the two-tier editor",
       html.count('class="sec-book-editor" data-book-kind="AFS"') == 1
       and html.count('class="sec-book-editor" data-book-kind="HTM"') == 1)
    ck("Securities editor restores full Growth and Purchases labels",
       html.count('<span class="sec-book-label">Growth</span>') == 2
       and html.count('<span class="sec-book-label">Purchases</span>') == 2)
    ck("Securities book name is responsive rather than hard-wired to 48px",
       '.sec-book-name{width:100% !important;min-width:0 !important;max-width:none !important}' in html
       and '.sec-book-name{flex:0 0 48px' not in html)
    ck("Securities Name and Opening balance fields are compact but not squeezed",
       '.sec-book-line-top{grid-template-columns:minmax(70px,90px) minmax(108px,126px);justify-content:start}' in html)
    ck("Workforce and Opex authoring sections have explicit compact Expand/Collapse controls",
       "nieSectionSetOpen('workforce'" in html and "nieSectionSetOpen('opex'" in html
       and 'class="nie-section-toggle"' in html and 'expand to inspect or edit' in html)
    ck("Loaded Workforce/Opex sections default collapsed while empty sections remain open",
       'function _nieSectionIsOpen(key,hasRows)' in html and ': !hasRows;' in html
       and 'window._nieSectionOpen.workforce=true' in html and 'window._nieSectionOpen.opex=true' in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
