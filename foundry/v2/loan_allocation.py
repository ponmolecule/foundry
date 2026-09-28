"""Portfolio allocation of target loan exposures across an explicit capacity.

This pure calculation has no spreadsheet or product-name dependencies.  The caller
owns the source Series and the cap; this module allocates their resolved period
values and exposes both retained and distributed amounts for audit.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite


def allocate_loan_levels(targets: Mapping[str, list[float]], cap: list[float]) -> dict:
    """Pro rata allocation of nonnegative target levels, one period at a time.

    A zero total target has factor 1, matching the useful identity convention;
    excess capacity never inflates a target.  Empty/mismatched horizons and
    duplicate identities cannot silently create a partial allocation.
    """
    if not targets:
        raise ValueError("loan allocation requires at least one product")
    horizon = len(cap)
    if not horizon:
        raise ValueError("loan allocation requires a nonempty cap horizon")
    for name, values in targets.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("loan allocation product identities must be nonempty")
        if len(values) != horizon:
            raise ValueError(f"loan allocation target {name!r} has an incomplete horizon")

    def amount(value, label):
        number = float(value)
        if not isfinite(number) or number < 0:
            raise ValueError(f"loan allocation {label} must be finite and nonnegative")
        return number

    caps = [amount(v, f"cap period {i + 1}") for i, v in enumerate(cap)]
    source = {name: [amount(v, f"target {name!r} period {i + 1}")
                     for i, v in enumerate(values)] for name, values in targets.items()}
    totals = [sum(values[i] for values in source.values()) for i in range(horizon)]
    factors = [min(1.0, caps[i] / totals[i]) if totals[i] else 1.0
               for i in range(horizon)]
    retained = {name: [v * factors[i] for i, v in enumerate(values)]
                for name, values in source.items()}
    distributed = {name: [v - retained[name][i] for i, v in enumerate(values)]
                   for name, values in source.items()}
    return {"targets": source, "cap": caps, "total_target": totals,
            "factor": factors, "retained": retained, "distributed": distributed}
