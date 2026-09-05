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
    ck("Operating Expense configuration column is wider than Securities", bool(vals) and vals[2] > vals[1], str(vals))
    ck("Securities book-name control is compact for AFS/HTM labels",
       '.sec-book-name{flex:0 0 48px !important;min-width:48px !important;max-width:48px !important}' in html)
    ck("Both AFS and HTM book rows use the compact name control",
       html.count('<input class="sec-book-name"') == 2)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
