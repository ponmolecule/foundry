"""r232 regression gate: fee streams on loans and deposits.

Loans and deposits already execute fee_streams in the engine; r232 makes them visible and editable in the
Products workspace (the same stream workspace fee products use) and validates deposit streams.
"""
import copy, json, re, sys


def main():
    sys.path.insert(0, ".")
    from foundry.v2.validate_q import validate_errors_v2
    from foundry.v2.run_q import run_v2
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))
    base = json.load(open("foundry/fixtures/universal_template_bank.json"))
    msgs = lambda c: [e["message"] for e in validate_errors_v2(c)]
    c = copy.deepcopy(base); c["assumptions"]["deposit_products"][0]["fee_streams"] = [{"name": "Broken", "basis": "nonsense"}]
    ck("a malformed deposit stream is rejected", any("deposit_products[0].fee_streams[0]" in m for m in msgs(c)))
    st = copy.deepcopy(base["assumptions"]["lending_products"][0]["fee_streams"][0]); st["quantity_series_id"] = "fee-qty-dep-test"
    c = copy.deepcopy(base); c["assumptions"]["deposit_products"][0]["fee_streams"] = [st]
    ck("a valid deposit balance stream is accepted", not any("deposit_products" in m for m in msgs(c)))
    st2 = copy.deepcopy(st); st2["driver"]["source"] = "product_funded_flow"
    c2 = copy.deepcopy(base); c2["assumptions"]["deposit_products"][0]["fee_streams"] = [st2]
    ck("a funded-flow source on a deposit is rejected", any("deposit_products[0].fee_streams[0]" in m for m in msgs(c2)))
    R0 = run_v2(copy.deepcopy(base)); R1 = run_v2(c)
    d0 = [x for x in R0["products"] if isinstance(x, dict) and x.get("family") == "deposit"][0]["fees"][-1]
    d1 = [x for x in R1["products"] if isinstance(x, dict) and x.get("family") == "deposit"][0]["fees"][-1]
    ck("the engine executes a deposit stream (deposit fees rise)", d1 > d0, f"{d0:.2f} → {d1:.2f}")
    html = open("web/console_v2.html", encoding="utf-8").read()
    ck("Fee streams tab for loans and deposits, Per-month overrides kept for every product",
       "if(fee||x.fam==='lending'||x.fam==='deposit') tabs.push(['streams','Fee streams',ns]); if(V21) tabs.push(['overrides','Per-month overrides',null]);" in html)
    ck("one stream workspace shared by all families, resolved through owner codes",
       "function _feeStreamsSectionHtml(fam, p, base, _fi)" in html and "function _stOwner(i)" in html
       and "_feeStreamsSectionHtml(fam,p,base,1000+_li)" in html and "_feeStreamsSectionHtml(fam,p,base,2000+_di)" in html
       and len(re.findall(r"obs_exposures(?:\|\|\[\]\))?\[(?:i|fi|_fi|\$\{_fi\}|productIndex)\]", html)) == 1   # the resolver itself
       and "return (a.obs_exposures||[])[i];" in html)
    ck("a new balance stream on a loan or deposit starts on its own balance",
       '((+i>=1000)?"own_balance":"managed_notional")' in html)
    ck("the Setup fee yield is listed (read-only) with the streams, with its own card",
       "function _stSetupFeeRow(fi)" in html and "function _ipFeeYieldHtml(fi)" in html and "if(p[0]==='fy') return _ipFeeYieldHtml(+p[1]);" in html)
    ck("Guide Me stays a fee-product tool", "if(+_fi<1000){ h += `<div class=\"fld wide\" style=\"display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:4px\"><label style=\"color:#D4A65C;margin:0;flex:1\">Fee streams</label><button class=\"btn-gold\"" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
