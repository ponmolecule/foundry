"""Foundry v2 — challenge layer for balance-driven configurations (A.11, A.12).

Reasonableness bands (two-sided where a de novo book can be suspiciously good),
pricing and funding checks, originate-to-sell sanity, and coupled-inconsistency
rules: assumptions that are individually defensible but jointly implausible.

Flags are deterministic functions of the configuration and the Q1 rate context.
Severity: 'severe' (examiners will challenge or the plan is inconsistent) or
'mild' (worth support in the assumption book).
"""
from .engine_q_a import rate_fn, _prod_rate

# canonical loan types from either predecessor's line vocabulary
_LINE_TYPE = {
    "loanCommercial": "commercial", "Loans: Commercial & Industrial": "commercial",
    "Loans: Commercial Real Estate": "commercial",
    "loanConsumer": "consumer", "Loans: Consumer": "consumer",
    "loanCreditCard": "credit_card", "Loans: Credit Cards": "credit_card",
    "Loans: Credit Card": "credit_card",
    "loanMortgage": "mortgage", "Loans: 1–4 Family Residential": "mortgage",
    "Loans: 1-4 Family Residential": "mortgage",
    "loanOther": "other", "Loans: Lease Financing": "other", "Loans: Other": "other",
}
_DDA_LINES = {"depDDA", "Deposits: Demand (DDA)", "Deposits: Transaction (DDA)"}

# two-sided annual net charge-off bands by loan type (decimals)
CO_BANDS = {
    "commercial": (0.0005, 0.030),
    "consumer": (0.0050, 0.080),
    "credit_card": (0.0150, 0.100),
    "mortgage": (0.0002, 0.015),
    "other": (0.0, 0.080),
}


def _flag(flags, fid, sev, text):
    flags.append({"id": fid, "sev": sev, "text": text})


def challenge_config(cfg):
    a = cfg["assumptions"]
    rate = rate_fn(a["rate_path_q"], a["rate_path_longer_run"])
    lend = a.get("lending_products") or []
    dep = a.get("deposit_products") or []
    flags = []

    # ---- pricing & credit bands, per lending product ----
    for p in lend:
        nm = p.get("name", "<?>")
        ltype = _LINE_TYPE.get(p.get("call_report_line", ""), "other")
        lo, hi = CO_BANDS[ltype]
        co = p.get("charge_off_ann") or 0.0
        y1 = _prod_rate(p, 1, rate)
        if co > hi:
            _flag(flags, "BAND-CO-HI", "severe",
                  f"{nm}: {co:.1%} annual charge-offs is above the typical range for "
                  f"{ltype.replace('_', ' ')} loans (~{lo:.2%}–{hi:.1%}). Examiners will challenge "
                  f"this or the pricing that supports it.")
        elif co < lo and (p.get("opening_balance") or 0) + (p.get("originations_q") or 0) > 0:
            _flag(flags, "BAND-CO-LO", "mild",
                  f"{nm}: {co:.2%} annual charge-offs is below the typical range for "
                  f"{ltype.replace('_', ' ')} loans (~{lo:.2%}–{hi:.1%}). A de novo book with no "
                  f"seasoning rarely outperforms industry loss experience.")
        if y1 > 0.25:
            _flag(flags, "PRICE-USURY", "severe",
                  f"{nm}: {y1:.1%} yield is at or above typical state usury thresholds and will "
                  f"draw fair-lending and UDAAP scrutiny.")
        elif 0 < y1 < 0.02:
            _flag(flags, "PRICE-LOWYIELD", "mild",
                  f"{nm}: {y1:.2%} yield is below any plausible funding cost — check the input.")
        rr = p.get("reserve_rate_pct_bal")
        if rr is not None and p.get("measurement") != "fair_value" and rr < co / 2:
            _flag(flags, "RES-THIN", "mild",
                  f"{nm}: ALLL reserve rate ({rr:.2%} of balance) looks thin relative to the "
                  f"assumed {co:.1%} annual charge-off rate.")
        pr = p.get("provision_rate_ann")
        if pr is not None and pr < co:
            _flag(flags, "PROV-BELOW-CO", "mild",
                  f"{nm}: provisioning ({pr:.2%}) below charge-offs ({co:.2%}) — the entity ALLL "
                  f"floor true-up will absorb the gap; support the release in the assumption book.")
        mb = p.get("mortgage_banking")
        if mb and (mb.get("sale_pct_of_orig") or 0) > 0:
            gm = mb.get("gain_on_sale_margin") or 0.0
            if gm < 0:
                _flag(flags, "GOS-MARGIN-NEG", "severe",
                      f"{nm}: negative gain-on-sale margin — the plan sells loans at a loss every quarter.")
            elif gm > 0.04:
                _flag(flags, "GOS-MARGIN-HI", "mild",
                      f"{nm}: {gm:.2%} gain-on-sale margin is above typical secondary-market execution "
                      f"(~0.5–4%). Examiners will ask for investor commitments supporting it.")
            if (mb.get("warehouse_hold_q") or 0) >= 3:
                _flag(flags, "GOS-WAREHOUSE", "mild",
                      f"{nm}: a {mb['warehouse_hold_q']}-quarter warehouse period is long for held-for-sale "
                      f"loans — confirm the pipeline funding plan.")
            if (mb.get("servicing_retained_pct") or 0) > 0:
                if (mb.get("msr_cap_rate_pct_upb") or 0) > 0.02:
                    _flag(flags, "MSR-CAP", "mild",
                          f"{nm}: MSR capitalization of {mb['msr_cap_rate_pct_upb']:.2%} of UPB is rich — "
                          f"typical agency servicing runs ~0.8–1.5%. A third-party MSR valuation will be expected.")
                fee = mb.get("servicing_fee_bp_ann") or 0.0
                if fee > 50 or (0 < fee < 12.5):
                    _flag(flags, "MSR-FEE", "mild",
                          f"{nm}: {fee:g}bp servicing fee is outside the typical 12.5–50bp range.")

    # ---- funding checks, per deposit product ----
    for p in dep:
        nm = p.get("name", "<?>")
        r1 = _prod_rate(p, 1, rate)
        if r1 > 0.055:
            _flag(flags, "FUND-HOT", "severe",
                  f"{nm}: {r1:.2%} rate paid is well above market — reliance on rate-sensitive funding "
                  f"is a classic de novo exam finding.")
        if p.get("call_report_line") in _DDA_LINES and r1 > 0.02:
            _flag(flags, "FUND-DDA", "mild",
                  f"{nm}: paying {r1:.2%} on transaction accounts is unusual — confirm this is intended.")
        if (p.get("growth_q") or 0) > 0.25:
            _flag(flags, "FUND-GROWTH", "mild",
                  f"{nm}: {p['growth_q']:.0%}/quarter deposit growth is aggressive — expect questions "
                  f"about what funds it and what it costs.")

    # ---- blended spread viability ----
    w_y = sum((p.get("opening_balance") or 0) * _prod_rate(p, 1, rate) for p in lend)
    w_l = sum((p.get("opening_balance") or 0) for p in lend)
    w_c = sum((p.get("opening_balance") or 0) * _prod_rate(p, 1, rate) for p in dep)
    w_d = sum((p.get("opening_balance") or 0) for p in dep)
    if w_l > 0 and w_d > 0:
        spread = w_y / w_l - w_c / w_d
        if spread < 0.01:
            _flag(flags, "SPREAD-VIAB", "severe",
                  f"Blended starting loan yield minus blended deposit cost is only {spread:.2%} — "
                  f"the balance sheet cannot cover operating costs at that spread.")

    # ---- coupled-inconsistency rules (A.12): jointly implausible ----
    if w_d > 0:
        wg = sum((p.get("opening_balance") or 0) * (p.get("growth_q") or 0) for p in dep) / w_d
        wc = w_c / w_d
        mkt = rate(1)
        if wg > 0.08 and wc < mkt - 0.0075:
            _flag(flags, "COUPLED-01", "severe",
                  f"Deposit growth of {wg:.1%}/quarter is claimed jointly with a blended deposit cost "
                  f"{mkt - wc:.2%} below the market rate. Cheap AND fast funding is the classic de novo "
                  f"contradiction — provide channel evidence supporting both, or relax one.")
    for p in lend:
        ltype = _LINE_TYPE.get(p.get("call_report_line", ""), "other")
        lo, _hi = CO_BANDS[ltype]
        y1 = _prod_rate(p, 1, rate)
        co = p.get("charge_off_ann") or 0.0
        if y1 > 0.12 and co < lo:
            _flag(flags, "COUPLED-02", "severe",
                  f"{p.get('name', '<?>')}: prices at {y1:.1%} (risk-based pricing) while assuming "
                  f"{co:.2%} charge-offs, below the bottom of the typical range. The yield implies a "
                  f"borrower population the loss rate denies.")

    return flags
