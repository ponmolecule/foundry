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
    try:
        run_v2(cfg); rejected = False
    except ConfigErrorV2:
        rejected = True
    check("T21b", "fail-closed preserved: empty start cannot run (UI gates the engine)", rejected)
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


if __name__ == "__main__":
    print("Foundry protocol harness — engine", runner.ENGINE_VERSION)
    t2(); t3(); t4(); t6(); t14(); t15(); t16(); t17(); t18(); t19(); t20(); t21(); t22()
    npass = sum(1 for *_x, ok, _d in [(r[0], r[1], r[2], r[3]) for r in RESULTS] if ok)
    print(f"\n{npass}/{len(RESULTS)} checks passed")
    sys.exit(0 if npass == len(RESULTS) else 1)
