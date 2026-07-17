"""Foundry v2 — quarterly balance-driven projection engine, profile B semantics.

Distinctives vs profile A: per-period override vectors on any driver; deliberate
AFS and HTM securities books plus a surplus-liquidity sweep (HTM never reprices);
expected-loss provisioning separate from charge-offs with an entity ALLL floor
true-up; beginning-of-quarter accrual on treasury balances; taxes on positive
pre-tax income only (no DTA). Deterministic, dollars in / dollars out.
"""

Q = 12


def _ov(p, field, q, base):
    """1-based per-quarter override lookup; blank -> baseline."""
    m = (p.get("overrides") or {}).get(field) or {}
    v = m.get(str(q))
    return float(v) if v is not None else base


def run_pf_b(cfg):
    import copy
    a = cfg["assumptions"]
    lend = copy.deepcopy(a.get("lending_products") or [])
    dep = copy.deepcopy(a.get("deposit_products") or [])
    obs = copy.deepcopy(a.get("obs_exposures") or [])
    afs_p = copy.deepcopy(a.get("securities_afs") or [])
    htm_p = copy.deepcopy(a.get("securities_htm") or [])

    capital = cfg["target_state"]["initial_capital"]
    _raises = cfg["assumptions"].get("capital_raises") or []
    cap_t = [capital] * 13
    for _r in _raises:
        for _q in range(int(_r["quarter"]), 13):
            cap_t[_q] += float(_r["amount"])
    non_earn = a["premises_equipment"] + a["intangibles"] + a["other_assets"]
    other_liab = a["other_liabilities"]
    alloc = a["sweep_securities_alloc"]
    floor_pct = a["alll_floor_pct_loans"]

    # ---- product projections ----
    def project(p, is_lend):
        beg, end, avg = [], [], []
        b = p.get("opening_balance", p.get("opening", p.get("notional", 0.0))) or 0.0
        for q in range(1, Q + 1):
            beg.append(b)
            runoff = _ov(p, "runoff_q", q, p.get("runoff_q") or 0.0)
            if is_lend and p.get("volume_mode") == "originations":
                e = max(0.0, b * (1 - runoff) + _ov(p, "originations_q", q, p.get("originations_q") or 0.0))
            else:
                e = max(0.0, b * (1 + _ov(p, "growth_q", q, p.get("growth_q") or 0.0) - runoff)
                        + (p.get("purchases_q") or 0.0))
            end.append(e)
            avg.append((b + e) / 2.0)
            b = e
        p["_beg"], p["_end"], p["_avg"] = beg, end, avg

    for p in lend:
        project(p, True)
    for p in dep + obs + afs_p + htm_p:
        project(p, False)

    gl0 = sum(p["_beg"][0] for p in lend)
    alll = gl0 * floor_pct
    _po = cfg.get("pre_opening") or {}
    _burn = sum(float(e.get("total", 0.0)) for e in (_po.get("expenses") or []))
    re = -_burn                      # organizational costs: opening deficit in RE
    equity = capital + re
    _aoci_sens = float(a.get("aoci_sensitivity_annual") or 0.0)
    aoci_cum = 0.0

    def plug(gross_end, alll_end, sec_prod_end, dep_end, equity_end):
        uses = gross_end - alll_end + sec_prod_end + non_earn
        liquid = dep_end + other_liab + equity_end - uses
        borrow = 0.0
        if liquid < 0:
            borrow = -liquid
            liquid = 0.0
        return liquid * (1 - alloc), liquid * alloc, borrow

    sec0 = sum(p["_beg"][0] for p in afs_p + htm_p)
    dep0 = sum(p["_beg"][0] for p in dep)
    cash, sweep, borrow = plug(gl0, alll, sec0, dep0, equity)
    prev_assets = cash + sweep + sec0 + (gl0 - alll) + non_earn

    out_bs = {k: [] for k in ("cash", "afs", "htm", "grossLoans", "alll", "netLoans",
                              "deposits", "borrowings", "equity", "retained", "aoci",
                              "paidIn", "totalAssets")}
    out_is = {k: [] for k in ("intLoans", "intSec", "intCash", "intDep", "intBorrow", "nii",
                              "provision", "fees", "opexProd", "fixedOpex", "pretax", "tax",
                              "ni", "chargeoffs")}

    for qi in range(Q):
        q = qi + 1
        int_loans = sum(p["_avg"][qi] * _ov(p, "yield_ann", q, p.get("yield_ann") or 0.0) / 4.0 for p in lend)
        int_sec_prod = sum(p["_avg"][qi] * (p.get("yield_ann") or 0.0) / 4.0 for p in afs_p + htm_p)
        int_sweep = sweep * a["sweep_securities_yield"] / 4.0          # beginning balance
        int_cash = cash * a["cash_yield"] / 4.0                        # beginning balance
        int_dep = sum(p["_avg"][qi] * _ov(p, "rate_paid_ann", q, p.get("rate_paid_ann") or 0.0) / 4.0 for p in dep)
        int_borrow = borrow * a["borrow_rate_ann"] / 4.0               # beginning balance
        nii = int_loans + int_sec_prod + int_sweep + int_cash - int_dep - int_borrow

        fees = sum(p["_avg"][qi] * (p.get("fee_yield_ann") or 0.0) / 4.0 for p in lend + dep + obs + afs_p + htm_p)
        opex_prod = sum((p.get("opex_fixed_m") or 0.0) * 3.0 for p in lend + dep + obs + afs_p + htm_p)
        nie = opex_prod + a["overhead_q"]

        gl_end = sum(p["_end"][qi] for p in lend)
        chargeoffs = sum(p["_avg"][qi] * _ov(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0) / 4.0
                         for p in lend)
        prov_prod = sum(p["_avg"][qi] * (p.get("provision_rate_ann")
                                          if p.get("provision_rate_ann") is not None
                                          else _ov(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0)) / 4.0
                        for p in lend)
        alll_tent = alll - chargeoffs + prov_prod
        floor = gl_end * floor_pct
        true_up = max(0.0, floor - alll_tent)
        provision = prov_prod + true_up
        alll_end = alll_tent + true_up

        pretax = nii + fees - nie - provision
        tax = max(0.0, pretax) * a["tax_rate"]
        ni = pretax - tax
        re += ni
        _afs_end = sum(p["_end"][qi] for p in afs_p) if afs_p else 0.0
        aoci_cum += _afs_end * _aoci_sens / 4.0
        equity_end = cap_t[qi] + re + aoci_cum

        dep_end = sum(p["_end"][qi] for p in dep)
        sec_prod_end = sum(p["_end"][qi] for p in afs_p + htm_p)
        c2, s2, b2 = plug(gl_end, alll_end, sec_prod_end, dep_end, equity_end)
        net_loans = gl_end - alll_end
        afs_end = s2 + sum(p["_end"][qi] for p in afs_p)
        htm_end = sum(p["_end"][qi] for p in htm_p)
        total_assets = c2 + afs_end + htm_end + net_loans + non_earn

        for k, v in (("cash", c2), ("afs", afs_end), ("htm", htm_end), ("grossLoans", gl_end),
                     ("alll", alll_end), ("netLoans", net_loans), ("deposits", dep_end),
                     ("borrowings", b2), ("equity", equity_end), ("retained", re),
                     ("aoci", aoci_cum), ("paidIn", cap_t[qi]),
                     ("totalAssets", total_assets)):
            out_bs[k].append(v)
        for k, v in (("intLoans", int_loans), ("intSec", int_sec_prod + int_sweep),
                     ("intCash", int_cash), ("intDep", int_dep), ("intBorrow", int_borrow),
                     ("nii", nii), ("provision", provision), ("fees", fees),
                     ("opexProd", opex_prod), ("fixedOpex", a["overhead_q"]),
                     ("pretax", pretax), ("tax", tax), ("ni", ni), ("chargeoffs", chargeoffs)):
            out_is[k].append(v)

        alll = alll_end
        cash, sweep, borrow = c2, s2, b2

    out_ratios = {"roa": [], "roe": [], "nim": [], "eff": [], "leverage": []}
    pa, pe = prev_assets, capital
    for qi in range(Q):
        ta, eq, ni = out_bs["totalAssets"][qi], out_bs["equity"][qi], out_is["ni"][qi]
        avg_a, avg_e = (pa + ta) / 2.0, (pe + eq) / 2.0
        out_ratios["roa"].append(ni * 4 / avg_a * 100 if avg_a > 0 else None)
        out_ratios["roe"].append(ni * 4 / avg_e * 100 if avg_e > 0 else None)
        out_ratios["nim"].append(None)  # informational only in profile B fixtures
        rev = out_is["nii"][qi] + out_is["fees"][qi]
        out_ratios["eff"].append((out_is["opexProd"][qi] + out_is["fixedOpex"][qi]) / rev * 100 if rev > 0 else None)
        out_ratios["leverage"].append(eq / ta * 100 if ta > 0 else None)
        pa, pe = ta, eq
    ftp = (a.get("reporting") or {}).get("ftp_benchmark_ann", 0.0)
    products = []
    for fam, plist in (("lending", lend), ("deposit", dep), ("obs", obs)):
        for p in plist:
            def _r(field, dflt_key):
                return [_ov(p, field, qi + 1, p.get(dflt_key) or 0.0) for qi in range(Q)]
            yv = _r("yield_ann", "yield_ann") if fam == "lending" else _r("rate_paid_ann", "rate_paid_ann")
            cov = _r("charge_off_ann", "charge_off_ann")
            products.append({
                "name": p.get("name"), "family": fam,
                "line": p.get("call_report_line"),
                "rate_type": "fixed", "index_spread": None, "is_fv": False,
                "sale_pct": 0.0, "serv_retained": 0.0,
                "rateQ": [v * 100 for v in yv] if fam != "obs" else None,
                "intInc": ([p["_avg"][qi] * yv[qi] / 4.0 for qi in range(Q)] if fam == "lending" else [0.0] * Q),
                "intExp": ([p["_avg"][qi] * yv[qi] / 4.0 for qi in range(Q)] if fam == "deposit" else [0.0] * Q),
                "origq": None, "soldOrig": None, "whCarry": None, "servUPB": None,
                "msrCap": None, "msrAmort": None, "msrBal": None, "alll": None,
                "fv": None, "fvAdj": None,
                "bal": list(p["_end"]),
                "avg": list(p["_avg"]),
                "interest": [p["_avg"][qi] * yv[qi] / 4.0 * (1 if fam == "lending" else -1)
                             for qi in range(Q)] if fam != "obs" else [0.0] * Q,
                "fees": [p["_avg"][qi] * (p.get("fee_yield_ann") or 0.0) / 4.0 for qi in range(Q)],
                "opex": [(p.get("opex_fixed_m") or 0.0) * 3.0] * Q,
                "co": [p["_avg"][qi] * cov[qi] / 4.0 for qi in range(Q)] if fam == "lending" else [0.0] * Q,
                "gos": [0.0] * Q, "servNet": [0.0] * Q,
                "ftp_rate": [ftp] * Q,
            })
    return {"products": products, "bs": out_bs, "is": out_is, "ratios": out_ratios}
