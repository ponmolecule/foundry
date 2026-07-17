"""Foundry v2 — quarterly balance-driven projection engine, profile A semantics.

Balance-driven product instances (deposits, lending, OBS) projected over a
12-quarter horizon with: forward rate path (fixed/floating pricing), reserve-
maintenance ALLL, originate-to-sell warehouse cohorts with MSR capitalization,
fair-value election via DCF, NOL-carryforward taxation, an iteratively solved
funding waterfall with a cash floor, and downturn overlay scenarios.

Deterministic, fail-closed, dollars in / dollars out. Pure Python.
"""

Q = 12
FV_HORIZON = 60


def rate_fn(path_q, longer_run):
    """Quarterly annual-rate lookup; glides 5bp/qtr toward longer_run past Q12."""
    def r(t):
        if t < 1:
            t = 1
        if t <= Q:
            return path_q[t - 1]
        last = path_q[Q - 1]
        step = 0.0005 * (t - Q)
        if last > longer_run:
            return max(longer_run, last - step)
        return min(longer_run, last + step)
    return r


def _ovq(p, field, q, base):
    m = (p.get("overrides") or {}).get(field) or {}
    v = m.get(str(q))
    return float(v) if v is not None else base


def _prod_rate(p, t, rate):
    if p.get("rate_type") == "float":
        return rate(t) + _ovq(p, "index_spread", t, p.get("index_spread", 0.0) or 0.0)
    if "yield_ann" in p:
        return _ovq(p, "yield_ann", t, p.get("yield_ann") or 0.0)
    return _ovq(p, "rate_paid_ann", t, p.get("rate_paid_ann") or 0.0)


def _fv_of(p, q, bal, rate, is_asset):
    """DCF fair value of the existing book at end of quarter q."""
    if bal <= 0:
        return 0.0
    decay = (p.get("runoff_q", 0.0) if is_asset else p.get("fv_decay_q", 0.10)) or 0.0
    co_rate = (p.get("charge_off_ann", 0.0) / 4.0) if is_asset else 0.0
    b, pv, df = bal, 0.0, 1.0
    for t in range(1, FV_HORIZON + 1):
        rc = _prod_rate(p, q + t, rate) / 4.0
        rd = (rate(q + t) + p.get("discount_spread_ann", 0.0)) / 4.0
        interest = b * rc
        principal = b * decay
        co = b * co_rate
        df /= (1.0 + rd)
        pv += (interest + principal) * df
        b -= (principal + co)
        if b < 1e-7:
            b = 0.0
            break
    pv += b * df
    return pv


def _apply_overlays(lend, dep, a, ov):
    """Downturn overlays: credit multipliers, rate shock, volume/GOS/MSR/sale-share."""
    shock = (ov.get("rate_shock_bp", 0) or 0) / 10000.0
    if shock:
        a["cash_yield"] = max(0.0, a["cash_yield"] + shock)
        a["securities_yield"] = max(0.0, a["securities_yield"] + shock)
        a["borrow_rate_ann"] = max(0.0, a["borrow_rate_ann"] + shock)
        a["rate_path_q"] = [max(0.0, x + shock) for x in a["rate_path_q"]]
        a["rate_path_longer_run"] = max(0.0, a["rate_path_longer_run"] + shock)
    co_m = ov.get("charge_off_mult", 1) or 1
    res_m = ov.get("reserve_mult", 1) or 1
    for p in lend:
        p["charge_off_ann"] = (p.get("charge_off_ann") or 0.0) * co_m
        if p.get("reserve_rate_pct_bal") is not None:
            p["reserve_rate_pct_bal"] *= res_m
        p["originations_q"] = (p.get("originations_q") or 0.0) * (1 - (ov.get("origination_volume_haircut", 0) or 0))
        mb = p.get("mortgage_banking")
        if mb:
            mb["gain_on_sale_margin"] *= (1 - (ov.get("gos_margin_compression", 0) or 0))
            mb["msr_cap_rate_pct_upb"] *= (1 - (ov.get("msr_value_haircut", 0) or 0))
            mb["sale_pct_of_orig"] *= (1 - (ov.get("sale_share_retention_shift", 0) or 0))


def run_pf_a(cfg):
    a = {k: (list(v) if isinstance(v, list) else v) for k, v in cfg["assumptions"].items()}
    import copy
    lend = copy.deepcopy(a.get("lending_products") or [])
    dep = copy.deepcopy(a.get("deposit_products") or [])
    obs = copy.deepcopy(a.get("obs_exposures") or [])
    afs_p = copy.deepcopy(a.get("securities_afs") or [])
    htm_p = copy.deepcopy(a.get("securities_htm") or [])
    ov = cfg.get("scenario_overlays")
    if ov:
        _apply_overlays(lend, dep, a, ov)
    rate = rate_fn(a["rate_path_q"], a["rate_path_longer_run"])

    capital = cfg["target_state"]["initial_capital"]
    # staged capital raises (additive, default-off): raises land at the START
    # of their stated quarter; the waterfall absorbs the cash side via plug()
    _raises = cfg["assumptions"].get("capital_raises") or []
    cap_t = [capital] * 13
    for _r in _raises:
        for _q in range(int(_r["quarter"]), 13):
            cap_t[_q] += float(_r["amount"])
    non_earn = a["premises_equipment"] + a["intangibles"] + a["other_assets"]
    cash_floor = a["cash_target_pct_deposits"]
    other_liab = a["other_liabilities"]

    # deliberate securities books (A.6): balance path with purchases and runoff;
    # HTM income at its own fixed coupon — the rate shock (applied above to the
    # path and treasury yields) does not touch it. That is what HTM means.
    for p in afs_p + htm_p:
        bal = [p.get("opening", 0.0) or 0.0]
        for _q in range(1, Q + 1):
            bal.append(max(0.0, bal[-1] * (1 + (p.get("growth_q") or 0.0) - (p.get("runoff_q") or 0.0))
                           + (p.get("purchases_q") or 0.0)))
        p["_bal"] = bal
        p["_avg"] = [None] + [(bal[i - 1] + bal[i]) / 2.0 for i in range(1, Q + 1)]

    # ---- per-product projection ----
    for p in lend + dep + obs:
        p["_bal"] = [p.get("opening_balance", p.get("notional", 0.0)) or 0.0]
        p["_avg"] = [None]
        p["_ii"] = [None]; p["_ie"] = [None]; p["_fee"] = [None]; p["_ox"] = [None]
    for p in lend:
        p["_co"] = [None]; p["_alll"] = [0.0]; p["_orig"] = [None]
        p["_sold"] = [0.0]; p["_wh"] = [0.0]; p["_whc"] = [0.0]; p["_gos"] = [None]
        p["_upb"] = [0.0]; p["_msr"] = [0.0]; p["_scap"] = [None]; p["_samort"] = [None]
        p["_sfee"] = [None]; p["_snet"] = [None]
        p["_is_fv"] = p.get("measurement") == "fair_value"
        mb = p.get("mortgage_banking") or {}
        p["_sale"] = mb.get("sale_pct_of_orig", 0.0) or 0.0
        p["_alll"][0] = 0.0 if p["_is_fv"] else p["_bal"][0] * (p.get("reserve_rate_pct_bal") or 0.0)

    for p in dep + obs:
        for q in range(1, Q + 1):
            beg = p["_bal"][q - 1]
            end = max(0.0, beg * (1 + _ovq(p, "growth_q", q, p.get("growth_q") or 0.0)
                                  - _ovq(p, "runoff_q", q, p.get("runoff_q") or 0.0)))
            avg = (beg + end) / 2.0
            r = _prod_rate(p, q, rate) if "rate_type" in p else 0.0
            p["_bal"].append(end); p["_avg"].append(avg)
            p["_ii"].append(0.0)
            p["_ie"].append(avg * r / 4.0 if p in dep else 0.0)
            p["_fee"].append(avg * (p.get("fee_yield_ann") or 0.0) / 4.0)
            p["_ox"].append(avg * (p.get("opex_pct_ann") or 0.0) / 4.0 + (p.get("opex_fixed_m") or 0.0) * 3.0)

    for p in lend:
        mb = p.get("mortgage_banking") or {}
        h = int(mb.get("warehouse_hold_q", 0) or 0)
        for q in range(1, Q + 1):
            beg = p["_bal"][q - 1]
            r = _prod_rate(p, q, rate)
            co = beg * _ovq(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0) / 4.0
            o = _ovq(p, "originations_q", q,
                     (p.get("originations_q") or 0.0) * (1 + (p.get("orig_growth_q") or 0.0)) ** (q - 1))
            retained = o * (1 - p["_sale"])
            p["_sold"].append(o * p["_sale"])
            end = max(0.0, beg + retained - beg * _ovq(p, "runoff_q", q, p.get("runoff_q") or 0.0) - co)
            avg = (beg + end) / 2.0
            p["_bal"].append(end); p["_avg"].append(avg); p["_co"].append(co); p["_orig"].append(o)
            p["_ii"].append(avg * r / 4.0); p["_ie"].append(0.0)
            p["_fee"].append(avg * _ovq(p, "fee_yield_ann", q, p.get("fee_yield_ann") or 0.0) / 4.0)
            p["_ox"].append(avg * (p.get("opex_pct_ann") or 0.0) / 4.0 + (p.get("opex_fixed_m") or 0.0) * 3.0)
            p["_alll"].append(0.0 if p["_is_fv"] else end * (p.get("reserve_rate_pct_bal") or 0.0))
        # warehouse cohorts: half-quarter coupon at origination and sale
        if p["_sale"] > 0:
            margin = mb.get("gain_on_sale_margin", 0.0) or 0.0
            for q in range(1, Q + 1):
                wh, wh_int, gos = 0.0, 0.0, 0.0
                rq = _prod_rate(p, q, rate)
                for j in range(max(1, q - h), q + 1):
                    cohort = p["_sold"][j]
                    if not cohort:
                        continue
                    if h == 0:
                        w = 0.5 if j == q else 0.0
                    elif j == q:
                        w = 0.5
                    elif q < j + h:
                        w = 1.0
                    elif q == j + h:
                        w = 0.5
                    else:
                        w = 0.0
                    wh_int += cohort * w * rq / 4.0
                    if q < j + h:
                        wh += cohort
                if p["_is_fv"]:
                    gos = p["_sold"][q] * margin
                elif q - h >= 1:
                    gos = p["_sold"][q - h] * margin
                p["_wh"].append(wh)
                p["_whc"].append(wh * (1 + (margin if p["_is_fv"] else 0.0)))
                p["_ii"][q] += wh_int
                p["_gos"].append(gos)
        else:
            for q in range(1, Q + 1):
                p["_wh"].append(0.0); p["_whc"].append(0.0); p["_gos"].append(0.0)
        # servicing retained: MSR capitalized at settlement, amortized on decay
        srv = mb.get("servicing_retained_pct", 0.0) or 0.0
        if p["_sale"] > 0 and srv > 0:
            fee_bp = mb.get("servicing_fee_bp_ann", 0.0) or 0.0
            cap_rate = mb.get("msr_cap_rate_pct_upb", 0.0) or 0.0
            decay = mb.get("msr_decay_q", 0.0) or 0.0
            for q in range(1, Q + 1):
                settled = p["_sold"][q - h] if q - h >= 1 else 0.0
                add = settled * srv
                upb_beg = p["_upb"][q - 1]
                upb = max(0.0, upb_beg - upb_beg * decay + add)
                cap = add * cap_rate
                amort = p["_msr"][q - 1] * decay
                msr = max(0.0, p["_msr"][q - 1] + cap - amort)
                sfee = ((upb_beg + upb) / 2.0) * fee_bp / 10000.0 / 4.0
                p["_upb"].append(upb); p["_msr"].append(msr)
                p["_scap"].append(cap); p["_samort"].append(amort)
                p["_sfee"].append(sfee); p["_snet"].append(sfee - amort)
                p["_gos"][q] += cap
        else:
            for q in range(1, Q + 1):
                p["_upb"].append(0.0); p["_msr"].append(0.0)
                p["_scap"].append(0.0); p["_samort"].append(0.0)
                p["_sfee"].append(0.0); p["_snet"].append(0.0)
        # fair value of the existing book
        p["_fv"] = []; p["_fvadj"] = []
        for q in range(0, Q + 1):
            if p["_is_fv"]:
                fv = _fv_of(p, q, p["_bal"][q], rate, True)
                p["_fv"].append(fv); p["_fvadj"].append(fv - p["_bal"][q])
            else:
                p["_fv"].append(None); p["_fvadj"].append(0.0)

    # ---- aggregation ----
    def z():
        return [0.0] * (Q + 1)
    gross, alll_t, hfs, msr_t, deps_c, deps_b, obs_n = z(), z(), z(), z(), z(), z(), z()
    for q in range(0, Q + 1):
        for p in lend:
            carry = p["_bal"][q] + (p["_fvadj"][q] if p["_is_fv"] else 0.0)
            gross[q] += carry + p["_whc"][q]
            alll_t[q] += p["_alll"][q]
            hfs[q] += p["_whc"][q]
            msr_t[q] += p["_msr"][q]
        for p in dep:
            deps_c[q] += p["_bal"][q]
            deps_b[q] += p["_bal"][q]
        for p in obs:
            obs_n[q] += p["_bal"][q]

    def plug(dep_carry, dep_bal, net_loans_end, equity_end, msr_end, sec_books_end=0.0):
        funding = dep_carry + other_liab + equity_end
        investable = funding - net_loans_end - non_earn - msr_end - sec_books_end
        req_cash = cash_floor * dep_bal
        if investable >= req_cash:
            return req_cash, investable - req_cash, 0.0
        return req_cash, 0.0, req_cash - investable

    day_one = sum(p["_fvadj"][0] for p in lend if p["_is_fv"])
    # pre-opening burn (Patrick I.9 convention, quarterly-converted at import):
    # organizational costs are EXPENSED into the opening deficit, not capitalized
    _po = cfg.get("pre_opening") or {}
    _burn = sum(float(e.get("total", 0.0)) for e in (_po.get("expenses") or []))
    day_one -= _burn
    net0 = gross[0] - alll_t[0]
    equity0 = capital + day_one
    sec_books0 = sum(p["_bal"][0] for p in afs_p + htm_p)
    c0, s0, b0 = plug(deps_c[0], deps_b[0], net0, equity0, 0.0, sec_books0)

    bs = {k: z() for k in ("cash", "sec", "netLoans", "borrow", "equity", "re", "totalAssets")}
    bs["cash"][0], bs["sec"][0], bs["borrow"][0] = c0, s0, b0
    bs["netLoans"][0], bs["re"][0], bs["equity"][0] = net0, day_one, equity0
    bs["totalAssets"][0] = c0 + s0 + sec_books0 + net0 + non_earn

    isk = ("loanInt", "secInt", "bookInt", "cashInt", "depExp", "borrExp", "nii", "prov", "fees",
           "gos", "servNet", "fvPnl", "prodOpex", "overhead", "pretax", "tax", "ni", "nco", "nol")
    is_ = {k: [None] * (Q + 1) for k in isk}

    re, nol = day_one, 0.0
    for q in range(1, Q + 1):
        loan_int = sum(p["_ii"][q] for p in lend)
        dep_exp = sum(p["_ie"][q] for p in dep)
        fees = sum(p["_fee"][q] for p in lend + dep + obs)
        prod_ox = sum(p["_ox"][q] for p in lend + dep + obs)
        nco = sum(p["_co"][q] for p in lend)
        gos = sum(p["_gos"][q] for p in lend)
        srv = sum(p["_snet"][q] for p in lend)
        fv_pnl = sum((p["_fvadj"][q] - p["_fvadj"][q - 1]) - p["_co"][q] for p in lend if p["_is_fv"])
        overhead = a["overhead_q"] * (1 + a.get("overhead_growth_q", 0.0)) ** (q - 1)
        nie = prod_ox + overhead
        nco_ac = sum(p["_co"][q] for p in lend if not p["_is_fv"])
        prov = (alll_t[q] - alll_t[q - 1]) + nco_ac
        net_loans_end = gross[q] - alll_t[q]
        sec_books_end = sum(p["_bal"][q] for p in afs_p + htm_p)
        book_int = sum(p["_avg"][q] * (p.get("yield_ann") or 0.0) / 4.0 for p in afs_p + htm_p)
        beg_c, beg_s, beg_b = bs["cash"][q - 1], bs["sec"][q - 1], bs["borrow"][q - 1]

        ni = 0.0
        for _ in range(60):
            equity_end = cap_t[q] + re + ni
            c, s, b = plug(deps_c[q], deps_b[q], net_loans_end, equity_end, msr_t[q], sec_books_end)
            sec_int = ((beg_s + s) / 2.0) * a["securities_yield"] / 4.0 + book_int
            cash_int = ((beg_c + c) / 2.0) * a["cash_yield"] / 4.0
            borr_exp = ((beg_b + b) / 2.0) * a["borrow_rate_ann"] / 4.0
            nii = loan_int + sec_int + cash_int - dep_exp - borr_exp
            pretax = nii + fees + fv_pnl + gos + srv - nie - prov
            taxable = max(0.0, pretax - nol)
            tax = taxable * a["tax_rate"]
            new_ni = pretax - tax
            if abs(new_ni - ni) < 1e-4:
                ni = new_ni
                break
            ni = new_ni
        if pretax < 0:
            nol += -pretax
        else:
            nol = max(0.0, nol - pretax)
        re += ni

        bs["cash"][q], bs["sec"][q], bs["borrow"][q] = c, s, b
        bs["netLoans"][q], bs["re"][q], bs["equity"][q] = net_loans_end, re, cap_t[q] + re
        bs["totalAssets"][q] = c + s + sec_books_end + net_loans_end + non_earn + msr_t[q]
        for k, v in (("loanInt", loan_int), ("secInt", sec_int), ("bookInt", book_int), ("cashInt", cash_int),
                     ("depExp", dep_exp), ("borrExp", borr_exp), ("nii", nii), ("prov", prov),
                     ("fees", fees), ("gos", gos), ("servNet", srv), ("fvPnl", fv_pnl),
                     ("prodOpex", prod_ox), ("overhead", overhead), ("pretax", pretax),
                     ("tax", tax), ("ni", ni), ("nco", nco), ("nol", nol)):
            is_[k][q] = v

    # ---- ratios (A.7): Tier 1 approx = equity - intangibles - MSA excess over the
    # 25%-of-Tier-1 threshold (12 CFR 3.22(d) simplification); deducted MSAs also
    # come out of average assets in the leverage denominator. ----
    ratios = {k: [None] * (Q + 1) for k in ("roa", "roe", "nim", "eff", "lev", "alllPct")}
    for q in range(1, Q + 1):
        avg_a = (bs["totalAssets"][q - 1] + bs["totalAssets"][q]) / 2.0
        avg_e = (bs["equity"][q - 1] + bs["equity"][q]) / 2.0
        avg_earn = ((gross[q - 1] + gross[q]) / 2.0 + (bs["sec"][q - 1] + bs["sec"][q]) / 2.0
                    + (bs["cash"][q - 1] + bs["cash"][q]) / 2.0)
        ni_q = is_["ni"][q]
        ratios["roa"][q] = (ni_q * 4 / avg_a * 100) if avg_a > 0 else None
        ratios["roe"][q] = (ni_q * 4 / avg_e * 100) if avg_e > 0 else None
        ratios["nim"][q] = (is_["nii"][q] * 4 / avg_earn * 100) if avg_earn > 0 else None
        rev = is_["nii"][q] + is_["fees"][q] + is_["gos"][q] + is_["servNet"][q]
        ratios["eff"][q] = ((is_["prodOpex"][q] + is_["overhead"][q]) / rev * 100) if rev > 0 else None
        t1 = bs["equity"][q] - a["intangibles"]
        msr_x = max(0.0, msr_t[q] - 0.25 * max(0.0, t1))
        ratios["lev"][q] = ((t1 - msr_x) / (avg_a - msr_x) * 100) if (avg_a - msr_x) > 0 else None
        ratios["alllPct"][q] = (alll_t[q] / gross[q] * 100) if gross[q] > 0 else None

    products = []
    for fam, plist in (("lending", lend), ("deposit", dep), ("obs", obs)):
        for p in plist:
            def _s(key):
                return [p[key][q] for q in range(1, Q + 1)] if p.get(key) else None
            products.append({
                "name": p.get("name"), "family": fam,
                "line": p.get("call_report_line"),
                "rate_type": p.get("rate_type", "fixed"),
                "index_spread": p.get("index_spread"),
                "is_fv": bool(p.get("_is_fv")),
                "sale_pct": p.get("_sale", 0.0),
                "serv_retained": (p.get("mortgage_banking") or {}).get("servicing_retained_pct", 0.0) if fam == "lending" else 0.0,
                "bal": [(p["_bal"][q] + (p["_fvadj"][q] if p.get("_is_fv") else 0.0)
                         if fam == "lending" else p["_bal"][q]) for q in range(0, Q + 1)],
                "rateQ": [_prod_rate(p, q, rate) * 100 for q in range(1, Q + 1)] if fam != "obs" else None,
                "intInc": _s("_ii"), "intExp": _s("_ie"),
                "origq": _s("_orig"), "soldOrig": _s("_sold"), "whCarry": _s("_whc"),
                "servUPB": _s("_upb"), "msrCap": _s("_scap"), "msrAmort": _s("_samort"),
                "msrBal": _s("_msr"), "alll": _s("_alll"),
                "fv": ([p["_fv"][q] for q in range(1, Q + 1)] if p.get("_is_fv") else None),
                "fvAdj": ([p["_fvadj"][q] for q in range(1, Q + 1)] if p.get("_is_fv") else None),
                "avg": [p["_avg"][q] for q in range(1, Q + 1)],
                "interest": [(p["_ii"][q] - p["_ie"][q]) for q in range(1, Q + 1)],
                "fees": [p["_fee"][q] for q in range(1, Q + 1)],
                "opex": [p["_ox"][q] for q in range(1, Q + 1)],
                "co": [(p["_co"][q] if "_co" in p else 0.0) for q in range(1, Q + 1)],
                "gos": [(p["_gos"][q] if p.get("_gos") else 0.0) for q in range(1, Q + 1)],
                "servNet": [(p["_snet"][q] if p.get("_snet") else 0.0) for q in range(1, Q + 1)],
                "ftp_rate": [rate(q) for q in range(1, Q + 1)],
            })
    return {"products": products,
            "ratios": {k: v[1:] for k, v in ratios.items()},
            "bs": {"cash": bs["cash"], "sec": bs["sec"], "netLoans": bs["netLoans"],
                   "grossLoans": gross, "alll": alll_t, "hfs": hfs, "msr": msr_t,
                   "borrow": bs["borrow"], "deposits": deps_c, "equity": bs["equity"],
                   "re": bs["re"], "totalAssets": bs["totalAssets"]},
            "is": {k: v[1:] for k, v in is_.items()}}
