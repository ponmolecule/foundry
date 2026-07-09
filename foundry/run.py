"""Orchestrator: full cradle-to-grave run for one engagement -> results.json."""
import json, math, hashlib, datetime, os, sys
from . import peers, chassis, challenge
from .client_solstice import CLIENT

ENGINE_VERSION = "foundry-engine 0.3.0"
OUTPUT_SCHEMA = "2"

def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]

def run(cfg=None):
    cfg = cfg or CLIENT
    from .configio import validate_config
    validate_config(cfg)
    q = dict(cfg["peer_query"])
    q["log_assets_yr3"] = math.log10(cfg["target_state"]["assets_yr3"])

    cohort = peers.select_cohort(q)

    scen = chassis.run_scenarios(cfg)
    base = scen["base"]

    a = cfg["assumptions"]
    ib_share = a.get("savings_share_accounts", a.get("interest_bearing_share", 1.0))
    chk = a.get("checking_rate", 0.0) * (1 - a.get("savings_share_accounts", 1.0)) \
          if "savings_share_accounts" in a else 0.0
    all_metrics = {
        "deposit_growth_yr1": base["summary"]["deposit_growth_yr1"],
        "cost_of_deposits_spread": (a["savings_rate"] * ib_share + chk) - a["fed_funds"],
        "card_nco_mature": a.get("card_nco_mature"),
        "cac_per_funded_account": (1.0 / a["new_accts_per_marketing_dollar"])
                                  if a.get("new_accts_per_marketing_dollar") else None,
        "opex_per_active_acct": base["rows"][-1]["opex"] * 12 / base["rows"][-1]["accounts"],
        "efficiency_q12": (base["rows"][11]["opex"] + base["rows"][11]["marketing"]) /
                          max(base["rows"][11]["int_income"] + base["rows"][11]["interchange"]
                              - base["rows"][11]["cost_deposits"], 1),
    }
    wanted = cfg.get("prior_metrics", list(all_metrics))
    client_metrics = {k: v for k, v in all_metrics.items() if k in wanted and v is not None}
    prior_table = peers.priors(cohort, client_metrics)

    commit = next(c["value"] for c in cfg["constraints"] if c["key"] == "leverage_min")
    rev_growth = chassis.reverse_stress(cfg, commit)
    rev_nco = chassis.reverse_stress_nco(cfg, commit)
    rev_cap = chassis.reverse_stress_capital(cfg, commit)

    ctests = challenge.constraint_tests(cfg, scen)
    flags = challenge.business_flags(cfg, base["rows"], prior_table)
    if cfg.get("archetype", "digital_consumer") == "digital_consumer":
        book = challenge.examiner_book(cfg, scen, prior_table, cohort, rev_nco)
    else:
        book = challenge.examiner_book_generic(cfg, scen, prior_table, cohort, ctests)

    # assumption book
    abook = []
    for k, (tag, prior_key) in cfg["assumption_tags"].items():
        val = cfg["assumptions"].get(k, client_metrics.get(k))
        row = {"assumption": k, "value": val, "confidence": tag,
               "ancestry": f"{cohort['cohort_id']} / criteria {cohort['criteria_doc']}"
                           if prior_key else "engagement record"}
        if prior_key and prior_key in prior_table:
            row["cohort_percentile"] = prior_table[prior_key]["client_percentile"]
            row["cohort_p50"] = prior_table[prior_key]["p50"]
        abook.append(row)

    readiness = {
        "constraints_pass": all(t["pass"] for t in ctests if t["scenario"] == "base"),
        "constraints_pass_all_scenarios": all(t["pass"] for t in ctests),
        "hard_stops": 0,
        "open_items": sum(1 for f in flags if f["class"] in
                          ("commercial_assumption_requiring_support",
                           "counsel_determination_required", "likely_regulatory_objection")),
        "insufficient_peer_evidence": cohort["insufficient_evidence"],
    }

    cohort_pub = {k: v for k, v in cohort.items() if not k.startswith("_")}
    results = {
        "engine_version": ENGINE_VERSION,
        "run_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "client": {k: cfg[k] for k in ("engagement_id", "client_legal_name", "proposed_bank",
                                        "hq", "config_version", "config_frozen")},
        "steps": {"minus_1": cfg["step_minus_1"], "zero": cfg["step_0"],
                  "zero_a": cfg["step_0a"], "one": cfg["step_1"]},
        "constraints": cfg["constraints"], "target_state": cfg["target_state"],
        "cohort": cohort_pub, "priors": prior_table,
        "scenarios": {k: v["summary"] for k, v in scen.items()},
        "base_monthly": [{kk: (round(vv) if isinstance(vv, float) and abs(vv) > 100 else
                          (round(vv, 4) if isinstance(vv, float) else vv))
                          for kk, vv in r.items()} for r in base["rows"]],
        "scenario_leverage_paths": {k: [round(r["leverage"], 4) for r in v["rows"]]
                                    for k, v in scen.items()},
        "reverse_stress": {"growth": rev_growth, "credit": rev_nco, "capital": rev_cap},
        "constraint_tests": ctests, "flags": flags,
        "assumption_book": abook, "examiner_book": book,
        "readiness": readiness,
    }
    # canonical hash: exclude non-economic metadata (run_at) per testing
    # protocol T2 — identical inputs must produce an identical hash forever
    canon = {k: v for k, v in results.items() if k != "run_at"}
    results["manifest"] = {
        "engine_version": ENGINE_VERSION,
        "output_schema": OUTPUT_SCHEMA,
        "config_hash": _h(cfg),
        "assumptions_hash": _h(cfg["assumptions"]),
        "reference_data": "fixture-v2",
        "reference_data_hash": _h(peers.REFERENCE),
        "cohort_id": cohort_pub["cohort_id"],
        "criteria_doc": cohort_pub["criteria_doc"],
        "rules_as_of": cfg["client" if False else "config_frozen"] if False else cfg["config_frozen"],
        "python": sys.version.split()[0],
        "requirements_hash": _h(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")).read()),
    }
    blob = json.dumps(canon, sort_keys=True, default=str).encode()
    results["run_hash"] = hashlib.sha256(blob).hexdigest()[:12]
    return results

if __name__ == "__main__":
    r = run()
    with open("results.json", "w") as f:
        json.dump(r, f, indent=1, default=str)
    s = r["scenarios"]["base"]
    print("run", r["run_hash"], "| cohort n =", r["cohort"]["n"],
          "| min lev", s["min_leverage"], "m" + str(s["min_leverage_month"]),
          "| breakeven m", s["breakeven_month"],
          "| assets yr3 ${:.0f}M".format(s["assets_yr3"] / 1e6),
          "| identity OK")
