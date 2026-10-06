"""r303: Tiered (piecewise) driver terms get Browse / search and a per-term series preview, like Formula."""
import sys
from pathlib import Path


def main():
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    p = f = 0
    def ck(name, cond):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name)
        else: f += 1; print("  FAIL ", name)
    ck("each Tiered term has a Browse / search link", 'onclick="browseTieredSources(${i},${j},${k});return false">Browse / search</a>' in html)
    ck("the catalogue picker has a Tiered mode limited to the sources Tiered accepts",
       "consumer==='opex_tiered'?!!(allowedIds&&allowedIds.has(x.series_id))" in html and "async function browseTieredSources(i,j,k){" in html
       and "map.set('bank.total_assets',o.value)" in html)
    ck("each term shows its series preview (AUC shared preview; balance quantity and total assets from the run)",
       "${_tieredTermPreviewHtml(t)}" in html and "function _tieredTermPreviewHtml(t){" in html
       and "driver:'customer_acquisition_auc',series_id:t.series_id" in html and "Fee-stream balance quantity" in html and "Bank \\u203a Total assets" in html)
    ck("an empty preview says why (no run yet, or the run failed / was rejected)",
       "function _pwNoRunNote(){" in html and "lastRunFailure" in html[html.index("function _pwNoRunNote(){"):html.index("function _pwNoRunNote(){")+500])
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
