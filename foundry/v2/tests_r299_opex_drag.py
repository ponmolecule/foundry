"""r299: dragging expense categories no longer re-lays out the table (card-era pseudo-element bars removed on rows)."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("no pseudo-element drop bars on expense table rows (they became an extra cell and shifted columns)",
       "tr.opex-item-card.drop-before::before,tr.opex-item-card.drop-after::after,tr.opex-item-card::before,tr.opex-item-card::after{content:none!important;display:none!important}" in html)
    ck("rows keep the layout-neutral inset marker",
       "tr.opex-item-card.drop-before td{box-shadow:inset 0 2px 0 var(--k-gold)}" in html
       and "tr.opex-item-card.drop-after td{box-shadow:inset 0 -2px 0 var(--k-gold)}" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
