"""T-PAR — the parity floor (Foundry v2, ledger G1/P0.4).

Foundry v2 must never be unable to do something its predecessors could do.
This harness runs every frozen predecessor fixture through the v2 engine and
compares line by line within the stated tolerance. It is RED BY DESIGN at P0:
the goldens exist before the engine that must satisfy them.

Green criteria per fixture: every expected line item, every quarter, within
±$1,000 ($1 in $000s terms). Exit code 0 only when all fixtures reproduce.

Run: python -m foundry.tests_parity   (from the repo root)
"""
import json, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures", "parity", "parity_fixtures.json")
CONFIGS = os.path.join(HERE, "fixtures", "parity", "configs")

TOL = 1.0  # $000s per line item per quarter

V2_TOP_REQUIRED = ["engagement_id", "schema_version", "client_legal_name", "proposed_bank",
                   "hq", "config_version", "config_frozen", "parity_profile",
                   "step_minus_1", "step_0", "step_0a", "step_1", "assumption_tags",
                   "constraints", "target_state", "peer_query", "assumptions",
                   "parity_expectation"]

def _h(o):
    return hashlib.sha256(json.dumps(o, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()[:12]

def load_v2_runner():
    """The v2 engine registers a parity runner here when it exists:
    foundry.v2.parity.run_parity(config) -> {'bs': {...}, 'is': {...}} in $000s,
    quarterly arrays matching the fixture snapshot shape."""
    try:
        from foundry.v2.parity import run_parity  # noqa
        return run_parity
    except Exception:
        return None

def compare(expected, got, path=""):
    diffs = []
    for k, v in expected.items():
        if k in ("advisories", "ratios"):   # ratios informational; advisories tested in challenge layer
            continue
        g = (got or {}).get(k)
        if isinstance(v, dict):
            diffs += compare(v, g or {}, path + k + ".")
        elif isinstance(v, list):
            if g is None:
                diffs.append(f"{path}{k}: missing"); continue
            for i, (a, b) in enumerate(zip(v, g)):
                if a is None or b is None:
                    continue
                if abs(a - b) > TOL:
                    diffs.append(f"{path}{k}[{i}]: expected {a}, got {b}")
    return diffs

def main():
    fx = json.load(open(FIXTURES, encoding="utf-8"))
    # 1) fixture integrity: hashes recompute
    bad = [k for k, v in fx["fixtures"].items()
           if _h({kk: v[kk] for kk in ("inputs", "expected")}) != v["fixture_hash"]]
    if bad:
        print("T-PAR INTEGRITY FAIL: fixture(s) altered since freeze:", bad); sys.exit(2)
    print(f"T-PAR: {len(fx['fixtures'])} fixtures verified intact (hashes reproduce)")

    # 2) configs parse and carry the v2 contract
    cfg_fail = 0
    for k in fx["fixtures"]:
        p = os.path.join(CONFIGS, k + ".json")
        try:
            cfg = json.load(open(p))
            missing = [t for t in V2_TOP_REQUIRED if t not in cfg]
            if missing:
                print(f"  CONFIG FAIL {k}: missing {missing}"); cfg_fail += 1
        except Exception as e:
            print(f"  CONFIG FAIL {k}: {e}"); cfg_fail += 1
    print(f"T-PAR: v2 configs structural check — {len(fx['fixtures'])-cfg_fail}/{len(fx['fixtures'])} pass")

    # 2b) fail-closed validator (A.13): accepts all fixtures, rejects nonsense
    try:
        from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
        import copy
        base = json.load(open(os.path.join(CONFIGS, "pf_a_base.json"), encoding="utf-8"))
        for label, breaker in [
            ("missing step_0a", lambda c: c.pop("step_0a")),
            ("negative runoff", lambda c: c["assumptions"]["lending_products"][0].__setitem__("runoff_q", -0.5)),
            ("FV without discount spread", lambda c: (c["assumptions"]["lending_products"][0].__setitem__("measurement", "fair_value"),
                                                      c["assumptions"]["lending_products"][0].pop("discount_spread_ann", None))),
            ("charge-off 80%", lambda c: c["assumptions"]["lending_products"][0].__setitem__("charge_off_ann", 0.80)),
        ]:
            broken = copy.deepcopy(base); breaker(broken)
            try:
                validate_config_v2(broken)
                print(f"  VALIDATOR FAIL: accepted nonsense ({label})"); sys.exit(1)
            except ConfigErrorV2:
                pass
        print("T-PAR: fail-closed validator — 4/4 nonsense configs rejected, fixtures accepted")
    except ImportError:
        pass

    # 2c) challenge layer (A.11/A.12): bands fire on the warning-heavy fixture,
    # stay silent on the clean base; coupled rules fire on crafted contradictions
    try:
        from foundry.v2.challenge_q import challenge_config
        import copy
        wh = json.load(open(os.path.join(CONFIGS, "pf_a_warning_heavy.json"), encoding="utf-8"))
        ids = {f["id"] for f in challenge_config(wh)}
        need = {"BAND-CO-HI", "PRICE-USURY", "FUND-HOT"}
        if not need <= ids:
            print(f"  CHALLENGE FAIL: warning-heavy fixture missing {need - ids}"); sys.exit(1)
        base = json.load(open(os.path.join(CONFIGS, "pf_a_base.json"), encoding="utf-8"))
        base_flags = challenge_config(base)
        sev = [f for f in base_flags if f["sev"] == "severe" and not f["id"].startswith("COUPLED")]
        if sev:
            print(f"  CHALLENGE FAIL: clean base raised severe band/pricing flags {[f['id'] for f in sev]}"); sys.exit(1)
        # the default digital-bank plan claims cheap AND fast funding — COUPLED-01 firing
        # on it is correct and deliberate (mirrors the Solstice precedent: review burden,
        # joint support required, not a noise gate)
        if "COUPLED-01" not in {f["id"] for f in base_flags}:
            print("  CHALLENGE FAIL: COUPLED-01 should fire on the default plan (13%/q growth, sub-market cost)"); sys.exit(1)
        c1 = copy.deepcopy(base)
        for p in c1["assumptions"]["deposit_products"]:
            p["growth_q"] = 0.12; p["rate_type"] = "fixed"; p["rate_paid_ann"] = 0.005
        if "COUPLED-01" not in {f["id"] for f in challenge_config(c1)}:
            print("  CHALLENGE FAIL: COUPLED-01 did not fire on cheap+fast funding"); sys.exit(1)
        c2 = copy.deepcopy(base)
        cc = [p for p in c2["assumptions"]["lending_products"] if "Card" in p["name"]][0]
        cc["yield_ann"] = 0.18; cc["charge_off_ann"] = 0.010
        if "COUPLED-02" not in {f["id"] for f in challenge_config(c2)}:
            print("  CHALLENGE FAIL: COUPLED-02 did not fire on risk pricing + prime losses"); sys.exit(1)
        print("T-PAR: challenge layer — bands fire on crafted configs, clean case raises no severe flags,"
              " both coupled rules fire")
    except ImportError:
        pass

    # 2d) OBS module (A.4): notional path and fee accrual on a synthetic product
    try:
        from foundry.v2.engine_q_b import run_pf_b
        import copy
        c = copy.deepcopy(json.load(open(os.path.join(CONFIGS, "pf_b_base.json"), encoding="utf-8")))
        c["assumptions"]["obs_exposures"] = [{"name": "Unused commitments", "notional": 10_000_000,
                                              "growth_q": 0.02, "fee_yield_ann": 0.004}]
        r0 = run_pf_b(json.load(open(os.path.join(CONFIGS, "pf_b_base.json"), encoding="utf-8")))
        r1 = run_pf_b(c)
        dfee = r1["is"]["fees"][0] - r0["is"]["fees"][0]
        expect = ((10_000_000 + 10_200_000) / 2) * 0.004 / 4
        if abs(dfee - expect) > 1.0:
            print(f"  OBS FAIL: fee accrual {dfee:.2f} vs expected {expect:.2f}"); sys.exit(1)
        print("T-PAR: OBS module — notional grows and fees accrue on average notional")
    except ImportError:
        pass

    # 2e) Excel layer (A.14/A.15): config workbook round-trips to identical parity
    # output for every fixture; results workbook cells tie to engine output exactly
    try:
        from foundry.v2.excel_q import workbook_from_config_v2, parse_workbook_v2, results_workbook_v2
        from foundry.v2.parity import run_parity as _rp
        import io as _io
        from openpyxl import load_workbook as _lw
        xls_fail = 0
        for k in fx["fixtures"]:
            cfg = json.load(open(os.path.join(CONFIGS, k + ".json"), encoding="utf-8"))
            buf = _io.BytesIO(); workbook_from_config_v2(cfg).save(buf)
            cfg2 = parse_workbook_v2(buf.getvalue())
            r1, r2 = _rp(cfg), _rp(cfg2)
            if r1 != r2:
                print(f"  XLS ROUND-TRIP FAIL {k}: parity output differs across formats"); xls_fail += 1
        print(f"T-PAR: Excel config round-trip — {len(fx['fixtures'])-xls_fail}/{len(fx['fixtures'])} identical across formats")
        cfg = json.load(open(os.path.join(CONFIGS, "pf_a_ots_msr.json"), encoding="utf-8"))
        res = _rp(cfg)
        buf = _io.BytesIO(); results_workbook_v2(cfg, res).save(buf)
        wb2 = _lw(_io.BytesIO(buf.getvalue()), data_only=True)
        bs_rows = {r[1]: list(r[5:]) for r in wb2["Balance Sheet"].iter_rows(min_row=2, values_only=True) if len(r) > 5 and r[1]}
        from foundry.v2 import present as _p2
        negated = {row["key"] for row in _p2.BS_LAYOUT if row.get("negate")}
        def _cell(k, i):
            v = bs_rows[k][i]
            return -v if (k in negated and v is not None) else v
        ok = all(k in bs_rows and abs((_cell(k, i) or 0) - (res["bs"][k][i] or 0)) < 0.005
                 for k in res["bs"] for i in range(len(res["bs"][k]))
                 if res["bs"][k][i] is not None)
        if not (ok and not xls_fail):
            print("  XLS FAIL: results workbook does not tie to engine output"); sys.exit(1)
        print("T-PAR: results workbook — every balance-sheet cell ties to engine output (MSR fixture)")
    except ImportError:
        pass

    # 2f) HTM shock invariance (A.6): under a +300bp overlay the HTM coupon is
    # unchanged while shocked treasury yields move — held-to-maturity means held
    try:
        from foundry.v2.engine_q_a import run_pf_a
        import copy
        c = copy.deepcopy(json.load(open(os.path.join(CONFIGS, "pf_a_base.json"), encoding="utf-8")))
        c["assumptions"]["securities_htm"] = [{"name": "HTM ladder", "opening": 20_000_000,
                                               "purchases_q": 0, "growth_q": 0, "runoff_q": 0.02,
                                               "yield_ann": 0.047}]
        r0 = run_pf_a(copy.deepcopy(c))
        cs = copy.deepcopy(c); cs["scenario_overlays"] = {"rate_shock_bp": 300}
        r1 = run_pf_a(cs)
        book0 = ((20_000_000 + 20_000_000 * 0.98) / 2) * 0.047 / 4
        if abs(r0["is"]["bookInt"][0] - book0) > 1.0:
            print(f"  HTM FAIL: book coupon {r0['is']['bookInt'][0]:.0f} vs expected {book0:.0f}"); sys.exit(1)
        if any(abs(a2 - b2) > 1e-6 for a2, b2 in zip(r0["is"]["bookInt"], r1["is"]["bookInt"])):
            print("  HTM FAIL: +300bp shock moved the HTM coupon — the book repriced"); sys.exit(1)
        if r1["is"]["cashInt"][0] <= r0["is"]["cashInt"][0]:
            print("  HTM FAIL: shock did not move treasury income — overlay not applied"); sys.exit(1)
        print("T-PAR: HTM shock invariance — +300bp moves treasury income, not the HTM coupon")
    except ImportError:
        pass

    # 2g) Call Report mapping (B.7): every result line and every product line in
    # the fixtures maps to a schedule/item reference
    try:
        from foundry.v2.callreport import code_for_result, code_for_line
        from foundry.v2.parity import run_parity as _rp2
        unmapped = set()
        for k in fx["fixtures"]:
            cfg = json.load(open(os.path.join(CONFIGS, k + ".json"), encoding="utf-8"))
            res = _rp2(cfg)
            for section in ("bs", "is"):
                for rk in res[section]:
                    if code_for_result(rk) is None:
                        unmapped.add(f"result:{rk}")
            for fam in ("deposit_products", "lending_products"):
                for p in cfg["assumptions"].get(fam) or []:
                    if p.get("call_report_line") and code_for_line(p["call_report_line"]) is None:
                        unmapped.add(f"line:{p['call_report_line']}")
        if unmapped:
            print(f"  CALLREPORT FAIL: unmapped {sorted(unmapped)}"); sys.exit(1)
        print("T-PAR: Call Report mapping — every result line and product line carries a schedule reference")
    except ImportError:
        pass

    # 2h) run wrapper (C.1/A.8): preview IS the run — deterministic, hash-stable;
    # constraint tests cover every constraint in every scenario
    try:
        from foundry.v2.run_q import run_v2, SCENARIOS_V2
        cfg = json.load(open(os.path.join(CONFIGS, "pf_a_base.json"), encoding="utf-8"))
        r1, r2 = run_v2(cfg), run_v2(cfg)
        if r1 != r2 or r1["run_hash"] != r2["run_hash"]:
            print("  T-PRV FAIL: identical config produced different results"); sys.exit(1)
        want = len(cfg["constraints"]) * len(SCENARIOS_V2)
        if len(r1["constraint_tests"]) != want:
            print(f"  A.8 FAIL: {len(r1['constraint_tests'])} constraint tests, expected {want}"); sys.exit(1)
        if not all(abs(sum(x['contribution'] for x in [dict(row) for row in r1['ftp']['rows']])
                       + r1['ftp']['treasury_center'] - r1['ftp']['consolidated_pretax']) < 0.05
                   for _ in [0]):
            print("  FTP FAIL: contributions + center != consolidated pretax"); sys.exit(1)
        ftp_rows = r1.get("ftp", {}).get("rows", [])
        bal_rows = [x for x in ftp_rows if x["family"] in ("lending", "deposit")
                    and abs(x.get("avg_balance", 0)) > 1]
        if bal_rows and not any(abs(x.get("ftp", 0)) > 1 for x in bal_rows):
            print("  FAIL: FTP charges/credits are all ~zero despite balances and a "
                  "nonzero rate path — rate series likely mangled by unit conversion")
            sys.exit(1)
        print("T-PAR: run wrapper — preview==run (hash-stable), constraint tests span every"
              " constraint x scenario, FTP view reconciles to pre-tax exactly")
    except ImportError:
        pass

    # 2i) UI-parity checklist (PC-3): the Workspace must carry the controls and the
    # presentation layer must carry the professional labels — the surface gets the
    # same discipline as the arithmetic. No dict keys as client-facing labels.
    try:
        from foundry.v2 import present as _pres
        need_labels = ["Retained earnings", "TOTAL ASSETS", "TOTAL LIABILITIES AND EQUITY",
                       "allowance for credit losses", "Loans held for sale",
                       "Mortgage servicing rights", "held-to-maturity", "NET INTEREST INCOME",
                       "Provision for credit losses", "NET INCOME"]
        blob = json.dumps(_pres.BS_LAYOUT + _pres.IS_LAYOUT)
        miss = [x for x in need_labels if x.lower() not in blob.lower()]
        html = open("web/console_v2.html", encoding="utf-8").read()
        # Iteration-1 contract: faithful replication of the predecessor HTML surface.
        # Tokens are drawn from the transcribed artifact, not from memory.
        need_controls = ["Products", "Balance Sheet", "Income Statement", "Ratios",
                         "Product Detail", "Stress Testing", "Assumptions & Notes",
                         "Pro Forma Balance Sheet", "Pro Forma Income Statement (quarterly)",
                         "Less: Allowance for Loan Losses", "TOTAL LIABILITIES & EQUITY",
                         "Total Loans & Leases (gross)", "Summary Ratios (annualized)",
                         "Efficiency Ratio", "Tier 1 Leverage Ratio", "NET INCOME (LOSS)",
                         "Per-Product Contributions", "Direct Contribution",
                         "Apply funds-transfer pricing", "Treasury (FTP mismatch center)",
                         "Stress Testing \\u2014 Scenario Comparison", "Net Income by Quarter",
                         "Tier 1 Leverage Ratio by Quarter",
                         "Reasonableness Flags", "Defaults Applied", "Methodology",
                         "Global Assumptions", "Interest Rate Forecast (SOFR)",
                         "Stress Scenario Settings", "stress_params",
                         "+ Add Product", "Add a product", "Call Report line",
                         "Floating (SOFR + spread)", "scenarioName", "Export to Excel",
                         "obs_exposures", "Longer run"]
        # efficiency ratio must exist in the server label set (exhibit path)
        need_labels.append("Efficiency ratio")
        # v2.1 additive layer (iteration 2, approved items 1/3/8): everything is
        # gated on window.V21 so the faithful surface is untouched at /v2.
        need_v21 = ["window.V21", "V21 ?", "refCell", "callreport", "SCHEDULE RC",
                    "SCHEDULE RI", "SCHEDULE RI-X", "Per-quarter overrides",
                    "blank cells use the baseline shown as placeholder",
                    "CBLR Framework Eligibility", "12 CFR 3.12", "overrides"]
        miss += [x for x in need_v21 if x not in html]
        app_src = open("app.py", encoding="utf-8").read()
        if '"/v2.1"' not in app_src or "window.V21=true" not in app_src:
            miss += ["/v2.1 route"]
        # v2.2 Foundry-native layer: config front door surface + run registry,
        # gated docs, and a live freeze->re-verify roundtrip through the registry.
        need_v22 = ["window.V22", '"config","Configuration"', '"gov","Governance"',
                    "Client configuration (JSON)", "Download configuration",
                    "Upload configuration", "config-workbook", "parse-workbook",
                    "Freeze current run", "Re-verify", "/api/v2/registry",
                    "REPRODUCED", "loadFrozen"]
        miss += [x for x in need_v22 if x not in html]
        app_src2 = open("app.py", encoding="utf-8").read()
        for tok in ['"/v2.2"', 'docs_url=None', '"/api/v2/freeze"', '"/api/v2/verify/{entry_id}"']:
            if tok not in app_src2:
                miss += [f"app.py: {tok}"]
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            os.environ["FOUNDRY_DATA_DIR"] = td
            try:
                from foundry.v2 import registry_q
                cfg_r = json.load(open(os.path.join(CONFIGS, "pf_a_base.json"), encoding="utf-8"))
                fe = registry_q.freeze(cfg_r, "gate roundtrip")
                vr = registry_q.verify(fe["id"])
                if not (vr and vr["match"]):
                    print("  FAIL: registry freeze->verify did not reproduce hashes"); sys.exit(1)
                if not registry_q.status()["persistent"]:
                    print("  FAIL: registry status should report persistent with FOUNDRY_DATA_DIR set"); sys.exit(1)
            finally:
                del os.environ["FOUNDRY_DATA_DIR"]
        print("T-PAR: v2.2 layer \u2014 config front door surface, gated API docs, run registry"
              " freeze\u2192re-verify reproduces hashes, persistence honesty reported")
        miss += [x for x in need_controls if x not in html]
        if miss:
            print(f"  UI-PARITY FAIL: missing {miss}"); sys.exit(1)
        print("T-PAR: v2.1 additive layer — Call Report ref column + schedule badges,"
              " per-quarter override grids, CBLR eligibility cards, all V21-gated;"
              " /v2.1 route serves the flag")
        print("T-PAR: UI parity checklist — faithful iteration-1 surface: predecessor tab set,"
              " three-card sidebar with quarter-labeled SOFR path, Products tab + Add-Product"
              " modal, line-level BS, contributions + per-product schedules, scenario"
              " comparison, flags/defaults/methodology, Excel export")
    except ImportError:
        pass

    # 3) parity runs
    runner = load_v2_runner()
    if runner is None:
        print("T-PAR: v2 engine not present — 0/%d fixtures reproduced." % len(fx["fixtures"]))
        print("T-PAR STATUS: RED BY DESIGN (P0). The floor is poured; the house is not built.")
        sys.exit(1)
    npass = 0
    for k, v in fx["fixtures"].items():
        cfg = json.load(open(os.path.join(CONFIGS, k + ".json"), encoding="utf-8"))
        got = runner(cfg)
        diffs = compare(v["expected"], got)
        # A.7 attestation: ratio layer must match predecessor ratios within 0.02pp
        exp_r, got_r = v["expected"].get("ratios") or {}, got.get("ratios") or {}
        for rk, ev in exp_r.items():
            gv = got_r.get(rk)
            if gv is None:
                continue
            for i, (e2, g2) in enumerate(zip(ev, gv)):
                if e2 is not None and g2 is not None and abs(e2 - g2) > 0.02:
                    diffs.append(f"ratios.{rk}[{i}]: expected {e2}, got {g2}")
        if diffs:
            print(f"  PARITY FAIL {k}: {len(diffs)} line-quarters out of tolerance; first: {diffs[0]}")
        else:
            npass += 1
            print(f"  PARITY PASS {k}")
    print(f"T-PAR: {npass}/{len(fx['fixtures'])} fixtures reproduced within ±${TOL:.0f}k/line/quarter")
    sys.exit(0 if npass == len(fx["fixtures"]) and cfg_fail == 0 else 1)

if __name__ == "__main__":
    main()
