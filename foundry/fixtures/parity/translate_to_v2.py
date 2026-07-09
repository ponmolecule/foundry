"""P0.3 — translate frozen predecessor scenario inputs into Foundry v2 Tier-3 configs.
Normative examples of the v2 schema; T-PAR runs these once v2 exists.
Units: v2 configs are in DOLLARS (Foundry convention); predecessor inputs and
fixture expectations are in $000s (their native unit) — the harness converts."""
import json, hashlib

FX = json.load(open("parity_fixtures.json"))
K = 1000.0
def pct(x): return None if x in (None, "") else float(x)/100.0

def steps_meta(eng_id, name, profile):
    return {
        "engagement_id": eng_id, "schema_version": "2.0",
        "client_legal_name": name, "proposed_bank": name + " (in organization)",
        "hq": "Parity fixture — n/a", "prepared_by": "Foundry v2 parity harness",
        "config_version": "1.0", "config_frozen": "2026-07-08",
        "parity_profile": profile,   # pf_a / pf_b: quarterly balance-driven predecessor semantics
        "step_minus_1": {"decision": "proceed_de_novo",
                         "alternatives_priced": {"de_novo": "Parity fixture."}},
        "step_0a": {"entities": {"bank": name + " — single entity"}, "flags_from_map": [], "map_approved": None},
        "step_1": {"charter": "n/a (fixture)", "regulators": ["n/a"], "rationale": "Parity fixture."},
        "assumption_tags": {},
    }

def from_pf_a(name, fxk):
    fx = FX["fixtures"][fxk]["inputs"]; g = fx["globals"]; prods = fx["products"]
    dep, lend, obs = [], [], []
    for p in prods:
        rate_type = p.get("rateType", "fixed")
        base = {"name": p["name"], "opening_balance": p.get("bal0", 0)*K,
                "rate_type": rate_type,
                "fee_yield_ann": pct(p.get("feeRate", 0)),
                "opex_pct_ann": pct(p.get("opexPct", 0.5)), "opex_fixed_m": p.get("opexFixed", 0)*K/3}
        if rate_type == "float": base["index_spread"] = pct(p.get("spread"))
        if p["cat"] == "liability":
            base.update({"growth_q": pct(p.get("growth", 0.5)), "runoff_q": 0.0,
                         "call_report_line": p["line"]})
            if rate_type == "fixed": base["rate_paid_ann"] = pct(p.get("ratePaid", 1))
            dep.append(base)
        elif p["cat"] == "asset":
            base.update({"originations_q": p.get("orig", 0)*K, "orig_growth_q": pct(p.get("origGrowth", 0.5)),
                         "runoff_q": pct(p.get("runoff", 5)),
                         "charge_off_ann": pct(p.get("chargeOff", 1)),
                         "provision_rate_ann": None,  # pf_a: reserve-maintenance semantics
                         "reserve_rate_pct_bal": pct(p.get("reserveRate", 1.5)),
                         "measurement": p.get("measurement", "amortized"),
                         "call_report_line": p["line"]})
            if rate_type == "fixed": base["yield_ann"] = pct(p.get("yld", 6))
            if p.get("measurement") == "fairvalue":
                base["discount_spread_ann"] = pct(p.get("discountSpread", 2.5))
            if p.get("salePct", 0):
                base["mortgage_banking"] = {
                    "sale_pct_of_orig": pct(p["salePct"]), "gain_on_sale_margin": pct(p.get("saleMargin", 1.5)),
                    "warehouse_hold_q": p.get("holdQtrs", 1),
                    "servicing_retained_pct": pct(p.get("servRetained", 0)),
                    "servicing_fee_bp_ann": p.get("servFee", 0),
                    "msr_cap_rate_pct_upb": pct(p.get("msrCapRate", 0)),
                    "msr_decay_q": pct(p.get("msrDecay", 0))}
            lend.append(base)
        else:
            obs.append({"name": p["name"], "notional": p.get("bal0", 0)*K,
                        "growth_q": pct(p.get("growth", 0.5)), "fee_yield_ann": pct(p.get("feeRate", 0))})
    stress = fx.get("stress") or {}
    cfg = steps_meta("ENG-PAR-" + fxk.upper(), name, "pf_a")
    cfg.update({
        "step_0": {"one_sentence": "Parity fixture (predecessor A semantics).",
                   "earning_engine": "spread",
                   "modules": ["balance_driven_deposits", "balance_driven_lending"]
                              + (["mortgage_banking"] if any("mortgage_banking" in l for l in map(json.dumps, lend)) else [])
                              + (["balance_driven_obs"] if obs else [])},
        "constraints": [{"key": "leverage_min", "value": g.get("levMin", 9)/100.0,
                         "text": "Tier 1 leverage floor.", "source": "Parity fixture (predecessor A default)"}],
        "target_state": {"initial_capital": g.get("capital", 60000)*K,
                         "assets_yr3": max(1.0, FX["fixtures"][fxk]["expected"]["bs"]["totalAssets"][-1]*K)},
        "peer_query": {"consumer_loan_share": 0.4, "fee_income_share": 0.2,
                       "core_funding_share": 0.9, "digital_channel": 1.0},
        "assumptions": {
            "rate_path_q": [g[f"sofr{i}"]/100.0 for i in range(1, 13)],
            "rate_path_longer_run": g.get("sofrLR", 3.15)/100.0,
            "tax_semantics": "nol_carryforward_pf_a",
            "tax_rate": g.get("taxRate", 21)/100.0,
            "cash_target_pct_deposits": g.get("cashFloor", 5)/100.0,
            "cash_yield": g.get("cashYield", 2.5)/100.0,
            "securities_yield": g.get("secYield", 4.0)/100.0,
            "borrow_rate_ann": g.get("borrowRate", 5.5)/100.0,
            "overhead_q": g.get("overheadQ", 1800)*K, "overhead_growth_q": g.get("overheadG", 1)/100.0,
            "premises_equipment": g.get("premises", 5000)*K, "intangibles": g.get("intangibles", 0)*K,
            "other_assets": g.get("otherAssets", 2000)*K, "other_liabilities": g.get("otherLiab", 1000)*K,
            "deposit_products": dep, "lending_products": lend, "obs_exposures": obs,
        },
        "scenario_overlays": ({"charge_off_mult": stress.get("coMult", 1), "reserve_mult": stress.get("resMult", 1),
                               "rate_shock_bp": stress.get("shockBp", 0),
                               "origination_volume_haircut": stress.get("volHaircut", 0)/100.0,
                               "gos_margin_compression": stress.get("gosComp", 0)/100.0,
                               "msr_value_haircut": stress.get("msrShock", 0)/100.0,
                               "sale_share_retention_shift": stress.get("saleShift", 0)/100.0} if stress else None),
        "parity_expectation": {"fixture": fxk, "run_scenario": "overlay" if stress else "base"},
    })
    return cfg

def from_pf_b(name, fxk):
    fx = FX["fixtures"][fxk]["inputs"]; g = fx["globals"]; prods = fx["products"]
    dep, lend, obs, afs, htm = [], [], [], [], []
    for p in prods:
        ov = p.get("overrides") or {}
        def vec(field, scale=1.0):
            m = ov.get(field) or {}
            return {str(int(q)+1): float(v)*scale for q, v in m.items() if v not in ("", None)} or None
        if p["category"] == "liability":
            d = {"name": p["name"], "opening_balance": p.get("balance", 0)*K,
                 "growth_q": pct(p.get("growth", 0.5)), "runoff_q": pct(p.get("runoff", 0)),
                 "rate_type": "fixed", "rate_paid_ann": pct(p.get("rate", 0)),
                 "fee_yield_ann": pct(p.get("fee", 0)), "opex_fixed_m": p.get("opex", 0)*K/3,
                 "call_report_line": p["line"],
                 "overrides": {k: v for k, v in {"growth_q": vec("growth", 0.01),
                                                 "rate_paid_ann": vec("rate", 0.01)}.items() if v} or None}
            dep.append(d)
        elif p["category"] == "asset" and p["line"].startswith("Securities"):
            (afs if "AFS" in p["line"] else htm).append(
                {"name": p["name"], "opening": p.get("balance", 0)*K, "purchases_q": 0.0,
                 "growth_q": pct(p.get("growth", 0)), "runoff_q": pct(p.get("runoff", 0)),
                 "yield_ann": pct(p.get("rate", 0))})
        elif p["category"] == "asset":
            l = {"name": p["name"], "opening_balance": p.get("balance", 0)*K,
                 "volume_mode": p.get("inputMode", "growth"),
                 "growth_q": pct(p.get("growth", 0.5)), "originations_q": (p.get("originations") or 0)*K,
                 "runoff_q": pct(p.get("runoff", 0)),
                 "rate_type": "fixed", "yield_ann": pct(p.get("rate", 0)),
                 "charge_off_ann": pct(p.get("chargeoff", 0)),
                 "provision_rate_ann": pct(p.get("loss")) if p.get("loss") not in ("", None) else None,
                 "reserve_rate_pct_bal": None,  # pf_b: entity ALLL floor semantics
                 "fee_yield_ann": pct(p.get("fee", 0)), "opex_fixed_m": p.get("opex", 0)*K/3,
                 "measurement": "amortized", "call_report_line": p["line"],
                 "overrides": {k: v for k, v in {"yield_ann": vec("rate", 0.01),
                                                 "charge_off_ann": vec("chargeoff", 0.01),
                                                 "originations_q": vec("originations", K)}.items() if v} or None}
            lend.append(l)
        else:
            obs.append({"name": p["name"], "notional": p.get("balance", 0)*K,
                        "growth_q": pct(p.get("growth", 0.5)), "fee_yield_ann": pct(p.get("fee", 0))})
    cfg = steps_meta("ENG-PAR-" + fxk.upper(), name, "pf_b")
    cfg.update({
        "step_0": {"one_sentence": "Parity fixture (predecessor B semantics).", "earning_engine": "spread",
                   "modules": ["balance_driven_deposits", "balance_driven_lending"]
                              + (["investment_portfolio"] if (afs or htm) else [])
                              + (["balance_driven_obs"] if obs else [])},
        "constraints": [{"key": "leverage_min", "value": 0.08,
                         "text": "Tier 1 leverage floor.", "source": "Parity fixture (predecessor B default)"}],
        "target_state": {"initial_capital": g.get("capital", 30000)*K,
                         "assets_yr3": max(1.0, FX["fixtures"][fxk]["expected"]["bs"]["totalAssets"][-1]*K)},
        "peer_query": {"consumer_loan_share": 0.4, "fee_income_share": 0.2,
                       "core_funding_share": 0.9, "digital_channel": 1.0},
        "assumptions": {
            "rate_path_q": [0.0] * 12,  # pf_b prices products directly; no index
            "rate_path_longer_run": 0.0,
            "tax_semantics": "no_dta_pf_b",
            "tax_rate": g.get("taxRate", 21)/100.0,
            "cash_yield": g.get("cashYield", 4.0)/100.0,
            "sweep_securities_yield": g.get("secYield", 4.4)/100.0,
            "sweep_securities_alloc": g.get("secAlloc", 60)/100.0,
            "borrow_rate_ann": g.get("borrowRate", 5.5)/100.0,
            "alll_floor_pct_loans": g.get("reserveRatio", 1.25)/100.0,
            "overhead_q": g.get("fixedOpex", 1400)*K, "overhead_growth_q": 0.0,
            "premises_equipment": g.get("premises", 3000)*K, "intangibles": g.get("intangibles", 0)*K,
            "other_assets": g.get("otherAssets", 750)*K, "other_liabilities": g.get("otherLiab", 400)*K,
            "reporting": {"ftp_benchmark_ann": g.get("ftpRate", 4.25)/100.0},
            "deposit_products": dep, "lending_products": lend, "obs_exposures": obs,
            "securities_afs": afs or None, "securities_htm": htm or None,
        },
        "scenario_overlays": None,
        "parity_expectation": {"fixture": fxk, "run_scenario": "base"},
    })
    return cfg

NAMES = {
 "pf_a_base": "Parity Fixture Bank A1", "pf_a_combined_stress": "Parity Fixture Bank A2",
 "pf_a_warning_heavy": "Parity Fixture Bank A3", "pf_a_ots_msr": "Parity Fixture Bank A4",
 "pf_a_fv_election": "Parity Fixture Bank A5",
 "pf_b_base": "Parity Fixture Bank B1", "pf_b_overrides": "Parity Fixture Bank B2",
 "pf_b_htm_securities": "Parity Fixture Bank B3", "pf_b_reserve_build": "Parity Fixture Bank B4"}

import os
os.makedirs("configs", exist_ok=True)
for k, nm in NAMES.items():
    cfg = (from_pf_a if k.startswith("pf_a") else from_pf_b)(nm, k)
    json.dump(cfg, open(f"configs/{k}.json", "w"), indent=1)
print("v2 configs written:", len(NAMES))
