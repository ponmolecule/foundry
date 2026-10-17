"""r340: Securities & AOCI component editors use the form kit; runs the browser-free renderer test."""
import subprocess
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name, detail)
    ck("Interest-bearing balances render through the form kit", "h+=_bcEditorHtmlFk();" in html and "h+=_bcEditorHtml();" not in html)
    ck("Other assets render through the form kit", "h += _oaEditorHtmlFk();" in html)
    ck("Other liabilities render through the form kit", "h += _olEditorHtmlFk(A4,_olm,_olModeNow);" in html)
    ck("legacy band decoration skips form-kit panels", "if(ol&&!ol.classList.contains('fk-panel')&&!ol.querySelector('.fsx-band')){" in html)
    ck("schedule drawer carries a native Close for the paste-surface controller", ">Close</button></div></div>`;" in html and "fk-drawer" in html)
    ck("styles are scoped to the Securities card", html.count("#content #card-sec .fk-panel") > 50)
    r = subprocess.run(["node", "web/tests_r340_form_kit.cjs"], capture_output=True, text=True)
    ck("renderer test (node)", r.returncode == 0, (r.stdout + r.stderr)[-400:])
    ck("build stamp", Path("BUILD_STAMP").read_text().strip() == "foundry-r340-securities-form-redesign")
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
