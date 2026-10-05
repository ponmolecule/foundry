"""r285: the New Executive Summary view uses the Klaros skin (no navy/blue palette)."""
import re
import sys
from pathlib import Path


def main():
    s = Path("foundry/v2/assets/exec_view_template.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, detail)
    blue = set()
    for h in re.findall(r"#([0-9a-fA-F]{6})\b", s):
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
        if b > r + 25 and b > g + 5: blue.add("#" + h)
    for m in re.findall(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", s):
        r, g, b = map(int, m)
        if b > r + 25 and b > g + 5: blue.add("rgb(%d,%d,%d)" % (r, g, b))
    ck("no blue-dominant colour anywhere in the New view template", not blue, str(sorted(blue)))
    ck("Klaros variables: warm-white surfaces, graphite text, deep gold accents",
       "--shell:#FFFFFF; --surface:#FFFFFF;" in s and "--text:#1D1C1A;" in s and "--gold:#9A7330;" in s and "--info:#4A4741;" in s)
    ck("tables use graphite headers with the gold rule", "background:#2C2C2C;color:#FFFFFF;" in s and "border-bottom:2px solid #DFB367;" in s)
    ck("injection marker preserved", "/*__FOUNDRY_DATA_INJECTION__*/" in s)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
