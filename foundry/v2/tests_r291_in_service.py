"""r291: 'placed in service' is a digits-only box (0 = opening, up to the horizon), not a horizon-long dropdown."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("the horizon-long dropdown is gone", 'title="Placed in service" onchange' not in html and '<option value="0"${isp===0?' not in html)
    ck("a numeric box replaces it, digits only as typed",
       'class="fa-isp"' in html and 'inputmode="numeric"' in html and "oninput=\"this.value=this.value.replace(/[^0-9]/g,'')\"" in html
       and 'maxlength="${String(NP()).length}"' in html)
    ck("labelled with the forecast horizon: 'Month placed in service (max = N)' (period word follows the cadence)",
       "return `${_faIspWord()} placed in service (max = ${NP()})`;" in html and "return PPY()===12?'Month':(PPY()===4?'Quarter':'Year');" in html)
    ck("out-of-range or empty entries are refused with a message, not silently clamped",
       "ok=/^[0-9]+$/.test(t)&&(+t)<=max" in html and "is past the forecast horizon; enter 0 to ${max}." in html
       and "cfg.assumptions.fixed_assets.assets[i].in_service_period=+t; refresh();" in html)
    ck("the asset table reads the box and shows the saved value while an entry is refused",
       "select=r.querySelector('input.fa-isp')" in html and "el.classList.contains('fa-isp-bad')?el.dataset.saved:el.value" in html
       and "[[select,_faIspLabel()]" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
