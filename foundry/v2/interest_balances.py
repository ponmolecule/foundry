"""Opt-in source-model interest balances for Profile A.

The module owns only the authored paths and closed equations.  It deliberately
defaults every input to zero and never invents rates or balances.
"""

from .series import resolve_entered_series


def prepare_interest_balance_model(assumptions, customer_counts, periods, ppy, *, growth_context=None):
    cfg = (assumptions or {}).get("interest_balance_model") or {}
    if not cfg or cfg.get("enabled") is False:
        return None

    def series(name):
        values = resolve_entered_series(cfg.get(name), periods, ppy,
                                        context=growth_context, default_value=0.0)
        if any(float(v) < 0 for v in values):
            raise ValueError(f"interest balance model {name} cannot be negative")
        return [float(v) for v in values]

    mab_source = cfg.get("mab_source") or {}
    if str(mab_source.get("source") or "entered").lower() == "link":
        sid = str(mab_source.get("series_id") or "").strip()
        measure = str(mab_source.get("measure") or "period_end").strip()
        measures = customer_counts.get(sid)
        if measures is None or measure not in measures:
            raise ValueError(f"interest balance model MAB source {sid!r} is unavailable")
        mab = [float(v or 0.0) for v in measures[measure]]
    else:
        mab = series("mab_spec")
    if any(v < 0 for v in mab):
        raise ValueError("interest balance model MAB count cannot be negative")

    out = {"mab": mab}
    for name in ("scenario_rate_spec", "deposit_attach_rate_spec",
                 "avg_noninterest_balance_per_mab_spec", "boost_attach_rate_spec",
                 "avg_interest_balance_per_mab_spec", "customer_cost_rate_spec",
                 "operating_cash_ratio_spec", "operating_cash_yield_spec",
                 "frb_stock_ratio_spec", "frb_stock_yield_spec"):
        out[name] = series(name)
    out["fiduciary_noninterest"] = [mab[i] * out["deposit_attach_rate_spec"][i]
                                     * out["avg_noninterest_balance_per_mab_spec"][i]
                                     for i in range(periods)]
    out["fiduciary_interest"] = [mab[i] * out["boost_attach_rate_spec"][i]
                                  * out["avg_interest_balance_per_mab_spec"][i]
                                  for i in range(periods)]
    return out
