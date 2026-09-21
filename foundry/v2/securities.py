"""Managed securities portfolio primitives.

This module owns the *causal grammar* for target-driven securities books.  It does
not hard-code instrument names, allocation weights, target percentages, or market
rates.  A managed portfolio links to a whitelisted endogenous balance-sheet Series,
sets an authored target ratio, allocates the target across named sleeves, applies
runoff/maturities, and solves net purchases/(sales) as the balancing flow.

Current first-class endogenous target sources include period-end Total Equity and
Total Deposits.  Sources are identified by stable Series IDs so additional balance-sheet
Series can be added without changing the portfolio equations.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .series import resolve_entered_series

EQUITY_END_SERIES_ID = "bank.balance_sheet.equity.end"
DEPOSITS_END_SERIES_ID = "bank.balance_sheet.deposits.end"
_VALID_CLASSIFICATIONS = {"AFS", "HTM"}
_VALID_YIELD_SOURCES = {"entered", "curve_library"}
_VALID_CURVES = {"sofr", "effr", "prime"}
_VALID_TARGET_TIMINGS = {"current_period", "prior_period"}
_VALID_PRIOR_INITIALIZATIONS = {"zero", "opening_source"}
_PERIOD_FREQ = {"year": 1, "quarter": 4, "month": 12}
_VALID_RATE_PERIODS = set(_PERIOD_FREQ) | {"model_period"}


def managed_securities_source_catalog() -> list[dict]:
    """Return endogenous balance-sheet Series that may drive managed portfolios."""
    return [
        {
            "series_id": EQUITY_END_SERIES_ID,
            "name": "Total equity — period end",
            "owner_module": "Balance Sheet",
            "semantic_type": "balance",
            "measure": "period_end",
        },
        {
            "series_id": DEPOSITS_END_SERIES_ID,
            "name": "Total deposits — period end",
            "owner_module": "Balance Sheet",
            "semantic_type": "balance",
            "measure": "period_end",
        },
    ]


def _entered(spec: Mapping[str, Any] | None, default: float, n: int, ppy: int, context=None) -> list[float]:
    return resolve_entered_series(spec or {"source": "entered", "trajectory": "flat", "value": default},
                                  n, ppy, context=context, default_value=default)


def _legacy_flat_spec(value: Any, default: float = 0.0) -> dict:
    return {"source": "entered", "trajectory": "flat", "value": float(default if value is None else value)}


def normalize_managed_portfolio(portfolio: Mapping[str, Any] | None) -> dict:
    p = deepcopy(dict(portfolio or {}))
    p.setdefault("name", "Managed securities portfolio")
    p.setdefault("target_source", {"kind": "bank_balance_sheet", "series_id": EQUITY_END_SERIES_ID})
    # r114/r115 portfolios targeted the current period.  Preserve that meaning for
    # existing saved configurations while making timing explicit for all new authoring.
    # Prior-period targets additionally own their first-model-period initialization so
    # the engine never silently substitutes opening balances for a source model whose
    # first projection period is intentionally zero.
    ts = p["target_source"] = deepcopy(dict(p.get("target_source") or {}))
    ts.setdefault("kind", "bank_balance_sheet")
    ts.setdefault("series_id", EQUITY_END_SERIES_ID)
    ts.setdefault("timing", "current_period")
    ts.setdefault("prior_initialization", "zero")
    if not p.get("target_ratio_spec"):
        p["target_ratio_spec"] = _legacy_flat_spec(p.get("target_ratio", 0.0))
    sleeves = []
    for raw in p.get("sleeves") or []:
        s = deepcopy(dict(raw or {}))
        s.setdefault("name", "Security")
        s["classification"] = str(s.get("classification") or "AFS").upper()
        s.setdefault("opening", 0.0)
        # Standardized-approach RWA classification is an authored fact, not an
        # inference from the sleeve name.  Preserve the historical 20% treatment
        # for existing portfolios while surfacing it explicitly for review/editing.
        s.setdefault("risk_weight", 0.20)
        if not s.get("allocation_spec"):
            s["allocation_spec"] = _legacy_flat_spec(s.get("allocation", 0.0))
        if not s.get("maturity_rate_spec"):
            s["maturity_rate_spec"] = _legacy_flat_spec(s.get("maturity_rate", s.get("runoff_rate", 0.0)))
        # The maturity/runoff percentage has an economic time unit independent of
        # how often its authored trajectory changes.  Legacy/pre-r114 objects had
        # model-period semantics; new authoring writes Month / Quarter / Year explicitly.
        s["maturity_rate_spec"].setdefault("period", "model_period")
        ysrc = str(s.get("yield_source") or "entered").lower()
        s["yield_source"] = ysrc
        if ysrc == "entered" and not s.get("yield_spec"):
            s["yield_spec"] = _legacy_flat_spec(s.get("yield_ann", 0.0))
        sleeves.append(s)
    p["sleeves"] = sleeves
    return p



def _periodize_runoff_rate(rate: float, natural_period: str, ppy: int) -> float:
    """Convert a stock-runoff fraction from its natural period to one engine period.

    Runoff compounds through survival, not by linear division.  Thus 12%/year in a
    monthly engine becomes ``1 - (1-.12)**(1/12)`` per month.  This preserves the
    authored economics across Month / Quarter / Year computational cadences.
    """
    r = float(rate or 0.0)
    per = str(natural_period or "model_period").lower()
    if per == "model_period":
        return r
    if per not in _PERIOD_FREQ:
        raise ValueError(f"unsupported managed-securities maturity period {natural_period!r}")
    if not 0.0 <= r <= 1.0:
        raise ValueError("managed-securities maturity/runoff rate must be between 0% and 100%")
    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    exponent = float(_PERIOD_FREQ[per]) / float(ppy)
    return 1.0 - (1.0 - r) ** exponent

def prepare_managed_securities(assumptions: Mapping[str, Any], n_periods: int, ppy: int,
                               *, growth_context=None, rate_curves: Mapping[str, Any] | None = None) -> list[dict]:
    """Normalize and resolve authored managed-portfolio assumptions to native paths.

    The returned runtime keeps opening/end histories separate from assumption paths.
    Endogenous target-source values are supplied later, one period at a time, by the
    engine's balance-sheet solver.
    """
    out = []
    n, ppy = int(n_periods), int(ppy)
    curves = dict(rate_curves or {})
    for raw in assumptions.get("managed_securities_portfolios") or []:
        p = normalize_managed_portfolio(raw)
        ratio = _entered(p.get("target_ratio_spec"), 0.0, n, ppy, growth_context)
        rp = {
            "name": p.get("name") or "Managed securities portfolio",
            "series_id": p.get("series_id"),
            "target_source": deepcopy(p.get("target_source") or {}),
            "target_ratio": ratio,
            "target_source_value": [],
            "target": [],
            "sleeves": [],
        }
        for s in p.get("sleeves") or []:
            alloc = _entered(s.get("allocation_spec"), 0.0, n, ppy, growth_context)
            mat_authored = _entered(s.get("maturity_rate_spec"), 0.0, n, ppy, growth_context)
            maturity_period = str((s.get("maturity_rate_spec") or {}).get("period") or "model_period").lower()
            mat = [_periodize_runoff_rate(v, maturity_period, ppy) for v in mat_authored]
            if s.get("yield_source") == "curve_library":
                curve = str(s.get("curve_name") or "").lower()
                fn = curves.get(curve)
                if not callable(fn):
                    raise ValueError(f"managed securities sleeve {s.get('name')!r} references unavailable curve {curve!r}")
                yld = [float(fn(i)) for i in range(1, n + 1)]
            else:
                yld = _entered(s.get("yield_spec"), 0.0, n, ppy, growth_context)
            rp["sleeves"].append({
                "name": s.get("name") or "Security",
                "series_id": s.get("series_id"),
                "classification": str(s.get("classification") or "AFS").upper(),
                "opening": float(s.get("opening") or 0.0),
                "risk_weight": float(s.get("risk_weight", 0.20)),
                "allocation": alloc,
                "maturity_rate_authored": mat_authored,
                "maturity_period": maturity_period,
                "maturity_rate": mat,
                "yield": yld,
                "yield_source": s.get("yield_source") or "entered",
                "curve_name": s.get("curve_name"),
                "starting": [float(s.get("opening") or 0.0)],
                "maturing": [],
                "net_purchases": [],
                "ending": [float(s.get("opening") or 0.0)],
                "interest_income": [],
            })
        out.append(rp)
    return out


def validate_managed_securities(assumptions: Mapping[str, Any], n_periods: int, ppy: int,
                                *, growth_context=None) -> list[str]:
    """Validate the managed-securities authoring contract; return human-readable errors."""
    errs: list[str] = []
    catalog = {x["series_id"] for x in managed_securities_source_catalog()}
    try:
        runtime = prepare_managed_securities(assumptions, n_periods, ppy, growth_context=growth_context,
                                             rate_curves={k: (lambda _i: 0.0) for k in _VALID_CURVES})
    except Exception as e:
        return [str(e)]
    seen_ids: set[str] = set()
    for pi, (raw, p) in enumerate(zip(assumptions.get("managed_securities_portfolios") or [], runtime)):
        path = f"managed_securities_portfolios[{pi}]"
        src = (normalize_managed_portfolio(raw).get("target_source") or {})
        sid = str(src.get("series_id") or "")
        if sid not in catalog:
            errs.append(f"{path}.target_source.series_id {sid!r} is not a supported balance-sheet Series")
        timing = str(src.get("timing") or "")
        if timing not in _VALID_TARGET_TIMINGS:
            errs.append(f"{path}.target_source.timing must be current_period or prior_period")
        init = str(src.get("prior_initialization") or "")
        if init not in _VALID_PRIOR_INITIALIZATIONS:
            errs.append(f"{path}.target_source.prior_initialization must be zero or opening_source")
        if not str(p.get("name") or "").strip():
            errs.append(f"{path}.name is required")
        if not p.get("sleeves"):
            errs.append(f"{path} requires at least one security sleeve")
            continue
        for i, v in enumerate(p["target_ratio"], 1):
            if not 0.0 <= float(v) <= 5.0:
                errs.append(f"{path}.target_ratio must be between 0% and 500% (period {i})")
                break
        alloc_sums = [0.0] * int(n_periods)
        for si, s in enumerate(p["sleeves"]):
            sp = f"{path}.sleeves[{si}]"
            if not str(s.get("name") or "").strip():
                errs.append(f"{sp}.name is required")
            if s.get("classification") not in _VALID_CLASSIFICATIONS:
                errs.append(f"{sp}.classification must be AFS or HTM")
            if float(s.get("opening") or 0.0) < 0:
                errs.append(f"{sp}.opening must be non-negative")
            ssid = str(s.get("series_id") or "").strip()
            if ssid:
                if ssid in seen_ids:
                    errs.append(f"duplicate managed securities sleeve series_id {ssid!r}")
                seen_ids.add(ssid)
            for i, v in enumerate(s["allocation"]):
                if not 0.0 <= float(v) <= 1.0:
                    errs.append(f"{sp}.allocation must be between 0% and 100% (period {i+1})")
                    break
                alloc_sums[i] += float(v)
            if str(s.get("maturity_period") or "") not in _VALID_RATE_PERIODS:
                errs.append(f"{sp}.maturity_rate_spec.period must be Month, Quarter, Year, or model_period")
            for i, v in enumerate(s["maturity_rate_authored"]):
                if not 0.0 <= float(v) <= 1.0:
                    errs.append(f"{sp}.maturity_rate must be between 0% and 100% (period {i+1})")
                    break
            for i, v in enumerate(s["yield"]):
                if float(v) <= -1.0:
                    errs.append(f"{sp}.yield must be greater than -100% (period {i+1})")
                    break
            nr = normalize_managed_portfolio(raw)["sleeves"][si]
            if nr.get("yield_source") not in _VALID_YIELD_SOURCES:
                errs.append(f"{sp}.yield_source must be entered or curve_library")
            if nr.get("yield_source") == "curve_library" and str(nr.get("curve_name") or "").lower() not in _VALID_CURVES:
                errs.append(f"{sp}.curve_name must be SOFR, EFFR, or Prime")
            rw = float(nr.get("risk_weight", 0.20))
            if rw not in (0.0, 0.20, 0.50, 1.00, 1.50, 2.50):
                errs.append(f"{sp}.risk_weight must be 0%, 20%, 50%, 100%, 150%, or 250%")
        for i, total in enumerate(alloc_sums, 1):
            if abs(total - 1.0) > 1e-7:
                errs.append(f"{path} sleeve allocations must sum to 100% in every period; period {i} sums to {total*100:.6g}%")
                break
    return errs


def managed_period_snapshot(runtime: list[dict], period: int, source_values: Mapping[str, float], ppy: int,
                            *, prior_source_values: Mapping[str, float] | None = None) -> list[dict]:
    """Resolve one model period from endogenous target-source values.

    `period` is 1-based.  Net purchases/(sales) are intentionally signed and are the
    balancing flow required to hit the target ending balance exactly.  Interest income
    follows the source model's period-end-balance convention and annual yield / ppy.

    Target-source timing is explicit per portfolio.  ``current_period`` consumes
    ``source_values``.  ``prior_period`` consumes ``prior_source_values`` after the
    first model period; in period 1 it either resolves to zero or to the supplied
    opening source according to ``prior_initialization``.
    """
    idx = int(period) - 1
    prior_values = dict(prior_source_values or {})
    out = []
    for p in runtime:
        src = p.get("target_source") or {}
        src_id = str(src.get("series_id") or "")
        timing = str(src.get("timing") or "current_period")
        if timing == "prior_period":
            init = str(src.get("prior_initialization") or "zero")
            if int(period) == 1 and init == "zero":
                source = 0.0
            else:
                source = float(prior_values[src_id])
        else:
            source = float(source_values[src_id])
        target = source * float(p["target_ratio"][idx])
        po = {"name": p.get("name"), "series_id": p.get("series_id"),
              "target_source_value": source, "target": target, "sleeves": []}
        for s in p.get("sleeves") or []:
            start = float(s["ending"][-1])
            maturity = start * float(s["maturity_rate"][idx])
            ending = target * float(s["allocation"][idx])
            net = ending - start + maturity
            yld = float(s["yield"][idx])
            interest = ending * yld / float(ppy)
            po["sleeves"].append({
                "name": s.get("name"), "series_id": s.get("series_id"),
                "classification": s.get("classification"), "starting": start,
                "maturing": maturity, "net_purchases": net, "ending": ending,
                "yield": yld, "interest_income": interest,
            })
        out.append(po)
    return out


def commit_managed_snapshot(runtime: list[dict], snapshot: list[dict]) -> None:
    """Append a converged period snapshot to the runtime's audit histories."""
    for p, ps in zip(runtime, snapshot):
        p["target_source_value"].append(float(ps.get("target_source_value") or 0.0))
        p["target"].append(float(ps["target"]))
        for s, ss in zip(p["sleeves"], ps["sleeves"]):
            s["starting"].append(float(ss["starting"]))
            s["maturing"].append(float(ss["maturing"]))
            s["net_purchases"].append(float(ss["net_purchases"]))
            s["ending"].append(float(ss["ending"]))
            s["interest_income"].append(float(ss["interest_income"]))


def managed_opening_totals(runtime: list[dict]) -> tuple[float, float]:
    afs = sum(float(s.get("opening") or 0.0) for p in runtime for s in p.get("sleeves") or [] if s.get("classification") == "AFS")
    htm = sum(float(s.get("opening") or 0.0) for p in runtime for s in p.get("sleeves") or [] if s.get("classification") == "HTM")
    return afs, htm


def snapshot_totals(snapshot: list[dict]) -> dict:
    afs = htm = interest = 0.0
    for p in snapshot:
        for s in p.get("sleeves") or []:
            end = float(s.get("ending") or 0.0)
            if s.get("classification") == "HTM": htm += end
            else: afs += end
            interest += float(s.get("interest_income") or 0.0)
    return {"afs": afs, "htm": htm, "total": afs + htm, "interest": interest}


def public_managed_securities(runtime: list[dict]) -> list[dict]:
    """Serialize audit-friendly native-period outputs without private resolver callables."""
    out = []
    for p in runtime:
        out.append({
            "name": p.get("name"), "series_id": p.get("series_id"),
            "target_source": deepcopy(p.get("target_source") or {}),
            "target_ratio": list(p.get("target_ratio") or []),
            "target_source_value": list(p.get("target_source_value") or []),
            "target": list(p.get("target") or []),
            "sleeves": [{
                "name": s.get("name"), "series_id": s.get("series_id"),
                "classification": s.get("classification"), "opening": s.get("opening"),
                "risk_weight": s.get("risk_weight", 0.20),
                "allocation": list(s.get("allocation") or []),
                "maturity_rate_authored": list(s.get("maturity_rate_authored") or []),
                "maturity_period": s.get("maturity_period") or "model_period",
                "maturity_rate": list(s.get("maturity_rate") or []),
                "yield": list(s.get("yield") or []),
                "starting": list(s.get("starting") or [])[1:],
                "maturing": list(s.get("maturing") or []),
                "net_purchases": list(s.get("net_purchases") or []),
                "ending": list(s.get("ending") or [])[1:],
                "interest_income": list(s.get("interest_income") or []),
            } for s in p.get("sleeves") or []],
        })
    return out
