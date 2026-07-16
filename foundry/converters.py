"""Mode T, stage T-3: the converter library (TRANSLATION_PIPELINE.md).

Every conversion between a source dialect and the canonical config is a named,
deterministic, side-effect-free function registered here — one source of truth
consumed by the mapping session (modet_map), the FIW importer, and any future
door. Each converter documents its convention inline; each has an arithmetic
gate (T26). Nothing here guesses: callers supply declared units and cadence.
"""


def identity(v, p=None):
    """No conversion; declared units already canonical."""
    return float(v)


def monthly_flow_x3(v, p=None):
    """Monthly flow ($/month) -> quarterly flow ($/quarter). Convention: x3,
    flat within the quarter (the Patrick originations conversion)."""
    return float(v) * 3.0


def annual_rate_div4(v, p=None):
    """Annual rate -> quarterly rate. Convention: /4 simple, matching the
    engine's own quarterly accrual (not compounded)."""
    return float(v) / 4.0


def pct_to_rate(v, p=None):
    """Percent (e.g. 1.5 meaning 1.5%) -> decimal rate (0.015)."""
    return float(v) / 100.0


def bp_to_rate(v, p=None):
    """Basis points (e.g. 25 meaning 25bp) -> decimal rate (0.0025)."""
    return float(v) / 10_000.0


def units_thousands(v, p=None):
    """$000s -> dollars (the workbook scale convention)."""
    return float(v) * 1000.0


def annual_steps_to_quarterly(vals, p=None):
    """Annual rate steps (one value per year, e.g. Patrick's fed funds Y1-Y3)
    -> 12 quarterly points. Convention: step function, each year's value held
    flat for its four quarters (no interpolation — a step is what was stated)."""
    out = []
    for v in vals:
        out.extend([float(v)] * 4)
    return out[:12] if len(out) >= 12 else out + [out[-1]] * (12 - len(out))


def dollar_adds_to_monthly_path(adds_m, runoff_ann, months=36, p=None):
    """Flat monthly $-adds + annual runoff -> monthly balance path.
    Convention (the source workbook's own recursion, verified by gate):
    B_m = B_{m-1} * (1 - runoff_ann/12) + adds_m, from zero."""
    b, out = 0.0, []
    for _ in range(int(months)):
        b = b * (1.0 - float(runoff_ann) / 12.0) + float(adds_m)
        out.append(b)
    return out


def monthly_path_to_quarterly_eop(monthly, p=None):
    """Monthly balance path -> quarterly end-of-period samples (month 3q)."""
    return [monthly[3 * q - 1] for q in range(1, len(monthly) // 3 + 1)]


REGISTRY = {
    "identity": identity,
    "monthly_flow_x3": monthly_flow_x3,
    "annual_rate_div4": annual_rate_div4,
    "pct_to_rate": pct_to_rate,
    "bp_to_rate": bp_to_rate,
    "units_thousands": units_thousands,
}
SERIES_REGISTRY = {
    "annual_steps_to_quarterly": annual_steps_to_quarterly,
    "dollar_adds_to_monthly_path": dollar_adds_to_monthly_path,
    "monthly_path_to_quarterly_eop": monthly_path_to_quarterly_eop,
}
