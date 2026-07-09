"""Tier 2 product modules.

Contract (per architecture v2.1 section 6, pilot-scale): each module is a
function step(a, S, t, ctx) mutating its own slice of state S and returning
a contribution dict the chassis aggregates:
  interest_terms : list of annualized interest-income products (order matters
                   for float-exact golden reproduction; chassis divides by 12
                   after summing)
  fee_income     : monthly fee/interchange income
  cost_of_funds  : monthly interest expense
  provision      : monthly provision expense
  ops_minutes    : capacity demand for the expense engine
  balances       : dict of balance-sheet contributions
Modules never see each other; shared volume state lives in S and is produced
by the deposit/customer module loaded for the engagement.
"""

# ---------------- deposit & customer engines ----------------

def core_deposits_app_funnel(a, S, t, ctx):
    """Solstice mechanics, lifted verbatim from chassis v0.1 for hash fidelity."""
    mkt = ctx["mkt"]
    new_from_mig = S["mig"]
    S["mig"] *= a["migration_decay"]
    new_from_mkt = mkt[t - 1] * a["new_accts_per_marketing_dollar"] * a.get("_growth_mult", 1.0)
    new_accts = new_from_mig + new_from_mkt
    attr = S["accts"] * a["monthly_attrition"]
    S["accts"] = S["accts"] + new_accts - attr
    S["new_hist"].append(new_accts)

    ramp = a["balance_ramp_months"]
    recent = S["new_hist"][-ramp:]
    immature_deficit = sum(recent[i] * (1 - (i + 1) / ramp) for i in range(len(recent)))
    eff_accts = max(S["accts"] - immature_deficit, 0.0)
    avg_bal = (a["savings_share_accounts"] * a["avg_balance_savings"]
               + (1 - a["savings_share_accounts"]) * a["avg_balance_checking"])
    deposits = eff_accts * avg_bal

    cost_dep = (ctx["savings_rate"] + a.get("_dep_cost_add", 0.0)) * a["savings_share_accounts"] * deposits / 12.0 \
               + a["checking_rate"] * (1 - a["savings_share_accounts"]) * deposits / 12.0
    S["deposits"] = deposits
    S["new_accts"] = new_accts
    return {"cost_of_funds": cost_dep, "balances": {"deposits": deposits}}


def core_deposits_relationship(a, S, t, ctx):
    """Community-bank mechanics: banker-driven relationship acquisition."""
    bankers = min(a["bankers_start"] + (t - 1) * a["bankers_add_per_m"], a["bankers_max"])
    new_rel = bankers * a["new_relationships_per_banker_m"] * a.get("_growth_mult", 1.0)
    churn = S["accts"] * a["monthly_attrition"]
    S["accts"] = S["accts"] + new_rel - churn
    S["new_hist"].append(new_rel)

    ramp = a["balance_ramp_months"]
    recent = S["new_hist"][-ramp:]
    immature_deficit = sum(recent[i] * (1 - (i + 1) / ramp) for i in range(len(recent)))
    eff = max(S["accts"] - immature_deficit, 0.0)
    deposits = eff * a["avg_deposit_per_relationship"]

    rate = ctx["savings_rate"] + a.get("_dep_cost_add", 0.0)   # blended interest-bearing rate
    cost_dep = rate * a["interest_bearing_share"] * deposits / 12.0
    S["deposits"] = deposits
    S["new_accts"] = new_rel
    S["bankers"] = bankers
    return {"cost_of_funds": cost_dep, "balances": {"deposits": deposits}}


# ---------------- credit modules ----------------

def revolving_credit(a, S, t, ctx):
    """Card book, lifted verbatim from chassis v0.1."""
    pen = a["card_penetration"] * min(1.0, t / a["card_penetration_ramp_m"])
    card_accts = S["accts"] * pen
    recv = card_accts * a["card_avg_balance"]
    nco_ann = a["card_nco_mature"] * min(1.0, t / a["card_nco_ramp_m"]) * a.get("_nco_mult", 1.0)
    chargeoffs = recv * nco_ann / 12.0
    target_all = a["allowance_coverage"] * recv
    provision = chargeoffs + max(target_all - S["allowance"], -S["allowance"])
    S["allowance"] = target_all
    S["recv"] = recv
    from .chassis import resolve_rate
    _cy = resolve_rate(a, a["card_yield"], t, ctx["rate_m"]) if "rate_m" in ctx else a["card_yield"]
    return {"interest_terms": [recv * _cy],
            "provision": provision,
            "balances": {"receivables": recv, "allowance": S["allowance"]}}


def commercial_lending(a, S, t, ctx):
    """CRE + C&I as parameterizations of one mechanic: originate, amortize, lose."""
    out = {"interest_terms": [], "provision": 0.0, "balances": {}}
    total_recv = 0.0; total_all = 0.0
    for seg in a["loan_segments"]:               # e.g. {"name":"cre", ...}
        key = "bal_" + seg["name"]
        bal = S.get(key, 0.0)
        lenders = min(a["lenders_start"] + (t - 1) * a["lenders_add_per_m"], a["lenders_max"])
        orig = lenders * seg["orig_per_lender_m"] * min(1.0, t / seg["ramp_m"]) * a.get("_growth_mult", 1.0)
        bal = bal * (1 - seg["amort_annual"] / 12.0) + orig
        nco_ann = seg["nco_mature"] * min(1.0, t / seg["nco_ramp_m"]) * a.get("_nco_mult", 1.0)
        chargeoffs = bal * nco_ann / 12.0
        bal -= chargeoffs
        S[key] = bal
        akey = "all_" + seg["name"]
        target_all = seg["allowance_coverage"] * bal
        out["provision"] += chargeoffs + max(target_all - S.get(akey, 0.0), -S.get(akey, 0.0))
        S[akey] = target_all
        from .chassis import resolve_rate
        _sy = resolve_rate(a, seg["yield"], t, ctx["rate_m"]) if "rate_m" in ctx else seg["yield"]
        out["interest_terms"].append(bal * _sy)
        total_recv += bal; total_all += target_all
        out["balances"]["loans_" + seg["name"]] = bal
    S["recv"] = total_recv
    S["allowance"] = total_all
    S["lenders"] = lenders
    out["balances"]["receivables"] = total_recv
    out["balances"]["allowance"] = total_all
    return out


# ---------------- fee modules ----------------

def payments_fees_digital(a, S, t, ctx):
    """Interchange + per-account fees, lifted verbatim."""
    interchange = S["accts"] * a["monthly_debit_spend_per_acct"] * a["interchange_rate"]
    fees = S["accts"] * a["fee_per_acct_m"]
    S["interchange"] = interchange
    return {"fee_terms": [interchange, fees]}


def payments_fees_relationship(a, S, t, ctx):
    """Service charges + treasury-management fees on commercial relationships."""
    fees = S["accts"] * a["service_charge_per_rel_m"] + S["deposits"] * a["tm_fee_rate_ann"] / 12.0
    S["interchange"] = 0.0
    return {"fee_terms": [fees]}


# ---------------- capacity expense engines ----------------

def capacity_expenses_digital(a, S, t, ctx):
    """Verbatim v0.1 digital-ops drivers."""
    ops_minutes = (S["new_accts"] * a["kyc_reviews_per_new_acct"] * a["kyc_min_per_review"]
                   + S["accts"] / 1000.0 * a["fraud_alerts_per_1k_accts_m"] * a["min_per_alert"]
                   + S["accts"] * a["service_contacts_per_acct_m"] * a["min_per_contact"])
    return {"ops_minutes": ops_minutes}


def capacity_expenses_branch(a, S, t, ctx):
    """Branch/credit-admin drivers: relationships and loans generate the minutes."""
    n_loans = sum(S.get("bal_" + seg["name"], 0.0) / seg["avg_loan_size"] for seg in a["loan_segments"])
    ops_minutes = (S["new_accts"] * a["onboarding_min_per_rel"]
                   + S["accts"] * a["service_min_per_rel_m"]
                   + n_loans * a["credit_admin_min_per_loan_m"])
    return {"ops_minutes": ops_minutes}


# ---------------- registry ----------------
# Configuration names map to (function, role). Roles order chassis execution:
# deposits -> credit -> fees -> capacity. investment_portfolio is chassis-level
# (funding-waterfall residual) and appears here as a no-op marker for validation.

REGISTRY = {
    "core_deposits":            (core_deposits_app_funnel,      "deposits"),
    "relationship_deposits":    (core_deposits_relationship,    "deposits"),
    "revolving_credit":         (revolving_credit,              "credit"),
    "commercial_lending":       (commercial_lending,            "credit"),
    "payments_fees":            (payments_fees_digital,         "fees"),
    "relationship_fees":        (payments_fees_relationship,    "fees"),
    "capacity_expenses":        (capacity_expenses_digital,     "capacity"),
    "branch_capacity_expenses": (capacity_expenses_branch,      "capacity"),
    "investment_portfolio":     (None,                          "chassis"),
}
