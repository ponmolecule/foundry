"""r298: the Governance data-check catalogue is collapsed by default and its heading no longer runs into its note."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("the catalogue is a details element, collapsed unless opened during the visit",
       '<details class="gq-cat"${window._govCatOpen?\' open\':\'\'} ontoggle="window._govCatOpen=this.open">' in html
       and "return h+`</details>`;" in html)
    ck("arriving at Governance from another tab collapses it again",
       "if(t==='gov'&&typeof currentTab!=='undefined'&&currentTab!=='gov') window._govCatOpen=false;" in html)
    ck("heading, count and note are separate, spaced elements (styles present)",
       '<span class="gq-cat-n">' in html and '<span class="gq-cat-note">' in html
       and ".gq-cat>summary.gq-cat-h{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 14px;" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
