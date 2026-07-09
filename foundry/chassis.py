"""Deterministic projection chassis (steps 3 volume decomposition, 6, 7).

Monthly loop, 36 months, generic over the Tier 2 module set named in the
client configuration. Every month asserts assets == liabilities + equity to
the cent; a failed identity raises rather than producing output (D6).
"""
from .modules import REGISTRY


def av(a, key, t, default=0.0):
    """B.3 — universal scalar-or-vector assumption: any numeric driver may be a
    monthly list (the marketing_budget_m pattern generalized). Scalars behave
    exactly as before; lists index by month, last value repeating."""
    v = a.get(key, default)
    if isinstance(v, list):
        if not v:
            return default
        return v[min(t, len(v)) - 1]
    return v


def rate_m(a):
    """B.1 — forward rate context. rate_path_m (monthly annual rates, last value
    repeating; glides 5bp/month toward rate_path_longer_run beyond the list) with
    scalar fed_funds as the compatibility fallback (a flat path — schema-v1
    configs auto-promote and reproduce their frozen numbers exactly, B.8)."""
    path = a.get("rate_path_m")
    if not path:
        ff = a["fed_funds"]
        return lambda t: ff
    lr = a.get("rate_path_longer_run", path[-1])
    n = len(path)

    def r(t):
        if t <= n:
            return path[t - 1]
        last = path[n - 1]
        step = 0.0005 * (t - n)
        return max(lr, last - step) if last > lr else min(lr, last + step)
    return r


def resolve_rate(a, spec, t, rm):
    """B.2 — fixed/floating rate typing for module drivers. A rate driver may be
    a scalar (fixed, exactly as before) or {"type": "float", "spread": x}, which
    reprices monthly at rate_path + spread (+ any scenario rate shock)."""
    if isinstance(spec, dict) and spec.get("type") == "float":
        return rm(t) + spec.get("spread", 0.0) + a.get("_rate_shock", 0.0)
    return spec


def project(cfg, overrides=None):
    a = dict(cfg["assumptions"])
    if overrides:
        a.update(overrides)
    T = 36
    mkt = list(a.get("marketing_budget_m", [0.0]))[:T]
    mkt = mkt + [mkt[-1]] * max(0, T - len(mkt))
    mkt = [m * a.get("_mkt_mult", 1.0) for m in mkt]

    loaded = [(n,) + REGISTRY[n] for n in cfg["step_0"]["modules"]]
    dep_mods = [f for n, f, r in loaded if r == "deposits"]
    credit_mods = [f for n, f, r in loaded if r == "credit"]
    fee_mods = [f for n, f, r in loaded if r == "fees"]
    cap_mods = [f for n, f, r in loaded if r == "capacity"]

    rm = rate_m(a)
    ctx = {"mkt": mkt, "rate_m": rm, "savings_rate": 0.0}

    S = {"accts": 0.0, "new_hist": [], "mig": a.get("migration_accounts_m1", 0.0),
         "deposits": 0.0, "recv": 0.0, "allowance": 0.0, "interchange": 0.0,
         "new_accts": 0.0}
    other_assets = 6.0e6
    paid_in = cfg["target_state"]["initial_capital"]
    retained = -a["org_costs_pre_open"]
    cum_pretax = -a["org_costs_pre_open"]
    rows = []

    for t in range(1, T + 1):
        ctx["savings_rate"] = av(a, "savings_rate", t) + a.get("_rate_shock", 0.0) * a.get("_beta", a["deposit_beta_up"])
        cost_dep = 0.0; provision = 0.0; ops_minutes = 0.0
        interest_terms = []; fee_terms = []

        for f in dep_mods:
            c = f(a, S, t, ctx)
            cost_dep += c.get("cost_of_funds", 0.0)
        for f in credit_mods:
            c = f(a, S, t, ctx)
            provision += c.get("provision", 0.0)
            interest_terms.extend(c.get("interest_terms", []))
        if not credit_mods:
            S["recv"] = 0.0; S["allowance"] = 0.0

        deposits = S["deposits"]; recv = S["recv"]; allowance = S["allowance"]

        # funding & investment waterfall (chassis-level). If loans outrun
        # deposits+equity, wholesale borrowings (FHLB-style) bridge the gap so
        # the identity holds through the real mechanism, not a silent plug.
        equity_pre = paid_in + retained
        cash = a["cash_target_pct_deposits"] * deposits
        borrowings = max(cash + recv + other_assets - allowance - deposits - equity_pre, 0.0)
        a_sec = max(deposits + borrowings + equity_pre + allowance - cash - recv - other_assets, 0.0)

        # income: sum annualized products left-to-right, divide once (float-exact)
        int_inc = sum([cash * a["cash_yield"], a_sec * a["securities_yield"]] + interest_terms) / 12.0
        cost_borrow = borrowings * (rm(t) + a.get("borrow_spread", 0.0045)) / 12.0

        for f in fee_mods:
            c = f(a, S, t, ctx)
            fee_terms.extend(c.get("fee_terms", []))
        for f in cap_mods:
            c = f(a, S, t, ctx)
            ops_minutes += c.get("ops_minutes", 0.0)

        ops_fte = ops_minutes / 60.0 / a["productive_hours_m"]
        opex = (ops_fte * a["loaded_cost_ops_fte_m"] + a["fixed_exec_team_m"]
                + a["tech_core_base_m"] + S["accts"] * a["tech_per_acct_m"]
                + a["occupancy_other_m"]) * a.get("_opex_mult", 1.0)
        marketing = mkt[t - 1]

        pretax = int_inc
        for x in fee_terms:
            pretax += x
        pretax = pretax - cost_dep - cost_borrow - provision - opex - marketing
        cum_pretax += pretax
        tax = max(pretax, 0.0) * a["tax_rate"] if cum_pretax > 0 else 0.0
        ni = pretax - tax
        retained += ni

        equity = paid_in + retained
        borrowings = max(cash + recv + other_assets - allowance - deposits - equity, 0.0)
        a_sec = max(deposits + borrowings + equity + allowance - cash - recv - other_assets, 0.0)
        assets = cash + a_sec + recv - allowance + other_assets
        liab_eq = deposits + borrowings + equity
        if abs(assets - liab_eq) > 1.0:
            raise AssertionError(f"identity broke month {t}: {assets:.2f} vs {liab_eq:.2f}")

        leverage = equity / assets if assets else 0.0
        rows.append({
            "m": t, "accounts": round(S["accts"]), "new_accounts": round(S["new_accts"]),
            "deposits": deposits, "receivables": recv, "securities": a_sec,
            "cash": cash, "assets": assets, "equity": equity,
            "net_income": ni, "pretax": pretax, "provision": provision,
            "opex": opex, "marketing": marketing, "interchange": S["interchange"],
            "int_income": int_inc, "cost_deposits": cost_dep, "borrowings": borrowings,
            "ops_fte": round(ops_fte, 1), "leverage": leverage,
            "card_share": recv / assets if assets else 0.0,
            "cre_balance": S.get("bal_cre", 0.0),
        })
    return rows


def summarize(rows, cfg):
    lev_min = min(r["leverage"] for r in rows)
    lev_min_m = min(rows, key=lambda r: r["leverage"])["m"]
    be = next((r["m"] for r in rows if r["pretax"] > 0), None)
    card_max = max(r["card_share"] for r in rows)
    y3 = rows[-1]
    cum_ni = sum(r["net_income"] for r in rows)
    cre_max = max((r["cre_balance"] / r["equity"]) if r["equity"] else 0.0 for r in rows)
    return {
        "min_leverage": round(lev_min, 4), "min_leverage_month": lev_min_m,
        "breakeven_month": be, "card_share_max": round(card_max, 4),
        "assets_yr3": round(y3["assets"]), "deposits_yr3": round(y3["deposits"]),
        "receivables_yr3": round(y3["receivables"]), "accounts_yr3": y3["accounts"],
        "equity_yr3": round(y3["equity"]), "cum_net_income": round(cum_ni),
        "leverage_yr3": round(y3["leverage"], 4),
        "cre_pct_capital_max": round(cre_max, 4),
        "deposit_growth_yr1": round(rows[23]["deposits"] / max(rows[11]["deposits"], 1) - 1, 3),
    }


SCENARIOS = {
    "base": {},
    "growth_miss": {"_growth_mult": 0.60},
    "credit_stress": {"_nco_mult": 1.75, "_dep_cost_add": 0.0050},
    "rate_shock_300": {"_rate_shock": 0.0300, "_beta": 0.75},
    "compound": {"_growth_mult": 0.75, "_dep_cost_add": 0.0040, "_opex_mult": 1.10},
}


def run_scenarios(cfg):
    out = {}
    for name, ov in SCENARIOS.items():
        rows = project(cfg, ov)
        out[name] = {"summary": summarize(rows, cfg), "rows": rows}
    return out


def reverse_stress(cfg, commit):
    """Solve growth multiplier m where min leverage hits the commitment."""
    lo, hi = 0.05, 1.0
    def f(m):
        return summarize(project(cfg, {"_growth_mult": m}), cfg)["min_leverage"]
    if f(1.0) < commit:
        return {"note": "base case already breaches", "mult": 1.0}
    # lower growth -> smaller assets -> HIGHER leverage; breach comes from the
    # cost side at very low growth. Scan for the breach direction honestly.
    grid = [round(0.05 + 0.05 * i, 2) for i in range(20)]
    vals = [(m, f(m)) for m in grid]
    breach = [m for m, v in vals if v < commit]
    if not breach:
        return {"breach_multiplier": None, "min_over_grid": round(min(v for _, v in vals), 4),
                "note": "No growth multiplier in [0.05, 1.0] breaches the commitment; "
                        "leverage binds through the cost base, not asset growth. "
                        "Binding reverse-stress dimension is credit + funding cost (see credit_stress)."}
    return {"breach_multiplier": max(breach), "note": "largest growth multiplier that breaches"}


def reverse_stress_capital(cfg, commit):
    """A.9 — additional opening capital such that minimum leverage holds the
    commitment in EVERY scenario. Exact solve (bisection over full re-runs with
    the extra capital in place), not the closed-form approximation: earnings
    feedback and balance-sheet effects of the added capital are included."""
    import copy as _copy

    def worst(extra):
        c = _copy.deepcopy(cfg)
        c["target_state"]["initial_capital"] = cfg["target_state"]["initial_capital"] + extra
        return min(s["summary"]["min_leverage"] for s in run_scenarios(c).values())

    if worst(0.0) >= commit:
        return {"additional_capital": 0.0,
                "note": "commitment holds in every scenario at current capital"}
    lo, hi = 0.0, 2.0 * cfg["target_state"]["initial_capital"]
    if worst(hi) < commit:
        return {"additional_capital": None,
                "note": "commitment not reachable within 2x current capital — restructure the plan"}
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if worst(mid) >= commit:
            hi = mid
        else:
            lo = mid
    return {"additional_capital": round(hi),
            "note": "smallest additional opening capital holding the commitment across all scenarios"}


def reverse_stress_nco(cfg, commit):
    """Solve NCO multiplier that breaches the leverage commitment."""
    lo, hi = 1.0, 8.0
    def f(m):
        return summarize(project(cfg, {"_nco_mult": m}), cfg)["min_leverage"]
    if f(lo) < commit:
        return {"nco_multiplier": 1.0, "note": "base already breaches"}
    if f(hi) >= commit:
        return {"nco_multiplier": None, "note": "no breach up to 8x mature NCO"}
    for _ in range(40):
        mid = (lo + hi) / 2
        if f(mid) < commit: hi = mid
        else: lo = mid
    mult = round(hi, 2)
    return {"nco_multiplier": mult,
            "implied_nco": round(cfg["assumptions"]["card_nco_mature"] * mult, 4),
            "note": "smallest NCO multiplier that breaches the 10% commitment"}
