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


if __name__ == "__main__":
    print("Foundry protocol harness — engine", runner.ENGINE_VERSION)
    t2(); t3(); t4(); t6(); t14(); t15(); t16(); t17(); t18(); t19()
    npass = sum(1 for *_x, ok, _d in [(r[0], r[1], r[2], r[3]) for r in RESULTS] if ok)
    print(f"\n{npass}/{len(RESULTS)} checks passed")
    sys.exit(0 if npass == len(RESULTS) else 1)
