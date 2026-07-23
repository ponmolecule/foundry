"""Flag / challenge test cases — one crafted config per flag, asserting it fires
with the right id and (where wired) a peer clause.

Run:  python -m foundry.tests_flags
Each case builds a minimal valid config off the TEMPLATE, then perturbs exactly
the inputs that trip one flag, so a failure points at one rule. Trigger values are
taken verbatim from challenge_q.py; Q1 market rate ~3.7% from the default rate path.

These are DETERMINISTIC config->flag tests (no DB needed). The peer-clause enrichment
is exercised separately against the local fixture where it resolves (deposit_cost).
"""
import re, json, copy, os, sys

_HTML = os.path.join(os.path.dirname(__file__), "..", "web", "console_v2.html")


def _template():
    html = open(_HTML, encoding="utf-8").read()
    return json.loads(re.search(r"const TEMPLATE = (\{.*?\});", html, re.S).group(1))


def _base():
    """A minimal, valid config with empty product books to perturb per case."""
    t = _template()
    cfg = copy.deepcopy(t)
    cfg["assumptions"]["lending_products"] = []
    cfg["assumptions"]["deposit_products"] = []
    return cfg


def _lend(**kw):
    d = {"name": "TestLoan", "opening_balance": 50_000_000.0, "rate_type": "fixed",
         "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0,
         "originations_q": 0.0, "orig_growth_q": 0.0, "runoff_q": 0.0,
         "charge_off_ann": 0.01, "provision_rate_ann": 0.01, "reserve_rate_pct_bal": 0.01,
         "measurement": "amortized", "call_report_line": "loanCommercial", "yield_ann": 0.06}
    d.update(kw)
    return d


def _dep(**kw):
    d = {"name": "TestDep", "opening_balance": 50_000_000.0, "rate_type": "fixed",
         "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0,
         "growth_q": 0.02, "runoff_q": 0.0, "call_report_line": "depTime",
         "rate_paid_ann": 0.015}
    d.update(kw)
    return d


# ---- one case per flag: (case id, description, config-builder, expected flag id) ----
def _cases():
    cases = []

    def add(name, desc, cfg, expect):
        cases.append((name, desc, cfg, expect))

    # BAND-CO-HI: commercial charge-off above 3.0% band high
    c = _base(); c["assumptions"]["lending_products"] = [_lend(charge_off_ann=0.05)]
    add("BAND-CO-HI", "commercial 5% charge-off > 3.0% band high", c, "BAND-CO-HI")

    # BAND-CO-LO: commercial charge-off below 0.05% band low, with a balance
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(charge_off_ann=0.0001, provision_rate_ann=0.0, reserve_rate_pct_bal=0.0)]
    add("BAND-CO-LO", "commercial 0.01% charge-off < 0.05% band low", c, "BAND-CO-LO")

    # PRICE-USURY: yield >= 25%
    c = _base(); c["assumptions"]["lending_products"] = [_lend(yield_ann=0.28, charge_off_ann=0.01)]
    add("PRICE-USURY", "28% yield >= 25% usury bar", c, "PRICE-USURY")

    # PRICE-LOWYIELD: 0 < yield < 2%
    c = _base(); c["assumptions"]["lending_products"] = [_lend(yield_ann=0.015)]
    add("PRICE-LOWYIELD", "1.5% yield below any funding cost", c, "PRICE-LOWYIELD")

    # RES-THIN: reserve rate < charge_off/2  (co=0.06 -> need rr < 0.03)
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(charge_off_ann=0.06, reserve_rate_pct_bal=0.01, provision_rate_ann=0.06)]
    add("RES-THIN", "1% reserve vs 6% charge-off (thin)", c, "RES-THIN")

    # PROV-BELOW-CO: provision < charge_off
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(charge_off_ann=0.02, provision_rate_ann=0.005, reserve_rate_pct_bal=0.02)]
    add("PROV-BELOW-CO", "0.5% provision below 2% charge-off", c, "PROV-BELOW-CO")

    # GOS-MARGIN-NEG: negative gain-on-sale (mortgage-banking, mortgage line)
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(call_report_line="loanMortgage", charge_off_ann=0.005,
              mortgage_banking={"sale_pct_of_orig": 0.5, "gain_on_sale_margin": -0.01,
                                "warehouse_hold_q": 1, "servicing_retained_pct": 0.0})]
    add("GOS-MARGIN-NEG", "selling loans at a loss (negative GOS)", c, "GOS-MARGIN-NEG")

    # GOS-MARGIN-HI: gain-on-sale > 4%
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(call_report_line="loanMortgage", charge_off_ann=0.005,
              mortgage_banking={"sale_pct_of_orig": 0.5, "gain_on_sale_margin": 0.06,
                                "warehouse_hold_q": 1, "servicing_retained_pct": 0.0})]
    add("GOS-MARGIN-HI", "6% gain-on-sale above secondary-market norm", c, "GOS-MARGIN-HI")

    # GOS-WAREHOUSE: warehouse hold >= 3 quarters
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(call_report_line="loanMortgage", charge_off_ann=0.005,
              mortgage_banking={"sale_pct_of_orig": 0.5, "gain_on_sale_margin": 0.02,
                                "warehouse_hold_q": 4, "servicing_retained_pct": 0.0})]
    add("GOS-WAREHOUSE", "4-quarter warehouse period is long", c, "GOS-WAREHOUSE")

    # MSR-CAP: MSR cap rate > 2% of UPB
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(call_report_line="loanMortgage", charge_off_ann=0.005,
              mortgage_banking={"sale_pct_of_orig": 0.5, "gain_on_sale_margin": 0.02,
                                "warehouse_hold_q": 1, "servicing_retained_pct": 0.5,
                                "msr_cap_rate_pct_upb": 0.03, "servicing_fee_bp_ann": 25})]
    add("MSR-CAP", "3% MSR cap rate is rich vs ~0.8-1.5%", c, "MSR-CAP")

    # MSR-FEE: servicing fee outside 12.5-50bp
    c = _base(); c["assumptions"]["lending_products"] = [
        _lend(call_report_line="loanMortgage", charge_off_ann=0.005,
              mortgage_banking={"sale_pct_of_orig": 0.5, "gain_on_sale_margin": 0.02,
                                "warehouse_hold_q": 1, "servicing_retained_pct": 0.5,
                                "msr_cap_rate_pct_upb": 0.01, "servicing_fee_bp_ann": 75})]
    add("MSR-FEE", "75bp servicing fee outside 12.5-50bp", c, "MSR-FEE")

    # FUND-HOT: deposit rate > 5.5%
    c = _base(); c["assumptions"]["deposit_products"] = [_dep(rate_paid_ann=0.062)]
    c["assumptions"]["lending_products"] = [_lend()]
    add("FUND-HOT", "6.2% deposit rate is hot money", c, "FUND-HOT")

    # FUND-DDA: DDA line paying > 2%
    c = _base(); c["assumptions"]["deposit_products"] = [
        _dep(call_report_line="depDDA", rate_paid_ann=0.03)]
    c["assumptions"]["lending_products"] = [_lend()]
    add("FUND-DDA", "3% on transaction accounts is unusual", c, "FUND-DDA")

    # FUND-GROWTH: deposit growth > 25%/quarter
    c = _base(); c["assumptions"]["deposit_products"] = [_dep(growth_q=0.30, rate_paid_ann=0.02)]
    c["assumptions"]["lending_products"] = [_lend()]
    add("FUND-GROWTH", "30%/qtr deposit growth is aggressive", c, "FUND-GROWTH")

    # SPREAD-VIAB: blended loan yield - deposit cost < 1%
    c = _base()
    c["assumptions"]["lending_products"] = [_lend(yield_ann=0.035, charge_off_ann=0.005)]
    c["assumptions"]["deposit_products"] = [_dep(rate_paid_ann=0.030, growth_q=0.02)]
    add("SPREAD-VIAB", "0.5% blended spread can't cover opex", c, "SPREAD-VIAB")

    # COUPLED-01: fast growth (>8%) AND cheap (>75bp below ~3.7% mkt)
    c = _base()
    c["assumptions"]["lending_products"] = [_lend()]
    c["assumptions"]["deposit_products"] = [_dep(growth_q=0.14, rate_paid_ann=0.006)]
    add("COUPLED-01", "13%+ growth AND cost far below market (contradiction)", c, "COUPLED-01")

    # COUPLED-02: high yield (>12%) AND charge-off below band low
    c = _base()
    c["assumptions"]["lending_products"] = [
        _lend(yield_ann=0.15, charge_off_ann=0.0002, provision_rate_ann=0.0002,
              reserve_rate_pct_bal=0.0002)]
    add("COUPLED-02", "15% risk-based yield but near-zero losses", c, "COUPLED-02")

    return cases


def run():
    from foundry.v2.challenge_q import challenge_config
    from foundry.v2.peer_calibration import peer_annotate
    cases = _cases()
    passed, failed = 0, 0
    print(f"Flag test cases ({len(cases)} flags)\n" + "=" * 70)
    for name, desc, cfg, expect in cases:
        flags = challenge_config(cfg)
        ids = [f["id"] for f in flags]
        ok = expect in ids
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {name:16} {desc}")
        if ok:
            passed += 1
            hit = next(f for f in flags if f["id"] == expect)
            # show the message so you can eyeball the wording
            print(f"        \"{hit['text'][:110]}{'...' if len(hit['text'])>110 else ''}\"")
        else:
            failed += 1
            print(f"        EXPECTED {expect}, GOT {ids}")
    print("=" * 70)

    # peer-clause enrichment against the local fixture (deposit_cost resolves)
    print("\nPeer-clause enrichment (local fixture: deposit_cost)\n" + "=" * 70)
    os.environ["FOUNDRY_ALLOW_FIXTURE_BANDS"] = "1"
    c = _base(); c["assumptions"]["deposit_products"] = [_dep(rate_paid_ann=0.062, growth_q=0.02)]
    c["assumptions"]["lending_products"] = [_lend()]
    ann = peer_annotate(challenge_config(c), c, cohort="200M_500M")
    fh = next((f for f in ann if f["id"] == "FUND-HOT"), None)
    if fh and "peer" in fh:
        print(f"[PASS] FUND-HOT enriched: sits {fh['peer']['position']} "
              f"(metric={fh['peer']['band_metric']}, vintage={fh['peer']['vintage']}, n={fh['peer']['n']})")
        print(f"        \"...{fh['text'].split('. ')[-1].strip()}\"")
        passed += 1
    else:
        print("[WARN] FUND-HOT not enriched — fixture may be off; peer clause needs the "
              "opt-in fixture locally or the live DB in prod")

    print("=" * 70)
    print(f"{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
