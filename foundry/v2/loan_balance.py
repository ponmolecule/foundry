"""Typed level-balance drivers for lending products.

Legacy roll-forward and customer-count-linked paths remain intact. Optional entered
targets and funded-flow-derived targets supply a retained level to the same loan
engine, which continues to own yield, allowance, provision and reporting.
"""
from __future__ import annotations

from typing import Mapping
from math import isfinite

from .cac_feeder import cac_customer_count_catalog, normalize_customer_count_measure
from .series import normalize_series_spec, resolve_entered_series


ROLLFORWARD = "rollforward"
LINKED_CUSTOMER_LEVEL = "linked_customer_level"
EXPLICIT_LEVEL = "explicit_level"
FUNDED_FLOW_LEVEL = "funded_flow_level"


def _funded_flow_timing(driver: Mapping) -> tuple[str, int, int, float]:
    """Normalize the meaning and native-model-period timing of a funded flow."""
    stage = str(driver.get("input_stage") or "funded_volume")
    if stage not in {"source_activity", "funded_volume"}:
        raise ValueError("funded-flow input_stage must be source_activity or funded_volume")
    def positive_period(key: str) -> int:
        raw = driver.get(key, 1)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not isfinite(raw) or raw < 1 or int(raw) != raw:
            raise ValueError(f"funded-flow {key} must be a positive whole model period")
        return int(raw)
    start = positive_period("start_period")
    ramp = positive_period("ramp_periods")
    try:
        take_up = float(driver.get("take_up_share", 1))
    except (TypeError, ValueError):
        raise ValueError("funded-flow take_up_share must be a share in [0, 1]")
    if not isfinite(take_up) or not 0 <= take_up <= 1:
        raise ValueError("funded-flow take_up_share must be a share in [0, 1]")
    if stage == "funded_volume" and (ramp != 1 or take_up != 1):
        raise ValueError("final funded volume already includes take-up and ramp; select source activity to apply them")
    return stage, start, ramp, take_up


def loan_balance_mode(product: Mapping | None) -> str:
    raw = str((product or {}).get("balance_mode") or ROLLFORWARD).strip().lower()
    if raw not in {ROLLFORWARD, LINKED_CUSTOMER_LEVEL, EXPLICIT_LEVEL, FUNDED_FLOW_LEVEL}:
        raise ValueError(f"unsupported loan balance mode {raw!r}")
    return raw


def normalize_linked_loan_balance(product: Mapping | None, assumptions: Mapping | None) -> dict | None:
    """Validate and normalize one opt-in customer-linked loan balance contract."""
    if loan_balance_mode(product) == ROLLFORWARD:
        return None
    p = product or {}
    if loan_balance_mode(p) == FUNDED_FLOW_LEVEL:
        fd = p.get("funded_flow_driver") or {}
        stage, start, ramp, take_up = _funded_flow_timing(fd)
        source = str(fd.get("source") or "").strip()
        if source == "entered":
            from .income_modules import _fee_entered_flow_value
            flow = fd.get("flow_path")
            if not isinstance(flow, Mapping) or flow.get("unit_kind") != "money_flow":
                raise ValueError("funded-flow balance needs an entered monetary flow_path")
            _fee_entered_flow_value(flow, 1, 12)
        elif source == "fee_stream_quantity":
            sid = str(fd.get("series_id") or "").strip()
            if not sid:
                raise ValueError("funded-flow balance link requires a stable series_id")
            from .income_modules import _fee_stream_quantity_kinds
            from .fee_links import has_links, FeeLinkPlan
            plan=FeeLinkPlan(assumptions) if has_links(assumptions or {}) else None
            matches = []
            for family in ("deposit_products", "obs_exposures"):
                for pi,prod in enumerate((assumptions or {}).get(family) or []):
                    streams = prod.get("fee_streams") or []
                    kinds = {i:plan.kinds[(pi,i)] for i in range(len(streams))} if plan and family=="obs_exposures" else _fee_stream_quantity_kinds(streams)
                    matches += [(st, kinds[i]) for i, st in enumerate(streams)
                                if str(st.get("quantity_series_id") or "") == sid]
            if len(matches) != 1 or matches[0][1] != "money" or matches[0][0].get("basis") != "transaction":
                raise ValueError(f"funded-flow Series {sid!r} must resolve to one upstream monetary transaction flow")
        else:
            raise ValueError("funded-flow balance requires entered or fee_stream_quantity source")
        for key in ("term_days", "day_count", "reserve_share", "target_retention_share"):
            if key not in p:
                raise ValueError(f"funded-flow balance requires {key}")
        term, days = float(p["term_days"]), float(p["day_count"])
        if not isfinite(term) or not isfinite(days) or term < 0 or days <= 0:
            raise ValueError("funded-flow term must be finite/nonnegative and day_count finite/positive")
        reserve, retention = float(p["reserve_share"]), float(p["target_retention_share"])
        if not (isfinite(reserve) and isfinite(retention) and 0 <= reserve <= 1 and 0 <= retention <= 1):
            raise ValueError("funded-flow reserve and retention shares must be in [0, 1]")
        if p.get("mortgage_banking") or p.get("structure") == "term":
            raise ValueError("funded-flow level cannot use mortgage-banking or term-cohort mechanics")
        if p.get("charge_off_balance_measure", "period_begin") not in {"period_begin", "period_end"}:
            raise ValueError("charge_off_balance_measure must be period_begin or period_end")
        if p.get("allowance_mode", "reserve_rate") not in {"reserve_rate", "loss_rate_term"}:
            raise ValueError("unsupported loan allowance_mode")
        measure = str(p.get("interest_balance_measure") or "")
        if measure not in {"period_average", "period_end", "period_begin"}:
            raise ValueError("funded-flow balance requires an explicit interest_balance_measure")
        return {"source": "funded_flow", "driver": dict(fd), "input_stage": stage,
                "start_period": start, "ramp_periods": ramp, "take_up_share": take_up,
                "term_days": term,
                "day_count": days, "reserve_share": reserve,
                "target_retention_share": retention,
                "interest_balance_measure": measure}
    if loan_balance_mode(p) == EXPLICIT_LEVEL:
        raw_spec = p.get("ending_balance_spec")
        if not isinstance(raw_spec, Mapping):
            raise ValueError("explicit-level loan requires ending_balance_spec")
        spec = normalize_series_spec(raw_spec)
        if spec["source"] != "entered":
            raise ValueError("explicit-level loan balance requires an entered Series")
        if p.get("mortgage_banking") or p.get("structure") == "term":
            raise ValueError("explicit-level loans cannot use mortgage-banking or term-cohort mechanics")
        measure = str(p.get("interest_balance_measure") or "period_average")
        if measure not in {"period_average", "period_end", "period_begin"}:
            raise ValueError("interest_balance_measure must be period_average, period_end or period_begin")
        return {"source": "entered", "ending_balance_spec": spec,
                "interest_balance_measure": measure}
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
                                ppy: int, *, growth_context=None,
                                fee_stream_quantities=None) -> dict | None:
    cfg = normalize_linked_loan_balance(product, assumptions)
    if cfg is None:
        return None
    if cfg["source"] == "entered":
        balances = resolve_entered_series(cfg["ending_balance_spec"], n_periods, ppy,
                                           context=growth_context)
        if any(float(v) < 0 for v in balances):
            raise ValueError("explicit loan ending balance resolves negative within the model horizon")
        return {**cfg, "ending_balance": balances}
    if cfg["source"] == "funded_flow":
        fd = cfg["driver"]
        if fd["source"] == "entered":
            from .income_modules import _fee_entered_flow_value
            flow_path = fd["flow_path"]
            if flow_path.get("trajectory") == "explicit_schedule":
                freq = {"year": 1, "quarter": 4, "month": 12}[flow_path["period"]]
                required = (n_periods * freq + ppy - 1) // ppy
                schedule = flow_path.get("schedule") or {}
                missing = [i for i in range(1, required + 1) if str(i) not in schedule]
                if missing:
                    raise ValueError(f"funded-flow schedule is missing source period {missing[0]}")
            flows = [_fee_entered_flow_value(fd["flow_path"], q, ppy,
                       {"growth_context": growth_context}) for q in range(1, n_periods + 1)]
        else:
            sid = str(fd["series_id"])
            flows = list((fee_stream_quantities or {}).get(sid) or [])
            if len(flows) != n_periods:
                raise ValueError(f"funded-flow source Series {sid!r} is unavailable or incomplete")
        if any(float(v) < 0 for v in flows):
            raise ValueError("funded-flow volume cannot be negative")
        stage, start, ramp, take_up = (cfg[k] for k in
            ("input_stage", "start_period", "ramp_periods", "take_up_share"))
        if stage == "funded_volume":
            conflict = next((q for q, v in enumerate(flows, 1)
                             if q < start and abs(float(v)) > 1e-9), None)
            if conflict is not None:
                raise ValueError(f"final funded volume is nonzero in model period {conflict} before start_period {start}; change the timing or source data")
            funded = [float(v) for v in flows]
        else:
            funded = [float(v) * take_up *
                      (0.0 if q < start else min(1.0, (q - start + 1) / ramp))
                      for q, v in enumerate(flows, 1)]
        outstanding = [v * ppy * cfg["term_days"] / cfg["day_count"]
                       * (1 - cfg["reserve_share"]) for v in funded]
        targets = [v * cfg["target_retention_share"] for v in outstanding]
        return {**cfg, "source_activity": flows, "funded_volume": funded,
                "outstanding": outstanding,
                "ending_balance": targets}
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
