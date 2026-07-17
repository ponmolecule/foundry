"""Protocol harness — runs the Phase A/B test set from
GPT_Claude_consolidated_v2 and prints a scored report.

  python -m foundry.tests_protocol
"""
import copy, json, math, os, sys
from . import chassis, run as runner
from .client_solstice import CLIENT as SOLSTICE
from .client_blackland import CLIENT as BLACKLAND

GOLDENS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "goldens.json")))
RESULTS = []

def check(tid, name, ok, detail=""):
    RESULTS.append((tid, name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{tid}] {name}" + (f" — {detail}" if detail else ""))

# ---------------- T2: golden regression ----------------
def t2():
    print("T2 golden-run regression")
    r = runner.run(copy.deepcopy(SOLSTICE))
    check("T2", "Solstice canonical hash reproduces golden v5",
          r["run_hash"] == GOLDENS["solstice_golden_v5"],
          f"{r['run_hash']} vs {GOLDENS['solstice_golden_v5']}")
    b = runner.run(copy.deepcopy(BLACKLAND))
    check("T2", "Blackland canonical hash reproduces golden v2",
          b["run_hash"] == GOLDENS["blackland_golden_v2"],
          f"{b['run_hash']} vs {GOLDENS['blackland_golden_v2']}")

# ---------------- T3: metamorphic with mechanism-exercised reporting ----------------
def _summ(cfg, ov=None, cap=None):
    c = copy.deepcopy(cfg)
    if ov: c["assumptions"].update(ov)
    if cap: c["target_state"]["initial_capital"] = cap
    return chassis.summarize(chassis.project(c), c)

def t3():
    print("T3 metamorphic suite (direct-mechanics layer; balances/behavior fixed)")
    for cfg, tag in ((SOLSTICE, "solstice"), (BLACKLAND, "blackland")):
        base = _summ(cfg)
        cases = [
            ("deposit rate +100bp -> cum NI must not improve",
             {"savings_rate": cfg["assumptions"]["savings_rate"] + 0.01},
             "cost_of_funds", lambda s: s["cum_net_income"] <= base["cum_net_income"],
             lambda s: s["cum_net_income"] != base["cum_net_income"]),
            ("NCO x1.5 -> cum NI must not improve",
             {"_nco_mult": 1.5}, "credit_losses",
             lambda s: s["cum_net_income"] <= base["cum_net_income"],
             lambda s: s["cum_net_income"] != base["cum_net_income"]),
            ("attrition x2 -> ending accounts must not rise",
             {"monthly_attrition": cfg["assumptions"]["monthly_attrition"] * 2},
             "volume_attrition", lambda s: s["accounts_yr3"] <= base["accounts_yr3"],
             lambda s: s["accounts_yr3"] != base["accounts_yr3"]),
            ("growth x0.5 with running fixed costs -> cumulative NI must worsen",
             {"_growth_mult": 0.5}, "volume_vs_fixed_cost",
             lambda s: s["cum_net_income"] <= base["cum_net_income"],
             lambda s: s["cum_net_income"] != base["cum_net_income"]),
        ]
        for name, ov, mech, expect, exercised in cases:
            s = _summ(cfg, ov)
            if not exercised(s):
                check("T3", f"{tag}: {name}", False, f"NOT EXERCISED (mechanism {mech} produced no delta)")
            else:
                check("T3", f"{tag}: {name}", expect(s), f"mechanism={mech}")
        # capital perturbation (target_state, not assumptions)
        s = _summ(cfg, cap=cfg["target_state"]["initial_capital"] + 50e6)
        ok = s["min_leverage"] >= base["min_leverage"]
        ex = s["min_leverage"] != base["min_leverage"]
        check("T3", f"{tag}: capital +$50M -> min leverage must not fall",
              ok if ex else False, "mechanism=capital_base" if ex else "NOT EXERCISED")

# ---------------- T4: challenge benchmark (Icarus expectations) ----------------
def t4():
    print("T4 challenge engine vs labeled broken applicant (Icarus)")
    icarus = copy.deepcopy(SOLSTICE)
    icarus["client_legal_name"] = "Icarus Financial Corp."
    icarus["proposed_bank"] = "Icarus Bank (in organization)"
    icarus["target_state"]["initial_capital"] = 45e6
    icarus["assumptions"].update({
        "new_accts_per_marketing_dollar": 1 / 22.0, "marketing_budget_m": [0.6e6] * 36,
        "savings_rate": 0.0125, "card_nco_mature": 0.021,
        "fraud_alerts_per_1k_accts_m": 2.0, "min_per_alert": 8.0})
    r = runner.run(icarus)
    exp = GOLDENS["icarus_expectations"]
    fails = {t["constraint"] for t in r["constraint_tests"] if not t["pass"]}
    for c in exp["constraints_fail"]:
        check("T4", f"constraint '{c}' detected as breached", c in fails)
    fids = {f["id"] for f in r["flags"]}
    for fid in exp["must_flag"]:
        check("T4", f"flag '{fid}' raised", fid in fids)
    clean = runner.run(copy.deepcopy(SOLSTICE))
    hard = [t for t in clean["constraint_tests"] if not t["pass"]]
    check("T4", "clean case (Solstice) raises no constraint breaches", len(hard) == 0,
          f"{len(clean['flags'])} advisory/support flags retained — review burden, not noise gate")

# ---------------- T14: fail-closed input validation ----------------
def t14():
    print("T14 fail-closed validation")
    broken = copy.deepcopy(BLACKLAND)
    del broken["assumptions"]["savings_rate"]
    try:
        runner.run(broken)
        check("T14", "missing required assumption fails closed", False, "run completed on invalid config")
    except Exception as e:
        check("T14", "missing required assumption fails closed", True, f"raised {type(e).__name__}: {str(e)[:60]}")
    broken2 = copy.deepcopy(SOLSTICE)
    broken2["assumptions"]["monthly_attrition"] = -0.5   # nonsense: negative attrition mints accounts
    try:
        runner.run(broken2)
        check("T14", "nonsense input (negative attrition) rejected", False,
              "engine calculated it — validation layer incomplete")
    except Exception as e:
        check("T14", "nonsense input (negative attrition) rejected", True,
              f"{type(e).__name__}: {str(e)[:70]}")
    # T1 supported-mechanics: a JSON-only client must run with zero code
    from .registry import ENGAGEMENTS
    if "prairie-digital-bank" in ENGAGEMENTS:
        p = runner.run(copy.deepcopy(ENGAGEMENTS["prairie-digital-bank"]["config"]))
        ok = all(t["pass"] for t in p["constraint_tests"])
        check("T1", "supported-mechanics client (Prairie, JSON-only) runs clean, zero code", ok,
              f"hash {p['run_hash']}")

# ---------------- T6 strong form ----------------
def t6():
    print("T6 strong form: unused modules must not move existing clients")
    r = runner.run(copy.deepcopy(SOLSTICE))
    check("T6", "Solstice unchanged with commercial_lending/relationship modules registered",
          r["run_hash"] == GOLDENS["solstice_golden_v5"])

def t15():
    print("T15 output-contract parity: Excel round-trip must reproduce the JSON run")
    import json as _json
    from .excelio import workbook_from_config, parse_workbook
    import io as _io
    cfg = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "clients_uploaded", "prairie_digital.json"), encoding="utf-8"))
    buf = _io.BytesIO(); workbook_from_config(cfg).save(buf)
    cfg2 = parse_workbook(buf.getvalue())
    r1, r2 = runner.run(copy.deepcopy(cfg)), runner.run(cfg2)
    check("T15", "scenarios identical across formats", r1["scenarios"] == r2["scenarios"])
    check("T15", "monthly financials identical across formats", r1["base_monthly"] == r2["base_monthly"])
    check("T15", "cohort, priors, flags identical across formats",
          r1["cohort"] == r2["cohort"] and r1["priors"] == r2["priors"]
          and [f["id"] for f in r1["flags"]] == [f["id"] for f in r2["flags"]])


def t16():
    print("T16 validate/run seam: anything validate_config passes, run() must complete")
    import json as _json
    from .configio import validate_config, ConfigError
    cfg = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "clients_uploaded", "prairie_digital.json"), encoding="utf-8"))
    validate_config(copy.deepcopy(cfg))
    try:
        runner.run(copy.deepcopy(cfg))
        check("T16", "validated config runs end-to-end", True)
    except KeyError as e:
        check("T16", "validated config runs end-to-end", False, f"KeyError {e} — seam reopened")
    broken = copy.deepcopy(cfg); broken.pop("step_0a")
    try:
        validate_config(broken)
        check("T16", "config missing run()-consumed key fails closed", False, "validator passed it")
    except ConfigError:
        check("T16", "config missing run()-consumed key fails closed", True)


def t17():
    print("T17 provenance gate: source names never appear in the product surface")
    import glob
    banned = ["goldstein", "superapp", "jsx build", "predecessor a", "predecessor b"]
    hits = []
    for path in glob.glob("web/*.html"):
        low = open(path, encoding="utf-8").read().lower()
        for b in banned:
            if b in low:
                hits.append(f"{path}: '{b}'")
    check("T17", "web/ carries no source attribution", not hits, "; ".join(hits))


def t18():
    print("T18 engagement store: schema-pinned save/load reproduces the golden hash")
    import tempfile
    from . import store
    base = runner.run(copy.deepcopy(SOLSTICE))["run_hash"]
    prev = os.environ.get("FOUNDRY_DATA_DIR")
    with tempfile.TemporaryDirectory() as td:
        os.environ["FOUNDRY_DATA_DIR"] = td
        try:
            meta = store.save_engagement(copy.deepcopy(SOLSTICE))
            loaded = store.load_engagement(meta["slug"])
            ok_ver = loaded.get("config_schema_version") == store.CONFIG_SCHEMA_VERSION
            rerun = runner.run(loaded)["run_hash"]
            check("T18a", "stored-then-loaded Solstice reproduces golden hash",
                  ok_ver and rerun == base, f"{rerun} vs {base}, ver_ok={ok_ver}")
            # tamper: unsupported version must refuse to load
            path = meta["path"]
            bad = json.load(open(path, encoding="utf-8"))
            bad["config_schema_version"] = "999"
            json.dump(bad, open(path, "w", encoding="utf-8"))
            try:
                store.load_engagement(meta["slug"])
                check("T18b", "unsupported schema version fails closed", False, "loaded anyway")
            except store.SchemaVersionError:
                check("T18b", "unsupported schema version fails closed", True)
            # missing version must refuse to load
            bad.pop("config_schema_version")
            json.dump(bad, open(path, "w", encoding="utf-8"))
            try:
                store.load_engagement(meta["slug"])
                check("T18c", "missing schema version fails closed", False, "loaded anyway")
            except store.SchemaVersionError:
                check("T18c", "missing schema version fails closed", True)
        finally:
            if prev is None:
                os.environ.pop("FOUNDRY_DATA_DIR", None)
            else:
                os.environ["FOUNDRY_DATA_DIR"] = prev


def t19():
    print("T19 field library: concordance closure + progressive disclosure + budget")
    from . import fieldlib as fl
    # (a) closure against the real goldens: every assumption key consumed by the
    # chassis for Solstice/Blackland has exactly one disposition in the library
    lib_fields = set()
    for a in fl.ARCHETYPES.values():
        lib_fields |= set(a["drivers"]) | set(a["defaults"])
    for d in fl.CAPACITY_DEFAULTS.values():
        lib_fields |= set(d)
    lib_fields |= set(fl.GLOBAL_DEFAULTS) | {"org_costs_pre_open"}
    golden_keys = set(SOLSTICE["assumptions"].keys()) | set(BLACKLAND["assumptions"].keys())
    missing = sorted(golden_keys - lib_fields)
    check("T19a", "every golden-consumed assumption key has a library disposition",
          not missing, f"missing: {missing}")
    phantom = sorted(f for f in lib_fields - golden_keys if f != "org_costs_pre_open")
    check("T19b", "library names no field the chassis does not consume",
          not phantom, f"phantom: {phantom}")
    # (c) progressive disclosure: deposits-only surface contains no lending field
    dep = fl.fields_for(["funnel_deposit"])
    lend = fl.fields_for(["funnel_deposit", "commercial_lending"])
    lend_drivers = set(fl.ARCHETYPES["commercial_lending"]["drivers"])
    leak = lend_drivers & (set(dep["typed"]) | set(dep["defaults"]))
    check("T19c", "deposits-only surface carries no lending fields", not leak, f"leak: {sorted(leak)}")
    strictly_adds = set(dep["typed"]) < set(lend["typed"])
    check("T19d", "adding an archetype strictly adds typed fields", strictly_adds,
          f"{len(dep['typed'])} -> {len(lend['typed'])}")
    # (e) budget rule P6
    two = fl.typed_budget(["funnel_deposit", "revolving_credit"])
    four = fl.typed_budget(list(fl.ARCHETYPES.keys())[:4])
    check("T19e", "typed budget: 2-product <=40, 4-product <=70",
          two <= 40 and four <= 70, f"two={two}, four={four}")


def t20():
    print("T20 dialect bridge: chassis drivers -> workspace config, paths pinned")
    import json as _json
    from .bridge import bridge_solstice
    from .v2.run_q import run_v2
    tpl = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    cfg, targets = bridge_solstice(copy.deepcopy(SOLSTICE), tpl)
    r = run_v2(cfg)
    deps = [p for p in r["products"] if p["family"] == "deposit"]
    card = [p for p in r["products"] if p["family"] == "lending"][0]
    dep_path = [sum(p["bal"][t + 1] for p in deps) * 1000 for t in range(12)]
    card_path = [b * 1000 for b in card["bal"][1:13]]
    dd = max(abs(a - b) for a, b in zip(dep_path, targets["target_deposits"]))
    cd = max(abs(a - b) for a, b in zip(card_path, targets["target_receivables"]))
    check("T20a", "bridged deposit path within $1k/qtr of chassis", dd < 1000, f"max ${dd:,.0f}")
    check("T20b", "bridged card path within $1k/qtr of chassis", cd < 1000, f"max ${cd:,.0f}")


def t21():
    print("T21 v3.1 empty-start + taxonomy templates carry the source values")
    import json as _json
    from .v2.run_q import run_v2
    from .v2.validate_q import ConfigErrorV2
    cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
    check("T21a", "default starts empty (products and modules)",
          not cfg["assumptions"]["lending_products"] and not cfg["assumptions"]["deposit_products"]
          and not cfg["step_0"]["modules"])
    r0 = run_v2(cfg)   # fidelity ruling: the source model keeps the BS alive
    bs0 = r0["financials"]["bs"]
    check("T21b", "empty start RUNS: capital plugs into securities, deposits zero (source-model fidelity)",
          bs0["sec"][0] > 0 and bs0["deposits"][0] == 0
          and abs(bs0["equity"][0] * 1000 - cfg["target_state"]["initial_capital"]) < 1e-3,
          f"sec Q1 {bs0['sec'][0]:,.0f}k, equity Q1 {bs0['equity'][0]:,.0f}k")
    tpl = _json.load(open("foundry/fixtures/patrick_templates_v31.json", encoding="utf-8"))
    cc = next(t for t in tpl["loans"] if t["name"] == "Credit Card")
    ok = (abs(cc["yield_ann"] - 0.18) < 1e-12 and abs(cc["originations_q"] - 1_500_000) < 1e-6
          and abs(cc["charge_off_ann"] - 0.04) < 1e-12)
    check("T21c", "template constants match the source workbook", ok)
    # materialize Retail Demand exactly as the UI does; path must hit the targets
    tg = _json.load(open("foundry/fixtures/patrick_default_targets.json", encoding="utf-8"))
    rd = next(t for t in tpl["deposits"] if t["name"] == "Retail Demand")
    b, monthly = 0.0, []
    for _ in range(36):
        b = b * (1 - rd["runoff_ann"] / 12.0) + rd["adds_m"]; monthly.append(b)
    qp = [monthly[3 * q - 1] for q in range(1, 13)]
    g = (qp[11] / qp[0]) ** (1 / 11) - 1.0 if qp[0] else 0.0
    cfg["assumptions"]["deposit_products"] = [{"name": "Retail Demand", "call_report_line": "depDDA",
        "opening_balance": qp[0] / (1 + g), "growth_q": g, "runoff_q": 0.0, "rate_type": "fixed",
        "rate_paid_ann": rd["rate_paid_ann"], "fee_yield_ann": 0.0, "opex_pct_ann": 0.0,
        "opex_fixed_m": 0.0}]
    cfg["step_0"]["modules"] = ["balance_driven_deposits"]
    r = run_v2(cfg)
    dep = [p for p in r["products"] if p["family"] == "deposit"][0]
    got = [x * 1000 for x in dep["bal"][1:13]]
    q1_exact = abs(got[0] - tg["Retail Demand"][0]) < 1000.0
    q12_close = abs(got[11] - tg["Retail Demand"][11]) < 1000.0
    check("T21d", "fitted template: Q1 exact and Q12 within house tol (editable scalars, no pins)",
          q1_exact and q12_close, f"Q1 d=${abs(got[0]-tg['Retail Demand'][0]):.2f}, Q12 d=${abs(got[11]-tg['Retail Demand'][11]):.2f}")


def t22():
    print("T22 FIW: per-engagement workbook, progressive sheets, values, hash")
    import io as _io
    import json as _json
    from openpyxl import load_workbook as _lw
    from .v2.fiw import build_fiw, cfg_hash
    cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
    cfg["proposed_bank"] = "Testament Bank"
    cfg["charter_profile"] = {"charter_type": "national", "regulator": "OCC",
                                "cblr_election": True, "pre_open_months": 9}
    cfg["assumptions"]["deposit_products"] = [{"name": "Retail Demand", "call_report_line": "depDDA",
        "opening_balance": 8_930_000, "growth_q": 0.24, "runoff_q": 0.0, "rate_type": "fixed",
        "rate_paid_ann": 0.005, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
    data, gh = build_fiw(cfg)
    wb = _lw(_io.BytesIO(data))
    check("T22a", "deposits-only FIW: no loan sheet (disclosure extends to paper)",
          wb.sheetnames == ["README", "CONTROL", "ASSM_DEPOSITS", "LIMITS"], str(wb.sheetnames))
    check("T22b", "generation hash on README matches the canonical hash",
          any(r[0].value == "Generation hash" and r[1].value == cfg_hash(cfg) for r in wb["README"].iter_rows()))
    dep = {(r[0].value): r[3].value for r in wb["ASSM_DEPOSITS"].iter_rows(min_row=2)}
    check("T22c", "values transcribed (rate 0.5%, opening $8.93M) and line rendered as label",
          abs(dep["deposit.0.rate_paid_ann"] - 0.005) < 1e-12
          and abs(dep["deposit.0.opening_balance"] - 8_930_000) < 1e-6
          and dep["deposit.0.call_report_line"] == "Deposits: Transaction (DDA)")
    cfg["assumptions"]["lending_products"] = [{"name": "Credit Card", "call_report_line": "loanCreditCard",
        "opening_balance": 0, "originations_q": 1_500_000, "orig_growth_q": 0, "runoff_q": 0,
        "rate_type": "fixed", "yield_ann": 0.18, "charge_off_ann": 0.04, "provision_rate_ann": None,
        "reserve_rate_pct_bal": 0.03, "measurement": "amortized", "fee_yield_ann": 0,
        "opex_pct_ann": 0, "opex_fixed_m": 0}]
    data2, _ = build_fiw(cfg)
    wb2 = _lw(_io.BytesIO(data2))
    keys2 = [r[0].value for r in wb2["ASSM_LOANS"].iter_rows(min_row=2)]
    check("T22d", "adding a loan adds ASSM_LOANS; no mb_ rows without originate-to-sell",
          "ASSM_LOANS" in wb2.sheetnames and not any("mortgage_banking" in (k or "") for k in keys2))


def t23():
    print("T23 FIW diff-import: only human edits apply; facts ignored; fail-closed")
    import io as _io
    import os as _os
    import json as _json
    import tempfile
    from openpyxl import load_workbook as _lw
    from .v2 import fiw as F
    old_env = _os.environ.get("FOUNDRY_DATA_DIR")
    tmp = tempfile.mkdtemp()
    _os.environ["FOUNDRY_DATA_DIR"] = tmp
    try:
        cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
        cfg["assumptions"]["deposit_products"] = [{"name": "Retail Demand", "call_report_line": "depDDA",
            "opening_balance": 8_930_000, "growth_q": 0.24, "runoff_q": 0.0, "rate_type": "fixed",
            "rate_paid_ann": 0.005, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
        cfg["step_0"]["modules"] = ["balance_driven_deposits"]
        data, gh = F.build_fiw(cfg)
        F.persist_snapshot(cfg, gh)
        wb = _lw(_io.BytesIO(data))
        ws = wb["ASSM_DEPOSITS"]
        for r in ws.iter_rows(min_row=2):
            if r[0].value == "deposit.0.rate_paid_ann":
                r[3].value = 0.0125          # human edit
            if r[0].value == "deposit.0.call_report_line":
                r[3].value = "Loans: Other"  # vandalized FACT — must be ignored
        buf = _io.BytesIO(); wb.save(buf)
        # in-app edit made AFTER generation must survive (workbook cell untouched)
        current = _json.loads(_json.dumps(cfg))
        current["assumptions"]["deposit_products"][0]["growth_q"] = 0.30
        merged, rep = F.diff_import(buf.getvalue(), current)
        d = merged["assumptions"]["deposit_products"][0]
        check("T23a", "the one human edit applied", abs(d["rate_paid_ann"] - 0.0125) < 1e-12)
        check("T23b", "untouched workbook cells do not clobber in-app edits since generation",
              abs(d["growth_q"] - 0.30) < 1e-12)
        check("T23c", "fact rows are ignored even when vandalized",
              d["call_report_line"] == "depDDA")
        check("T23d", "edit report names exactly the human change",
              rep["edit_count"] == 1 and rep["edits"][0]["key"] == "deposit.0.rate_paid_ann")
        try:
            wb2 = _lw(_io.BytesIO(data))
            for r in wb2["README"].iter_rows():
                if r[0].value == "Generation hash":
                    r[1].value = "abcdef000000"
            b2 = _io.BytesIO(); wb2.save(b2)
            F.diff_import(b2.getvalue(), current); failed = False
        except ValueError:
            failed = True
        check("T23e", "unknown generation state fails closed", failed)
    finally:
        if old_env is None:
            _os.environ.pop("FOUNDRY_DATA_DIR", None)
        else:
            _os.environ["FOUNDRY_DATA_DIR"] = old_env


def t24():
    print("T24 Mode T stage T-1: ingest+recon on the two real shapes")
    import os as _os
    from .modet import recon_file
    src = "/mnt/project/Klaros_Bank_Charter_Financial_Model_v1_0_Patrick.xlsx"
    if _os.path.exists(src):
        rep = recon_file(open(src, "rb").read(), src)
        check("T24a", "hidden sheets surfaced (the PEER lesson)",
              "PEER" in rep["hidden_sheets"], str(rep["hidden_sheets"])[:90])
        themes = {t for c in rep["candidates"] for t in c["themes"]}
        check("T24b", "lexicon finds the expected themes across the workbook",
              {"deposits", "loans", "credit", "capital", "treasury"} <= themes, str(sorted(themes)))
        long_axes = [ax for sh in rep["sheets"] for ax in sh["time_axes"]
                      if ax["cadence"] == "monthly" or (ax["cadence"] == "periodic" and ax["span"] >= 18)]
        check("T24c", "a long time axis detected (labeled monthly, or periodic span>=18)", bool(long_axes))
        check("T24d", "no unit is ever asserted",
              all(c["units"] == "UNVERIFIED" for c in rep["candidates"]))
        rep2 = recon_file(open(src, "rb").read(), src)
        check("T24e", "recon is deterministic", rep["report_hash"] == rep2["report_hash"])
    else:
        print("  SKIP  source workbook not present in this environment (T24a-e)")
        print("        (5 checks skipped by design on machines without the client file;")
        print("         they run and must pass in the build environment before any bundle ships)")
    csvp = "foundry/fixtures/modet/prairie_style_unit_economics.csv"
    rep = recon_file(open(csvp, "rb").read(), csvp)
    ok = (rep["kind"] == "csv"
          and any(ax["cadence"] == "periodic" and ax["span"] == 12
                   for sh in rep["sheets"] for ax in sh["time_axes"])
          and any("volume" in c["themes"] for c in rep["candidates"])
          and any("fees" in c["themes"] for c in rep["candidates"]))
    check("T24f", "CSV shape (S4): periodic axis (span 12, cadence NOT guessed) + volume/fee candidates", ok,
          f"{rep['candidate_count']} candidates")


def t25():
    print("T25 Mode T stage T-2: mapping session — declarations, exact series, gaps")
    import json as _json
    from .modet import ingest
    from . import modet_map as M
    from .modet import recon
    from .v2.run_q import run_v2
    csvp = "foundry/fixtures/modet/prairie_style_unit_economics.csv"
    inv = ingest(open(csvp, "rb").read(), csvp)
    rep = recon(inv)
    cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
    cfg["assumptions"]["deposit_products"] = [{"name": "Digital Deposits", "call_report_line": "depDDA",
        "opening_balance": None, "growth_q": 0.0, "runoff_q": 0.0, "rate_type": "fixed",
        "rate_paid_ann": None, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
    cfg["step_0"]["modules"] = ["balance_driven_deposits"]
    sess = M.new_session(rep, cfg)
    # refusing to declare is refusing to map
    try:
        M.assign(sess, {"sheet": "(csv)", "row": 4, "label": "Deposit balance"},
                  "deposit.0.balance_path"); undeclared_ok = True
    except ValueError:
        undeclared_ok = False
    check("T25a", "series assignment without declared cadence/units is refused", not undeclared_ok)
    M.assign(sess, {"sheet": "(csv)", "row": 4, "label": "Deposit balance"},
              "deposit.0.balance_path", converter="series_pin",
              declared={"cadence": "monthly", "units": "dollars"})
    M.assign(sess, {"sheet": "(client meeting)", "row": 0, "label": "stated cost of funds"},
              "deposit.0.rate_paid_ann", converter="pct_to_rate",
              declared={"units": "percent"}, params={"value": 1.5})
    merged, log, gaps = M.apply_session(sess, inv, cfg)
    r = run_v2(merged)
    dep = [p for p in r["products"] if p["family"] == "deposit"][0]
    got = [x * 1000 for x in dep["bal"][1:5]]
    src = [5_817_000, 14_294_900, 23_894_900, 34_393_900]  # CSV months 3/6/9/12
    worst = max(abs(a - b) for a, b in zip(got, src))
    check("T25b", "mapped series reproduces the client's path exactly (house tol $1k)",
          worst < 1000.0, f"worst ${worst:,.0f}")
    check("T25c", "scalar conversion applied with provenance user",
          abs(merged["assumptions"]["deposit_products"][0]["rate_paid_ann"] - 0.015) < 1e-12
          and all(x["provenance"] == "user" for x in log))
    check("T25d", "translation log names source, slot, and conversion for every assignment",
          len(log) == 2 and all(("source" in x and "slot" in x and "conversion" in x) for x in log))
    holed = _json.loads(_json.dumps(merged))
    holed["assumptions"]["cash_yield"] = None   # a genuine hole, on a copy
    gaps2 = [g for g in M.slots_for(holed) if g["required"] and not g["filled"]]
    check("T25e", "unfilled required slots surface as gap questions",
          any(g["slot"] == "assumptions.cash_yield" for g in gaps2),
          str([g["slot"] for g in gaps2])[:80])


def t26():
    print("T26 converter library: arithmetic, conventions, registry integrity")
    from . import converters as C
    ok = (abs(C.monthly_flow_x3(1000) - 3000) < 1e-12
          and abs(C.annual_rate_div4(0.15) - 0.0375) < 1e-12
          and abs(C.pct_to_rate(1.5) - 0.015) < 1e-12
          and abs(C.bp_to_rate(25) - 0.0025) < 1e-12
          and abs(C.units_thousands(60000) - 60_000_000) < 1e-6)
    check("T26a", "scalar converters: x3, /4, pct, bp, $000s", ok)
    steps = C.annual_steps_to_quarterly([0.038, 0.036, 0.034])
    check("T26b", "annual steps -> 12 quarterly points, held flat per year (no interpolation)",
          len(steps) == 12 and steps[0] == steps[3] == 0.038 and steps[4] == 0.036 and steps[11] == 0.034)
    path = C.dollar_adds_to_monthly_path(3_000_000, 0.05, 36)
    qp = C.monthly_path_to_quarterly_eop(path)
    import json as _json
    tg = _json.load(open("foundry/fixtures/patrick_default_targets.json", encoding="utf-8"))
    worst = max(abs(a - b) for a, b in zip(qp, tg["Retail Demand"]))
    check("T26c", "dollar-adds path matches the source-workbook recursion (targets sidecar)",
          worst < 1.0, f"worst ${worst:.4f}")
    from .modet_map import CONVERTERS as MC
    check("T26d", "mapping session consumes the library registry (no duplicate arithmetic)",
          MC is C.REGISTRY)


def t27():
    print("T27 inverter metamorphic gate: golden statements -> invert -> re-run -> same statements")
    import json as _json
    import hashlib as _hl
    from .v2.run_q import run_v2
    from .inverter import aggregate_from_run, invert_statements
    cfg = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    r1 = run_v2(cfg)
    agg1 = aggregate_from_run(r1)          # the "client's statements"
    inv = invert_statements(agg1, cfg)
    r2 = run_v2(inv)
    agg2 = aggregate_from_run(r2)
    def worst(key):
        return max(abs(a - b) for a, b in zip(agg1[key], agg2[key]))
    check("T27a", "deposit balance path reproduced ($000s, house tol 1.0)",
          worst("dep_bal") < 1.0, f"worst {worst('dep_bal'):.3f}")
    check("T27b", "loan balance path reproduced", worst("loan_bal") < 1.0,
          f"worst {worst('loan_bal'):.3f}")
    check("T27c", "interest expense reproduced (pinned deposit rates)",
          worst("dep_int_exp") < 1.0, f"worst {worst('dep_int_exp'):.3f}")
    check("T27d", "interest income reproduced (pinned yields)",
          worst("loan_int_inc") < 1.0, f"worst {worst('loan_int_inc'):.3f}")
    check("T27e", "charge-offs reproduced (pinned CO rates, compensated originations)",
          worst("charge_offs") < 1.0, f"worst {worst('charge_offs'):.3f}")
    h = lambda a: _hl.sha256(_json.dumps({k: [round(x, 6) for x in v] for k, v in a.items()},
                                          sort_keys=True).encode()).hexdigest()[:12]
    check("T27f", "statement-series hash equality (the doc's metamorphic test, made precise)",
          h(agg1) == h(agg2), f"{h(agg1)} vs {h(agg2)}")


def t28():
    print("T28 stage T-5: translation log first-class; gaps become questions")
    import json as _json
    from .modet import ingest, recon
    from . import modet_map as M
    csvp = "foundry/fixtures/modet/prairie_style_unit_economics.csv"
    inv = ingest(open(csvp, "rb").read(), csvp)
    rep = recon(inv)
    cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
    cfg["assumptions"]["deposit_products"] = [{"name": "Digital Deposits", "call_report_line": "depDDA",
        "opening_balance": None, "growth_q": 0.0, "runoff_q": 0.0, "rate_type": "fixed",
        "rate_paid_ann": None, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
    cfg["step_0"]["modules"] = ["balance_driven_deposits"]
    sess = M.new_session(rep, cfg)
    M.assign(sess, {"sheet": "(csv)", "row": 4, "label": "Deposit balance"},
              "deposit.0.balance_path", converter="series_pin",
              declared={"cadence": "monthly", "units": "dollars"})
    out = M.finalize(sess, inv, cfg, rep)
    log, qs = out["translation_log"], out["gap_questions"]
    check("T28a", "log carries the source recon hash and one row per assignment",
          log["source_report_hash"] == rep["report_hash"] and len(log["rows"]) == 1)
    check("T28b", "unmapped required slot (deposit rate) becomes a phrased question",
          any("Digital Deposits" in q and "rate paid" in q and q.endswith("authority?") for q in qs),
          qs[0] if qs else "(none)")
    out2 = M.finalize(sess, inv, cfg, rep)
    check("T28c", "the log is deterministic (stable hash)",
          log["log_hash"] == out2["translation_log"]["log_hash"])
    check("T28d", "doctrine rides in the artifact itself",
          any("interpolation" in d for d in log["doctrine"]))


def t29():
    print("T29 Icarus at entry: blockers stop nonsense; optimism enters WITH warnings")
    import json as _json
    from .entry_screen import entry_screen
    cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
    a = cfg["assumptions"]
    a["deposit_products"] = [{"name": "MMDA / Savings", "call_report_line": "depSavings",
        "opening_balance": 1e6, "growth_q": 0.05, "runoff_q": 0.0, "rate_type": "fixed",
        "rate_paid_ann": 0.0125, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
    a["lending_products"] = [{"name": "Credit Card", "call_report_line": "loanCreditCard",
        "opening_balance": 0, "originations_q": 1e6, "orig_growth_q": 0, "runoff_q": 0,
        "rate_type": "fixed", "yield_ann": 0.18, "charge_off_ann": 0.019,
        "provision_rate_ann": None, "reserve_rate_pct_bal": 0.03, "measurement": "amortized",
        "fee_yield_ann": 0, "opex_pct_ann": 0, "opex_fixed_m": 0}]
    sc = entry_screen(cfg)
    check("T29a", "Icarus's mispriced savings (1.25% vs baseline 2.5%) enters WITH a warning",
          not sc["blockers"] and any("MMDA" in w and "1.25%" in w for w in sc["warnings"]),
          (sc["warnings"] or ["-"])[0][:80])
    check("T29b", "Icarus's optimistic card losses (1.9% vs baseline 4%) warned by name",
          any("Credit Card" in w and "optimism" in w for w in sc["warnings"]))
    bad = _json.loads(_json.dumps(cfg))
    bad["target_state"]["initial_capital"] = 2_000_000
    bad["assumptions"]["org_costs_pre_open"] = 2_500_000
    bad["assumptions"]["deposit_products"][0]["runoff_q"] = -0.2
    sc2 = entry_screen(bad)
    check("T29c", "arithmetic self-destruction and negative runoff are BLOCKERS",
          len(sc2["blockers"]) == 2 and any("Day-1" in b for b in sc2["blockers"])
          and any("mints balances" in b or "outside" in b for b in sc2["blockers"]))
    clean = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    sc3 = entry_screen(clean)
    check("T29d", "the clean golden passes the screen silently",
          not sc3["blockers"] and not sc3["warnings"])


def t30():
    print("T30 equivalence matrix: an unedited workbook round-trip is a perfect no-op")
    import io as _io
    import os as _os
    import json as _json
    import tempfile
    from .v2 import fiw as F
    from .v2.run_q import run_v2
    old_env = _os.environ.get("FOUNDRY_DATA_DIR")
    _os.environ["FOUNDRY_DATA_DIR"] = tempfile.mkdtemp()
    try:
        # a wizard-shaped bank, built from the same template constants the JS uses
        tpl = _json.load(open("foundry/fixtures/patrick_templates_v31.json", encoding="utf-8"))
        cfg = _json.load(open("foundry/fixtures/patrick_default_v31.json", encoding="utf-8"))
        rd = next(t for t in tpl["deposits"] if t["name"] == "Retail Demand")
        b, monthly = 0.0, []
        for _ in range(36):
            b = b * (1 - rd["runoff_ann"] / 12.0) + rd["adds_m"]; monthly.append(b)
        qp = [monthly[3 * q - 1] for q in range(1, 13)]
        g = (qp[11] / qp[0]) ** (1 / 11) - 1.0
        cc = next(t for t in tpl["loans"] if t["name"] == "Credit Card")
        cfg["assumptions"]["deposit_products"] = [{"name": "Retail Demand", "call_report_line": "depDDA",
            "opening_balance": qp[0] / (1 + g), "growth_q": g, "runoff_q": 0.0, "rate_type": "fixed",
            "rate_paid_ann": rd["rate_paid_ann"], "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
        cfg["assumptions"]["lending_products"] = [{"name": "Credit Card", "call_report_line": "loanCreditCard",
            "opening_balance": 0.0, "originations_q": cc["originations_q"], "orig_growth_q": 0.0,
            "runoff_q": cc["runoff_q"], "rate_type": "fixed", "yield_ann": cc["yield_ann"],
            "charge_off_ann": cc["charge_off_ann"], "provision_rate_ann": None,
            "reserve_rate_pct_bal": cc["reserve_rate_pct_bal"], "measurement": "amortized",
            "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0}]
        cfg["step_0"]["modules"] = ["balance_driven_deposits", "balance_driven_lending"]
        for name, case in (("wizard-shaped bank", cfg),
                            ("golden pf_a", _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8")))):
            data, gh = F.build_fiw(case)
            F.persist_snapshot(case, gh)
            merged, repd = F.diff_import(data, case)
            same_cfg = _json.dumps(merged, sort_keys=True) == _json.dumps(case, sort_keys=True)
            h1, h2 = run_v2(case)["run_hash"], run_v2(merged)["run_hash"]
            check("T30a" if name.startswith("wizard") else "T30b",
                  f"{name}: unedited round-trip -> zero edits, identical config, identical run hash",
                  repd["edit_count"] == 0 and same_cfg and h1 == h2,
                  f"edits={repd['edit_count']}, hash {h1[:8]} vs {h2[:8]}")
    finally:
        if old_env is None:
            _os.environ.pop("FOUNDRY_DATA_DIR", None)
        else:
            _os.environ["FOUNDRY_DATA_DIR"] = old_env


def t31():
    print("T31 Call Report schedules: assembled from engine series, ties recomputed")
    import json as _json
    from .v2.run_q import run_v2
    from .v2.callreport import build_call_report
    cfg = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    res = run_v2(cfg)
    cr = build_call_report(res, cfg)
    rc = {r["item"]: r["values"] for r in cr["RC"]["rows"]}
    n = len(rc["12"])
    check("T31g", "all schedule rows are uniform Q1..Q12 (openings normalized away)",
          n == 12 and all(len(r["values"]) == 12 for sch in cr.values() for r in sch["rows"]))
    worst_rc = max(abs(rc["1"][t] + rc["2.b"][t] + rc["4.d"][t]
                        + (rc.get("RC-M 2.a", [0]*n)[t]) + rc["6"][t] + rc["10"][t] + rc["11"][t]
                        - rc["12"][t]) for t in range(n))
    check("T31a", "RC ties to the ENGINE's total (HFS memoranda per disclosed convention)",
          worst_rc < 1.0 and any("warehouse" in nt for nt in cr["RC"].get("notes", [])),
          f"worst {worst_rc:.4f}")
    worst_lq = max(abs(rc["13.a"][t] + rc["16"][t] + rc["20"][t] + rc["27.a"][t] - rc["12"][t])
                    for t in range(n))
    check("T31b", "RC ties: deposits + borrowings + other liabilities + equity = Total Assets",
          worst_lq < 1.0, f"worst {worst_lq:.4f}")
    ri = {r["item"]: r["values"] for r in cr["RI"]["rows"]}
    worst_ri = max(abs(ri["1.h"][t] - ri["2.e"][t] - ri["4"][t] + ri["5"][t] - ri["7"][t]
                        - ri["8"][t]) for t in range(n))
    check("T31c", "RI ties: interest income - expense - provision + noninterest net = pretax",
          worst_ri < 1.0, f"worst {worst_ri:.4f}")
    worst_ni = max(abs(ri["8"][t] - ri["9"][t] - ri["12"][t]) for t in range(n))
    check("T31d", "RI ties: pretax - taxes = NET INCOME", worst_ni < 1.0)
    rce = cr["RC-E"]["rows"]
    tot = [r for r in rce if "Total deposits" in r["label"]][0]["values"]
    worst_e = max(abs(tot[t] - rc["13.a"][t]) for t in range(len(tot)))
    check("T31e", "RC-E total ties to RC 13.a", worst_e < 1.0)
    rcr = {str(r["item"]): r["values"] for r in cr["RC-R"]["rows"]}
    lev = res["financials"]["ratios"]["lev"]
    check("T31f", "RC-R leverage equals the ratios tab; omissions and proxies disclosed",
          rcr["31"] == lev and any("proxied" in nt for nt in cr["RC-R"]["notes"]))


def t32():
    print("T32 retrodiction harness: known drift measured exactly; fail-closed labels")
    import json as _json
    from .v2.run_q import run_v2
    from .retro import load_actuals, compare
    cfg = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    res = run_v2(cfg)
    act = load_actuals(open("foundry/fixtures/retro/synthetic_de_novo_actuals.csv", "rb").read(),
                        "synthetic_de_novo_actuals.csv")
    rep = compare(res, act)
    dep = next(s2 for s2 in rep["series"] if s2["label"] == "deposits")
    loans = next(s2 for s2 in rep["series"] if s2["label"] == "loans")
    check("T32a", "deposits drift recovered (~7.4% APE from the x1.08 fixture)",
          abs(dep["mape_pct"] - (1 - 1 / 1.08) * 100) < 0.15, f"MAPE {dep['mape_pct']}%")
    check("T32b", "loans drift recovered (~5.3% APE from the x0.95 fixture)",
          abs(loans["mape_pct"] - (1 / 0.95 - 1) * 100) < 0.15, f"MAPE {loans['mape_pct']}%")
    check("T32c", "overlap window respected (8 actual quarters, not 12)",
          rep["quarters"] == 8 and all(len(s2["rows"]) == 8 for s2 in rep["series"]))
    check("T32d", "summary counts within-15% series and names the worst miss",
          rep["summary"]["series_compared"] == 5
          and isinstance(rep["summary"]["worst_terminal_error_pct"], (int, float)))
    try:
        load_actuals(b"metric,1,2\nmystery_series,1,2\n", "x.csv")
        bad_ok = True
    except ValueError:
        bad_ok = False
    check("T32e", "unknown series labels fail closed (exact labels by design)", not bad_ok)
    rep2 = compare(res, act)
    check("T32f", "the report is deterministic", rep["report_hash"] == rep2["report_hash"])


def t33():
    print("T33 CharterIQ client: read-only contract, units, caveats, fail-closed map")
    import os as _os
    from .charteriq_client import CharterIQClient, accuracy_label
    calls = []
    def fake_exec(sql, params):
        calls.append((sql, params))
        if "information_schema" in sql:
            table = params[0]
            cols = {"institutions": ["cert", "name", "state", "city", "asset_size_mm",
                                       "est_year", "estymd", "end_year", "fail_date",
                                       "charter_type", "active", "profile_tag"],
                     "peer_percentiles": ["id", "cert", "year", "quarter", "group_type",
                                           "group_id", "metric_name", "value", "percentile_rank",
                                           "peer_p10", "peer_p25", "peer_p50", "peer_p75",
                                           "peer_p90", "peer_count"]}[table]
            return [(c2,) for c2 in cols]
        if "FROM institutions" in sql:
            return [(12345, "Testament Bank", "TX", "Austin", 250.0, 2024, "2024-03-15",
                      None, None, "state_nonmember", True, "community")]
        if "FROM metrics" in sql and "DISTINCT" not in sql:
            return [("cet1_ratio", 2025, 3, 12.5), ("cet1_ratio", 2025, 4, 12.8)]
        if "DISTINCT metric_name" in sql:
            return [("cet1_ratio",), ("tier1_ratio",), ("nim",)]
        if "FROM peer_percentiles" in sql:
            return [(8.1, 9.4, 10.9, 12.6, 14.8, 412)]
        return []
    cl = CharterIQClient(executor=fake_exec)
    try:
        cl._run("DELETE FROM institutions"); wrote = True
    except PermissionError:
        wrote = False
    check("T33a", "read-only enforced: non-SELECT refused before any executor sees it", not wrote)
    inst = cl.get_institution(12345)
    check("T33b", "institution record shaped with the terminal-status honesty note",
          inst["name"] == "Testament Bank" and "attribution pending" in inst["terminal_status_note"])
    ser = cl.get_bank_quarterly_series(12345, ["cet1_ratio"])
    check("T33c", "quarterly series ordered and accuracy-labeled per family",
          ser["series"]["cet1_ratio"][0]["value"] == 12.5
          and "item-level" in ser["accuracy"]["cet1_ratio"]
          and "legacy" in accuracy_label("nim"))
    pp = cl.get_peer_percentiles("cet1_ratio", "500M_2B", 2025, 4)
    check("T33d", "capital-family percentiles from the surveyed schema (group_id + "
                    "peer_count), caveat attached",
          pp["p50"] == 10.9 and pp["n"] == 412
          and "approximate until refreshed" in pp["caveat"])
    import os as _os2
    _os2.environ["CHARTERIQ_RETRO_MAP"] = '{"leverage": "leverage_ratio"}'
    try:
        m2 = cl.retro_map()
        check("T33g", "a partial retro map with one ratio series is accepted",
              m2 == {"leverage": "leverage_ratio"})
    finally:
        _os2.environ.pop("CHARTERIQ_RETRO_MAP", None)
    _os.environ.pop("CHARTERIQ_RETRO_MAP", None)
    try:
        cl.get_retro_actuals(12345); mapped = True
    except ValueError as e:
        mapped = False
        msg = str(e)
    check("T33e", "retro pull fails closed without the series map, listing real metric names",
          not mapped and "cet1_ratio" in msg and "CHARTERIQ_RETRO_MAP" in msg)
    check("T33f", "queries are parameterized (no literals interpolated)",
          all("%s" in sql for sql, _ in calls if "WHERE" in sql))


def t34():
    print("T34 staged capital raises: additive, exact, waterfall-absorbed, both engines")
    import json as _json
    from .v2.run_q import run_v2
    for fx, eng in (("pf_a_base", "A"), ("pf_b_base", "B")):
        cfg = _json.load(open(f"foundry/fixtures/parity/configs/{fx}.json", encoding="utf-8"))
        base = run_v2(cfg)
        cfg2 = _json.loads(_json.dumps(cfg))
        cfg2["assumptions"]["capital_raises"] = []
        same = run_v2(cfg2)
        check(f"T34a-{eng}", f"engine {eng}: empty raises list == feature absent (identical results)",
              same["financials"]["bs"]["equity"] == base["financials"]["bs"]["equity"]
              and same["financials"]["bs"]["totalAssets"] == base["financials"]["bs"]["totalAssets"])
        cfg3 = _json.loads(_json.dumps(cfg))
        cfg3["assumptions"]["capital_raises"] = [{"quarter": 4, "amount": 10_000_000}]
        r = run_v2(cfg3)
        eb, ea_ = base["financials"]["bs"], r["financials"]["bs"]
        rk = "re" if "re" in eb else "retained"
        n2 = min(len(eb["equity"]), len(eb[rk]))
        paid_b = [eb["equity"][t] - eb[rk][t] for t in range(n2)]
        paid_r = [ea_["equity"][t] - ea_[rk][t] for t in range(n2)]
        d3, d4 = paid_r[3] - paid_b[3], paid_r[4] - paid_b[4]
        check(f"T34b-{eng}", f"engine {eng}: paid-in capital steps by exactly $10M at Q4 "
                              "(the raise itself; its earnings land in RE, correctly)",
              abs(d3) < 0.01 and abs(d4 - 10_000.0) < 0.01, f"dQ3 {d3:.2f}k, dQ4 {d4:.2f}k")
        ta_b, ta_r = base["financials"]["bs"]["totalAssets"], r["financials"]["bs"]["totalAssets"]
        check(f"T34c-{eng}", f"engine {eng}: the waterfall absorbs the cash (assets up ~$10M at Q4)",
              9_500.0 < (ta_r[4] - ta_b[4]) < 10_500.0, f"dTA {ta_r[4]-ta_b[4]:.0f}k")
    from .v2.validate_q import validate_errors_v2
    import json as _j
    bad = _j.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    bad["assumptions"]["capital_raises"] = [{"quarter": 13, "amount": -5}]
    errs = validate_errors_v2(bad)
    msgs = [e["message"] if isinstance(e, dict) else str(e) for e in errs]
    check("T34d", "validator rejects quarter 13 and negative amounts",
          any("1..12" in m for m in msgs) and any("positive" in m for m in msgs))


def t35():
    print("T35 peer placement + FIW raises round-trip")
    from .charteriq_client import band_for_assets_mm, placement
    check("T35a", "asset band derivation at the fenceposts",
          band_for_assets_mm(199) == "under_200M" and band_for_assets_mm(200) == "200M_500M"
          and band_for_assets_mm(1999) == "500M_2B" and band_for_assets_mm(60000) == "over_50B")
    row = {"p10": 7.0, "p25": 8.5, "p50": 10.0, "p75": 12.0, "p90": 14.5}
    check("T35b", "placement phrasing is coarse and correct",
          placement(6.0, row) == "below p10" and placement(9.0, row) == "p25\u2013p50"
          and placement(15.0, row) == "above p90")
    import io as _io
    import os as _os
    import json as _json
    import tempfile
    from .v2 import fiw as F
    from openpyxl import load_workbook as _lw
    old_env = _os.environ.get("FOUNDRY_DATA_DIR")
    _os.environ["FOUNDRY_DATA_DIR"] = tempfile.mkdtemp()
    try:
        cfg = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
        cfg["assumptions"]["capital_raises"] = [{"quarter": 4, "amount": 10_000_000}]
        data, gh = F.build_fiw(cfg)
        F.persist_snapshot(cfg, gh)
        wb = _lw(_io.BytesIO(data))
        labels = [r[0].value for r in wb["CONTROL"].iter_rows()]
        check("T35c", "FIW CONTROL carries the staged raise rows",
              any("Staged raise 1" in str(l) for l in labels))
        for r in wb["CONTROL"].iter_rows():
            if str(r[0].value).startswith("Staged raise 1 — amount"):
                r[1].value = 15_000_000   # the human ups the raise in Excel
        buf = _io.BytesIO(); wb.save(buf)
        merged, rep = F.diff_import(buf.getvalue(), cfg)
        check("T35d", "editing a raise in Excel round-trips as exactly one edit",
              rep["edit_count"] == 1
              and merged["assumptions"]["capital_raises"][0]["amount"] == 15_000_000
              and merged["assumptions"]["capital_raises"][0]["quarter"] == 4)
    finally:
        if old_env is None:
            _os.environ.pop("FOUNDRY_DATA_DIR", None)
        else:
            _os.environ["FOUNDRY_DATA_DIR"] = old_env


def t36():
    print("T36 vintage corridor: age re-clocking, suppression, survivorship, determinism")
    from .charteriq_client import CharterIQClient, build_vintage_corridor
    def fake_exec(sql, params):
        if "FROM institutions" in sql:
            # three banks: 2019 charter, 2021 charter, 2020 charter that failed
            return [(1, 2019, None, None), (2, 2021, None, None), (3, 2020, 2022, "2022-05-01")]
        if "FROM metrics" in sql:
            rows = []
            # bank 1: roa 1.0,1.1,1.2,1.3 starting 2019Q1 (ages 1..4)
            for i, (y, q) in enumerate([(2019,1),(2019,2),(2019,3),(2019,4)]):
                rows.append((1, "roa", y, q, 1.0 + 0.1*i))
            # bank 2: roa 2.0,2.1 starting 2021Q1 (ages 1..2) + a pre-charter noise row
            rows.append((2, "roa", 2020, 4, 99.0))
            for i, (y, q) in enumerate([(2021,1),(2021,2)]):
                rows.append((2, "roa", y, q, 2.0 + 0.1*i))
            # bank 3: roa 3.0 only (age 1), then it failed
            rows.append((3, "roa", 2020, 1, 3.0))
            return rows
        return []
    cl = CharterIQClient(executor=fake_exec)
    V = build_vintage_corridor(cl, 2018, 2023, metrics=["roa"], min_n=2, max_age_q=4)
    ages = {a["age_q"]: a for a in V["corridor"]["roa"]["ages"]}
    check("T36a", "age re-clocking: three different charter years land on the same age axis "
                    "(age-1 pool = 1.0, 2.0, 3.0; pre-charter noise excluded)",
          ages[1]["n"] == 3 and ages[1]["p50"] == 2.0 and ages[1]["p25"] == 1.0)
    check("T36b", "truncation and survivorship shrink later ages (age-2 n=2, age-3 n=1)",
          ages[2]["n"] == 2 and ages[3]["n"] == 1)
    check("T36c", "below min_n the band is suppressed, not estimated",
          ages[3]["suppressed"] and ages[3]["p50"] is None and not ages[2]["suppressed"])
    check("T36d", "survivorship is counted and stated",
          V["survivorship"]["failed"] == 1 and "not hidden" in V["survivorship"]["note"])
    V2 = build_vintage_corridor(cl, 2018, 2023, metrics=["roa"], min_n=2, max_age_q=4)
    check("T36e", "the corridor is deterministic and fingerprinted",
          V["fingerprint"] == V2["fingerprint"] and len(V["fingerprint"]) == 12)
    Vc = build_vintage_corridor(cl, 2018, 2023, metrics=["tier1_ratio"], min_n=2, max_age_q=2)
    lbl = Vc["corridor"]["tier1_ratio"]["accuracy"]
    check("T36f", "capital history labeled as PROXY with the in-place repair schedule",
          "PROXY" in lbl and "2025Q4" in lbl and "Milestone 2" in lbl)
    from .charteriq_client import VINTAGE_METRICS
    check("T36g", "cet1 excluded from the corridor (proxy duplicate of tier1 pre-2025Q4)",
          "cet1_ratio" not in VINTAGE_METRICS and "tier1_ratio" in VINTAGE_METRICS)


def t37():
    print("T37 pre-opening phase (FLOOR F-010/020/021/022): burn to opening deficit, gate")
    import json as _json
    from .v2.run_q import run_v2
    from .v2.validate_q import validate_errors_v2
    for fx, eng in (("pf_a_base", "A"), ("pf_b_base", "B")):
        cfg = _json.load(open(f"foundry/fixtures/parity/configs/{fx}.json", encoding="utf-8"))
        base = run_v2(cfg)
        cfg2 = _json.loads(_json.dumps(cfg))
        cfg2["pre_opening"] = {"expenses": [
            {"category": "Organizational & legal", "total": 600_000},
            {"category": "Consulting & advisory (incl. Klaros)", "total": 960_000},
            {"category": "Core banking implementation", "total": 720_000},
        ], "min_day1_capital": 20_000_000}
        r = run_v2(cfg2)
        eb, er = base["financials"]["bs"], r["financials"]["bs"]
        has_open = len(eb["equity"]) == 13
        # engine A exposes a true opening column (exact assertion); engine B's
        # index 0 is Q1-end, so the delta includes one quarter's earnings drag
        # on the missing money — correct economics, banded assertion
        lo, hi = (2_279.99, 2_280.01) if has_open else (2_280.0, 2_280.0 * 1.03)
        d_eq = eb["equity"][0] - er["equity"][0]
        check(f"T37a-{eng}", f"engine {eng}: {'opening' if has_open else 'Q1-end'} equity drops "
                              f"by the burn{'' if has_open else ' plus its earnings drag'}",
              lo <= d_eq <= hi, f"d {d_eq:.2f}k")
        rk = "re" if "re" in er else "retained"
        d_re = eb[rk][0] - er[rk][0]
        check(f"T37b-{eng}", f"engine {eng}: the deficit lands in retained earnings, not paid-in",
              lo <= d_re <= hi, f"d {d_re:.2f}k")
        check(f"T37c-{eng}", f"engine {eng}: the waterfall absorbs (assets down ~burn)",
              2_100.0 < (eb["totalAssets"][0] - er["totalAssets"][0]) < 2_450.0)
        check(f"T37d-{eng}", f"engine {eng}: sufficiency gate computes (cushion vs min Day-1)",
              r["pre_open"]["sufficient"] and r["pre_open"]["flag"] == "SUFFICIENT"
              and abs(r["pre_open"]["burn_total"] - 2_280_000) < 1)
    cfg3 = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    cfg3["pre_opening"] = {"expenses": [{"category": "Everything", "total": 999_000_000_000}],
                             "min_day1_capital": 20_000_000}
    r3 = run_v2(cfg3)
    check("T37e", "an underwater plan flags INSUFFICIENT — REVIEW CAPITAL PLAN",
          not r3["pre_open"]["sufficient"] and "INSUFFICIENT" in r3["pre_open"]["flag"])
    bad = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    bad["pre_opening"] = {"expenses": [{"category": "", "total": -5}]}
    msgs = [e["message"] if isinstance(e, dict) else str(e) for e in validate_errors_v2(bad)]
    check("T37f", "validator rejects blank categories and negative totals",
          any("category is required" in m for m in msgs)
          and any("non-negative" in m for m in msgs))


if __name__ == "__main__":
    print("Foundry protocol harness — engine", runner.ENGINE_VERSION)
    t2(); t3(); t4(); t6(); t14(); t15(); t16(); t17(); t18(); t19(); t20(); t21(); t22(); t23(); t24(); t25(); t26(); t27(); t28(); t29(); t30(); t31(); t32(); t33(); t34(); t35(); t36(); t37()
    npass = sum(1 for *_x, ok, _d in [(r[0], r[1], r[2], r[3]) for r in RESULTS] if ok)
    print(f"\n{npass}/{len(RESULTS)} checks passed")
    sys.exit(0 if npass == len(RESULTS) else 1)
