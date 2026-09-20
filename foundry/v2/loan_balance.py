"""Typed balance drivers for lending products.

Legacy loans remain roll-forward products.  A linked-level loan instead observes a
CAC-owned customer-count Series and applies an entered average-balance-per-customer
Series.  The loan module still owns the resulting on-balance-sheet asset, yield,
allowance, provision and Call Report classification.
"""
from __future__ import annotations

from typing import Mapping

from .cac_feeder import cac_customer_count_catalog, normalize_customer_count_measure
from .series import normalize_series_spec, resolve_entered_series


ROLLFORWARD = "rollforward"
LINKED_CUSTOMER_LEVEL = "linked_customer_level"


def loan_balance_mode(product: Mapping | None) -> str:
    raw = str((product or {}).get("balance_mode") or ROLLFORWARD).strip().lower()
    if raw not in {ROLLFORWARD, LINKED_CUSTOMER_LEVEL}:
        raise ValueError(f"unsupported loan balance mode {raw!r}")
    return raw


def normalize_linked_loan_balance(product: Mapping | None, assumptions: Mapping | None) -> dict | None:
    """Validate and normalize one opt-in customer-linked loan balance contract."""
    if loan_balance_mode(product) == ROLLFORWARD:
        return None
    p = product or {}
    raw = p.get("balance_driver")
    if not isinstance(raw, Mapping):
        raise ValueError("linked loan balance requires balance_driver")
    source = str(raw.get("source") or "customer_acquisition_count").strip().lower()
    if source != "customer_acquisition_count":
        raise ValueError("linked loan balance source must be customer_acquisition_count")
    sid = str(raw.get("series_id") or "").strip()
    if not sid:
        raise ValueError("linked loan balance requires a customer-count series_id")
    known = {x["series_id"] for x in cac_customer_count_catalog(assumptions or {})}
    if sid not in known:
        raise ValueError(f"linked loan customer-count Series {sid!r} does not exist")
    measure = normalize_customer_count_measure(raw.get("measure"), default="period_end")
    if measure == "annual_count":
        raise ValueError("linked loan balance requires period_end or period_average customer count")
    multiplier = normalize_series_spec(raw.get("average_balance_per_customer_spec") or {
        "source": "entered", "trajectory": "flat", "value": 0.0
    })
    if multiplier.get("source") != "entered":
        raise ValueError("average balance per customer must be an entered Series")
    vals = []
    if multiplier.get("trajectory") == "flat":
        vals = [multiplier.get("value")]
    elif multiplier.get("trajectory") == "growth":
        vals = [multiplier.get("base")]
    else:
        vals = list(multiplier.get("values") or [])
    if any(float(v or 0.0) < 0.0 for v in vals):
        raise ValueError("average balance per customer must be nonnegative")
    if p.get("mortgage_banking"):
        raise ValueError("linked-level loans cannot also use mortgage-banking sale mechanics")
    if p.get("structure") == "term":
        raise ValueError("linked-level loans cannot also use term-cohort amortization")
    return {
        "source": source,
        "series_id": sid,
        "measure": measure,
        "average_balance_per_customer_spec": multiplier,
    }


def resolve_linked_loan_balance(product: Mapping, assumptions: Mapping,
                                customer_count_series: Mapping, n_periods: int,
                                ppy: int, *, growth_context=None) -> dict | None:
    cfg = normalize_linked_loan_balance(product, assumptions)
    if cfg is None:
        return None
    sid, measure = cfg["series_id"], cfg["measure"]
    by_measure = (customer_count_series or {}).get(sid)
    if not isinstance(by_measure, Mapping) or measure not in by_measure:
        raise ValueError(f"linked loan customer-count Series {sid!r} measure {measure!r} is unavailable")
    counts = [float(v or 0.0) for v in list(by_measure[measure])[:n_periods]]
    if len(counts) != int(n_periods):
        raise ValueError(f"linked loan customer-count Series {sid!r} has an incomplete horizon")
    multipliers = resolve_entered_series(
        cfg["average_balance_per_customer_spec"], n_periods, ppy,
        context=growth_context, default_value=0.0)
    if any(float(v or 0.0) < 0.0 for v in multipliers):
        raise ValueError("average balance per customer resolves negative within the model horizon")
    if any(float(v or 0.0) < 0.0 for v in counts):
        raise ValueError("linked loan customer count resolves negative within the model horizon")
    balances = [counts[i] * float(multipliers[i] or 0.0)
                for i in range(int(n_periods))]
    return {**cfg, "customer_count": counts,
            "average_balance_per_customer": multipliers,
            "ending_balance": balances}
