"""Peer-assumption seeding ("Use Peer Assumptions") — an INTERNAL convenience toy.

Given one or more peer institutions (by FDIC cert) or an asset-band cohort, produce a set of SUGGESTED
config values the user can review and adopt in the Start/Reset tab. Every suggested value carries a
provenance string. Nothing here touches the projection engine: the output is a plain dict of
suggestions; the frontend applies (or discards) them into the editable config, exactly as if the user
had typed them.

SCOPE (grounded in what Call Reports actually contain, per the design discussion):
  - Balances / product mix : PER-PRODUCT, real. RC-C reports balances by loan category.
  - Growth rates           : PER-PRODUCT, derivable from balance changes quarter-over-quarter.
  - Charge-off rates        : category-level where the substrate carries them.
  - Yields / rates          : AGGREGATE ONLY. Call Reports report total loan interest income, not
                              per-product yields. Seeded rates are the peer's BLENDED book yield, and
                              are labelled as such. This is a real limitation, disclosed, not hidden.
  - Maturity / term         : NOT SEEDED. Not derivable per-product from Call Reports, and it is a
                              business-plan decision the client should own.

DEGRADES GRACEFULLY: if the substrate/client is not configured or a lookup fails, returns a structured
"unavailable" payload — it never raises into the caller and never affects anything else.
"""

# Call Report metric names we attempt to pull. These are the substrate's metric_name keys; if a name is
# absent the field is simply omitted from suggestions (fail-open per field, not fatal).
_BALANCE_METRICS = {
    "loanConsumer":   "loans_consumer",
    "loanCreditCard": "loans_credit_card",
    "loanCommercial": "loans_ci",
    "loanMortgage":   "loans_1_4_family",
    "loanCRE":        "loans_cre",
}
_AGG_YIELD_METRIC = "loan_yield"          # blended book loan yield (%)
_COST_OF_FUNDS_METRIC = "cost_of_funds"   # blended deposit cost (%)
_NCO_METRIC = "net_charge_off_rate"       # net charge-off rate (%)


def _latest(series):
    """Last non-null point of a metric series -> (value, 'YYYYQn') or (None, None)."""
    if not series:
        return None, None
    for pt in reversed(series):
        if pt.get("value") is not None:
            return pt["value"], f"{pt['year']}Q{pt['quarter']}"
    return None, None


def _cagr_q(series):
    """Quarterly growth rate from first to last non-null point of a balance series."""
    pts = [p for p in (series or []) if p.get("value") not in (None, 0)]
    if len(pts) < 2:
        return None
    first, last = pts[0]["value"], pts[-1]["value"]
    n = (pts[-1]["year"] - pts[0]["year"]) * 4 + (pts[-1]["quarter"] - pts[0]["quarter"])
    if n <= 0 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / n) - 1.0


def seed_from_peers(client, certs, products, since_year=None):
    """Build provenance-stamped config suggestions for the given products from the named peers.

    client   : a CharterIQClient (or anything with get_institution / get_bank_quarterly_series).
    certs    : list of FDIC certs (1 = "select" that peer; >1 = median blend across them).
    products : the user's lending_products list (each carries call_report_line / line).
    Returns  : {"available": bool, "peers": [...], "suggestions": {product_index: {...}}, "note": str}
    """
    if not client or not getattr(client, "configured", lambda: False)():
        return {"available": False, "note": "Peer substrate is not configured in this environment.",
                "peers": [], "suggestions": {}}
    if not certs:
        return {"available": False, "note": "No peers selected.", "peers": [], "suggestions": {}}

    # resolve peer identities (best-effort; a missing institution row is non-fatal)
    peers = []
    for c in certs:
        try:
            inst = client.get_institution(int(c))
        except Exception:
            inst = None
        peers.append({"cert": int(c), "name": (inst or {}).get("name") or f"cert {c}",
                      "asset_size_mm": (inst or {}).get("asset_size_mm")})

    blend = len(certs) > 1
    prov_base = ("median of " + ", ".join(p["name"] for p in peers)) if blend else peers[0]["name"]

    # metrics we need per peer: each product's balance metric + aggregates
    want = list({m for ln, m in _BALANCE_METRICS.items()}) + \
           [_AGG_YIELD_METRIC, _COST_OF_FUNDS_METRIC, _NCO_METRIC]

    # pull each peer's series once
    per_peer = {}
    for c in certs:
        try:
            res = client.get_bank_quarterly_series(int(c), want)
            per_peer[int(c)] = res.get("series", {})
        except Exception:
            per_peer[int(c)] = {}

    def _median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        n = len(vals)
        return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0

    # aggregate rate hints (blended book yield / cost of funds) — labelled as aggregate
    agg_yield_vals, agg_yield_asof = [], None
    cof_vals = []
    for c in certs:
        y, asof = _latest(per_peer[c].get(_AGG_YIELD_METRIC))
        if y is not None:
            agg_yield_vals.append(y); agg_yield_asof = asof
        cof, _ = _latest(per_peer[c].get(_COST_OF_FUNDS_METRIC))
        if cof is not None:
            cof_vals.append(cof)
    agg_yield = _median(agg_yield_vals)
    agg_cof = _median(cof_vals)

    suggestions = {}
    for i, p in enumerate(products or []):
        line = p.get("call_report_line") or p.get("line")
        bm = _BALANCE_METRICS.get(line)
        if not bm:
            continue
        # balance (latest) and growth (quarterly), per peer, then median across peers
        bals, asofs, growths = [], [], []
        for c in certs:
            v, asof = _latest(per_peer[c].get(bm))
            if v is not None:
                bals.append(v); asofs.append(asof)
            g = _cagr_q(per_peer[c].get(bm))
            if g is not None:
                growths.append(g)
        s = {}
        med_bal = _median(bals)
        if med_bal is not None:
            # substrate balances are typically $mm; Foundry inputs are $000s -> x1000
            s["opening_balance"] = {"value": round(med_bal * 1000.0, 1),
                                    "provenance": f"{prov_base} \u2014 {line} balance, {asofs[-1] if asofs else 'latest'} Call Report"}
        med_g = _median(growths)
        if med_g is not None:
            s["orig_growth_q"] = {"value": round(med_g, 4),
                                  "provenance": f"{prov_base} \u2014 realized {line} quarterly balance growth"}
        # rate hint (AGGREGATE, labelled)
        if agg_yield is not None:
            s["yield_ann"] = {"value": round(agg_yield / 100.0, 4),
                              "provenance": f"{prov_base} \u2014 BLENDED book loan yield ({agg_yield_asof or 'latest'}); "
                                            "Call Reports do not report per-product yields, so this is the whole-book average, not this product's rate"}
        # charge-off (category-level where present)
        nco_vals = []
        for c in certs:
            n, _ = _latest(per_peer[c].get(_NCO_METRIC))
            if n is not None:
                nco_vals.append(n)
        med_nco = _median(nco_vals)
        if med_nco is not None:
            s["charge_off_ann"] = {"value": round(med_nco / 100.0, 4),
                                   "provenance": f"{prov_base} \u2014 net charge-off rate (book-level)"}
        if s:
            suggestions[i] = s

    dep_hint = None
    if agg_cof is not None:
        dep_hint = {"rate_paid_ann": {"value": round(agg_cof / 100.0, 4),
                                       "provenance": f"{prov_base} \u2014 blended cost of funds"}}

    return {
        "available": True,
        "blend": blend,
        "peers": peers,
        "suggestions": suggestions,
        "deposit_hint": dep_hint,
        "scope_note": ("Seeds per-product balances and growth from real peer Call Reports; rates are the "
                       "peers' BLENDED book yield (per-product yields are not in Call Reports); maturity "
                       "is never seeded (not in the data, and a decision for you to own). Every value is "
                       "a suggestion you can edit or discard before it enters the model."),
    }
