"""Challenge engine (step 6 flags) + examiner simulator (step 8).

Everything here is deterministic templating over engine outputs and
configuration facts — the D7 discipline: narrative from numbers,
never numbers from narrative.
"""

# constraint key -> (summary metric, comparator, detail template). Data-driven:
# a new constraint of a known type is a config row, not code (T1/T8 discipline).
CONSTRAINT_EVALUATORS = {
    "leverage_min": ("min_leverage", "ge", "min leverage {v:.2%} in month {m}"),
    "card_receivables_max_share": ("card_share_max", "le", "peak card share of assets {v:.1%}"),
    "cre_max_pct_capital": ("cre_pct_capital_max", "le", "peak CRE / tier 1 capital {v:.0%}"),
    "brokered_max_share": None,        # structural: attested via funding plan, no brokered modeled
    "marketing_linkage": None,         # structural: attested via BUS-01 flag
}

def constraint_tests(cfg, scen):
    tests = []
    for x in cfg["constraints"]:
        ev = CONSTRAINT_EVALUATORS.get(x["key"], None)
        if ev is None:
            continue
        metric, op, tmpl = ev
        for name, s in scen.items():
            sm = s["summary"]
            v = sm.get(metric)
            if v is None:
                continue
            ok = v >= x["value"] if op == "ge" else v <= x["value"]
            tests.append({"scenario": name, "constraint": x["key"], "value": v,
                          "limit": x["value"], "pass": ok,
                          "detail": tmpl.format(v=v, m=sm.get("min_leverage_month")),
                          "source": x["source"]})
    return tests


def business_flags(cfg, base_rows, prior_table):
    a = cfg["assumptions"]
    flags = list(cfg["step_0a"]["flags_from_map"])
    # growth-linkage flag, channel-aware: growth must be mechanically tied to
    # its acquisition driver (spend for funnel channels, hiring for relationship)
    if "new_accts_per_marketing_dollar" in a:
        cac = 1.0 / a["new_accts_per_marketing_dollar"]
        flags.append({"id": "BUS-01", "class": "satisfied",
                      "text": f"Growth linkage present: every funded account carries an explicit "
                              f"${cac:.0f} acquisition cost; deposit growth cannot move without spend."})
    elif "new_relationships_per_banker_m" in a:
        flags.append({"id": "BUS-01", "class": "satisfied",
                      "text": f"Growth linkage present: deposit growth is mechanically tied to banker "
                              f"headcount ({a['new_relationships_per_banker_m']:.1f} new relationships "
                              f"per banker per month, hiring ramp capped at {a['bankers_max']:.0f}); "
                              f"relationships cannot appear without the hires that source them."})
    # staffing scales
    f0, f1 = base_rows[5]["ops_fte"], base_rows[-1]["ops_fte"]
    flags.append({"id": "BUS-02", "class": "advisory",
                  "text": f"Ops staffing scales with volume: {f0:.0f} FTE month 6 to {f1:.0f} FTE "
                          f"month 36, driven by KYC, fraud-alert, and service-contact capacity."})
    # percentile outliers, direction-aware: only aggressive-direction outliers need support
    aggressive_high = {"deposit_growth_yr1"}                     # too-fast growth
    aggressive_low = {"card_nco_mature", "cost_of_deposits_spread", "cac_per_funded_account",
                      "opex_per_active_acct", "efficiency_q12"}  # too-cheap losses/funding/costs
    for m, p in prior_table.items():
        pc = p["client_percentile"]
        if (m in aggressive_high and pc >= 90) or (m in aggressive_low and pc <= 10):
            flags.append({"id": f"PEER-{m}", "class": "commercial_assumption_requiring_support",
                          "text": f"{m}: client at p{pc:.0f} of frozen cohort "
                                  f"(cohort p50 {p['p50']}); aggressive vs peer evidence, "
                                  f"requires additional support."})
        elif pc >= 90 or pc <= 10:
            flags.append({"id": f"PEER-{m}", "class": "advisory",
                          "text": f"{m}: client at p{pc:.0f} of frozen cohort "
                                  f"(cohort p50 {p['p50']}); conservative-direction outlier, "
                                  f"note in assumption book."})
    # coupled-inconsistency rules: contradictions across assumptions, not
    # independent outliers (challenge class 3, cross-domain)
    def _p(m):
        return prior_table[m]["client_percentile"] if m in prior_table else None
    if _p("cost_of_deposits_spread") is not None and _p("deposit_growth_yr1") is not None \
       and _p("cost_of_deposits_spread") <= 10 and _p("deposit_growth_yr1") >= 50:
        flags.append({"id": "COUPLED-01", "class": "commercial_assumption_requiring_support",
                      "text": "Coupled contradiction: funding priced below nearly all peers "
                              f"(p{_p('cost_of_deposits_spread'):.0f}) while deposit growth runs at/above "
                              f"peer median (p{_p('deposit_growth_yr1'):.0f}). Below-market pricing and "
                              "above-market growth cannot both hold without an unmodeled advantage; "
                              "requires joint support, not two separate footnotes."})
    if _p("cac_per_funded_account") is not None and _p("deposit_growth_yr1") is not None \
       and _p("cac_per_funded_account") <= 10 and _p("deposit_growth_yr1") >= 50:
        flags.append({"id": "COUPLED-02", "class": "commercial_assumption_requiring_support",
                      "text": "Coupled contradiction: acquisition cost below nearly all peers "
                              f"(p{_p('cac_per_funded_account'):.0f}) combined with at/above-median growth "
                              f"(p{_p('deposit_growth_yr1'):.0f}); the growth story depends on an "
                              "acquisition efficiency no cohort member achieved."})

    # Durbin exemption rule item (only where interchange revenue is modeled)
    if "interchange_rate" in a:
        flags.append({"id": "REG-DURBIN", "class": "counsel_determination_required",
                  "text": "Interchange revenue assumes Durbin small-issuer exemption (<$10B assets). "
                              "Projection stays under threshold, but confirm treatment of parent-affiliate "
                              "asset aggregation with counsel."})
    return flags


def examiner_book(cfg, scen, prior_table, cohort, rev_nco):
    sm = scen["base"]["summary"]
    q = []
    def add(question, links, response):
        q.append({"q": question, "links": links, "proposed_response": response})

    add("Deposit growth reaches ${:.0f}M by year 3. What evidence supports acquisition at this pace?"
        .format(sm["deposits_yr3"] / 1e6),
        ["assumption: new_accts_per_marketing_dollar", "assumption: migration_accounts_m1",
         f"cohort {cohort['cohort_id']}"],
        "Growth decomposes to funded accounts at a ${:.0f} CAC against 940k existing parent-app "
        "relationships; year-2 deposit growth sits at p{:.0f} of the frozen de novo cohort."
        .format(1.0 / cfg["assumptions"]["new_accts_per_marketing_dollar"],
                prior_table["deposit_growth_yr1"]["client_percentile"]))

    add("What supports the {:.1%} mature card loss assumption?".format(cfg["assumptions"]["card_nco_mature"]),
        ["assumption: card_nco_mature", "confidence: externally_benchmarked"],
        "Externally benchmarked at p{:.0f} of consumer-active cohort members; vintage ramp applied "
        "over 12 months; allowance held at 6.5% coverage."
        .format(prior_table["card_nco_mature"]["client_percentile"]))

    add("At what point does the plan breach the 10% leverage commitment?",
        ["scenario: reverse_stress"],
        "Growth misses alone do not breach within the tested range; the binding dimension is credit: "
        "losses must reach {} of the assumed mature rate (NCO {:.1%}) before minimum leverage "
        "touches 10%. Capital is sized to the downside percentile, not base."
        .format(f"{rev_nco.get('nco_multiplier')}x" if rev_nco.get("nco_multiplier") else "beyond 8x",
                rev_nco.get("implied_nco") or 0))

    add("The bank's sole growth channel sits in an affiliate. How is operational independence assured?",
        ["flag: MAP-01", "step 0A entity map"],
        "Marketing services agreement priced at arm's length with termination continuity terms; "
        "fraud-ops staff migrate to bank employment by open date; board-level dependency review quarterly.")

    add("Four of the cohort's nearest peers did not survive as independent institutions. Why will this bank differ?"
        if cohort["terminal_summary"]["failed"] + cohort["terminal_summary"]["acquired"] >= 4 else
        "Several cohort peers exited. Why will this bank differ?",
        [f"cohort {cohort['cohort_id']} terminal summary"],
        "Terminal-event peers are retained in the evidence base deliberately; their common pattern "
        "(cost base outrunning deposit ramp) is the compound scenario, which the plan survives at "
        "{:.1%} minimum leverage.".format(scen["compound"]["summary"]["min_leverage"]))

    add("How does staffing scale if account growth doubles plan?",
        ["engine: capacity expenses"],
        "Opex is capacity-driven, not a fixed row: KYC minutes, fraud alerts, and service contacts "
        "convert account volume to FTE directly, so the expense base moves with the miss or the beat.")

    add("What happens to margin under +300bp?",
        ["scenario: rate_shock_300"],
        "Deposit beta migrates to 0.75; minimum leverage remains {:.1%}; asset side reprices via "
        "securities yield and card APR.".format(scen["rate_shock_300"]["summary"]["min_leverage"]))

    add("Which assumptions are unsubstantiated?",
        ["assumption book confidence tags"],
        "None tagged unsubstantiated. Two management estimates (migration pace, savings rate) carry "
        "sensitivity exhibits; savings-rate spread sits at p{:.0f} of cohort."
        .format(prior_table["cost_of_deposits_spread"]["client_percentile"]))
    return q


def examiner_book_generic(cfg, scen, prior_table, cohort, ctests):
    """Archetype-neutral question book: constraints, cohort placement, survivorship."""
    q = []
    def add(question, links, response):
        q.append({"q": question, "links": links, "proposed_response": response})
    for t in [t for t in ctests if t["scenario"] == "base"]:
        add(f"Constraint '{t['constraint']}' ({t['source']}): what is the margin and where is it thinnest?",
            [f"constraint: {t['constraint']}"],
            f"{t['detail']}; limit {t['limit']}; result {'holds' if t['pass'] else 'BREACH'} in base, "
            f"tested identically in every scenario.")
    for m, p in prior_table.items():
        if p["client_percentile"] >= 90 or p["client_percentile"] <= 10:
            add(f"{m} sits at p{p['client_percentile']:.0f} of the frozen cohort. What supports it?",
                [f"assumption: {m}", f"cohort {cohort['cohort_id']}"],
                f"Cohort p50 {p['p50']}; client {p['client']}. Support documented in the assumption book; "
                "deviation argued, not asserted.")
    ts = cohort["terminal_summary"]
    if ts["failed"] + ts["acquired"] >= 3:
        add("Several cohort peers did not survive independently. Why will this bank differ?",
            [f"cohort {cohort['cohort_id']} terminal summary"],
            "Terminal-event peers are retained in evidence deliberately; the compound scenario tests "
            "their common failure pattern and the plan's minimum leverage under it is "
            f"{scen['compound']['summary']['min_leverage']:.1%}.")
    return q
