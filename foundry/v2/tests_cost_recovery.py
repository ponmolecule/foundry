"""Regression tests for linked cost pools + cost-recovery fee pricing (r46).

Run: python3 -m foundry.v2.tests_cost_recovery
"""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from .cost_pools import (cost_pool_series, cost_pool_series_map, resolve_cost_pool_ref,
                         cost_pool_balance_source_catalog)
from .income_modules import fee_stream_q, _validate_fee_stream_shape
from .run_q import run_v2
from .engine_q_a import run_pf_a
from .validate_q import validate_config_v2, ConfigErrorV2


def _eq(a, b, tol=1e-7):
    return abs(float(a) - float(b)) <= tol


def _stream(ref="pool-platform", recovery=.90, markup=.10, markup_obj=None):
    params = {"recovery_pct": recovery}
    if markup_obj is None:
        params["markup"] = {"value": markup, "trajectory": "flat"}
    else:
        params["markup"] = markup_obj
    return {
        "name": "Platform services fee",
        "basis": "transaction",
        "driver": {"source": "cost_pool", "ref": ref, "trajectory": "flat", "params": {}},
        "rate": {"behavior": "cost_recovery", "params": params},
        "timing": {"start_period": 1},
        "cost": {"kind": "none", "params": {}},
    }


def _assumptions(ppy=12, n=12):
    return {
        "periods_per_year": ppy,
        "n_periods": n,
        "nie_detail": {
            "categories": [{
                "series_id": "opex-tech", "owner_module": "operating_expense",
                "name": "Technology", "per_quarter": 30_000.0, "trajectory": "flat",
            }],
            "workforce": {
                "mode": "roles", "default_payroll_load_rate": .25,
                "roles": [{
                    "series_id": "wf-count-platform", "compensation_series_id": "wf-comp-platform",
                    "expense_series_id": "wf-exp-platform", "owner_module": "operating_expense.workforce",
                    "role": "Platform operations", "count": 2, "annual_comp": 120_000.0,
                    "hire_period": 1,
                }],
            },
        },
        "cost_pools": [{
            "series_id": "pool-platform", "owner_module": "cost_pool",
            "name": "Platform Services Eligible Costs",
            "components": [
                {"kind": "operating_expense_category", "series_id": "opex-tech", "allocation_pct": .80},
                {"kind": "workforce_role_expense", "series_id": "wf-exp-platform", "allocation_pct": .40},
            ],
        }],
    }


def main():
    P = F = 0

    def ck(name, cond, detail=""):
        nonlocal P, F
        if cond:
            P += 1; print(f"PASS {name}")
        else:
            F += 1; print(f"FAIL {name}" + (f" — {detail}" if detail else ""))

    # --- source composition: component allocation is upstream and dimensionless ---
    a = _assumptions(12, 12)
    pool = a["cost_pools"][0]
    arr = cost_pool_series(pool, a, 12, 12)
    # Opex: 30k/q => 10k/mo * 80% = 8k/mo.
    # Workforce: 2 * 120k * 1.25 / 12 = 25k/mo * 40% = 10k/mo.
    ck("cost pool composes native-period Opex + Workforce flows with component allocations",
       len(arr) == 12 and all(_eq(x, 18_000.0) for x in arr))
    ck("cost pool stable ID resolves independently of display name",
       resolve_cost_pool_ref("pool-platform", a)["name"] == "Platform Services Eligible Costs")
    renamed = copy.deepcopy(a); renamed["cost_pools"][0]["name"] = "Renamed display label"
    ck("cost pool stable reference survives pool rename",
       all(_eq(x, 18_000.0) for x in cost_pool_series_map(renamed, 12, 12)["pool-platform"]))

    # Assumption-driven cost bases are pricing inputs, not Operating Expense postings.
    manual = {
        "periods_per_year": 12, "n_periods": 24,
        "cost_pools": [{
            "series_id": "pool-manual", "owner_module": "cost_pool",
            "name": "Entered eligible platform cost",
            "components": [{
                "kind": "assumption_cost_base", "series_id": "cost-base-entered",
                "name": "Platform cost base", "allocation_pct": .75,
                "flow_spec": {"trajectory": "flat", "value": 1_200_000.0, "period": "year"},
            }],
        }],
    }
    ma = cost_pool_series(manual["cost_pools"][0], manual, 12, 12)
    ck("entered assumption cost base resolves as a non-posting natural-period flow",
       len(ma) == 12 and all(_eq(x, 75_000.0) for x in ma))
    mq = copy.deepcopy(manual); mq["periods_per_year"] = 4; mq["n_periods"] = 4
    qarr = cost_pool_series(mq["cost_pools"][0], mq, 4, 4)
    ck("entered annual cost base is cadence-stable between monthly and quarterly engines",
       _eq(sum(ma), 900_000.0) and _eq(sum(qarr), 900_000.0) and _eq(sum(ma), sum(qarr)))
    mg = copy.deepcopy(manual)
    mg["cost_pools"][0]["components"][0]["allocation_pct"] = 1.0
    mg["cost_pools"][0]["components"][0]["flow_spec"] = {
        "trajectory": "growth", "value": 1_200_000.0, "period": "year",
        "growth_spec": {"rate": .10, "period": "year", "method": "step", "anchor": "model_year"},
    }
    mga = cost_pool_series(mg["cost_pools"][0], mg, 24, 12)
    ck("entered cost-base Growth uses canonical periodic-flow semantics",
       _eq(sum(mga[:12]), 1_200_000.0) and _eq(sum(mga[12:24]), 1_320_000.0))
    me = copy.deepcopy(manual)
    me["cost_pools"][0]["components"][0]["allocation_pct"] = 1.0
    me["cost_pools"][0]["components"][0]["flow_spec"] = {
        "trajectory": "explicit", "period": "year", "values": [1_200_000.0, 1_500_000.0],
    }
    mea = cost_pool_series(me["cost_pools"][0], me, 24, 12)
    ck("entered cost-base Explicit schedule preserves supplied annual totals",
       _eq(sum(mea[:12]), 1_200_000.0) and _eq(sum(mea[12:24]), 1_500_000.0))
    mbad = copy.deepcopy(manual); del mbad["cost_pools"][0]["components"][0]["flow_spec"]
    try: cost_pool_series(mbad["cost_pools"][0], mbad, 12, 12); manual_missing_failed = False
    except ValueError as e: manual_missing_failed = "requires flow_spec" in str(e)
    ck("entered assumption cost base fails closed without an amount trajectory", manual_missing_failed)

    # --- source-workbook parity: fixed annual base + average-AUC variable base + markup ---
    # Literal workbook formula for each month:
    # ((FixedAnnual * (1+Escalation)^YearIndex / 12)
    #   + (AvgAUC * VariableAnnualRate / 12)) * (1+Markup)
    # Source columns establish the annual index explicitly: Month 1 uses YearIndex=0;
    # Month 14 (AC) is in forecast Year 2 and uses YearIndex=1.  Therefore the supplied fixed
    # base is already the Year-1 amount, matching Foundry's period1 recurring-flow contract.
    def source_formula_assumptions(ppy=12, n=None, *, shape="rising"):
        n = int(n or ppy)
        if shape == "rising":
            beginning_auc, beginning_customers, attrition = 900_000.0, 0.0, 0.0
            channels = [{"name": "Explicit adds", "method": "explicit",
                         "params": {"new_customers_by_year": [1.0], "spend": 0.0},
                         "avg_auc_per_customer": 2_400_000.0}]
        elif shape == "flat":
            beginning_auc, beginning_customers, attrition = 1_000_000.0, 0.0, 0.0
            channels = []
        elif shape == "falling":
            beginning_auc, beginning_customers, attrition = 1_200_000.0, 1.0, .50
            channels = []
        else:
            raise ValueError(shape)
        return {
            "periods_per_year": ppy, "n_periods": n,
            "cac_feeds": {"Primary managed notional": {
                "series_id": "cac-auc-platform", "owner_module": "customer_acquisition",
                "beginning_auc": beginning_auc, "beginning_customers": beginning_customers,
                "attrition_rate": attrition, "intra_year_shape": "linear", "channels": channels,
            }},
            "cost_pools": [{
                "series_id": "pool-source-formula", "owner_module": "cost_pool",
                "name": "Eligible service costs", "components": [
                    {"kind": "assumption_cost_base", "series_id": "cost-base-fixed",
                     "name": "Fixed service cost", "allocation_pct": 1.0,
                     "flow_spec": {"trajectory": "growth", "value": 1_200.0, "period": "year",
                                   "base_position": "period1",
                                   "growth_spec": {"rate": .10, "period": "year",
                                                   "method": "step", "anchor": "model_year"}}},
                    {"kind": "balance_derived_cost", "series_id": "cost-base-variable",
                     "name": "Average-AUC variable cost", "allocation_pct": 1.0,
                     "source_kind": "managed_notional", "source_series_id": "cac-auc-platform",
                     "measure": "period_average", "rate_period": "year",
                     "rate_spec": {"source": "entered", "trajectory": "flat", "value": .012}},
                ],
            }],
        }

    sfm = source_formula_assumptions(12, 12)
    sfp = sfm["cost_pools"][0]
    sfa = cost_pool_series(sfp, sfm, 12, 12)
    # M1 AUC EOP = 1.1m, beginning AUC = 0.9m => average = 1.0m.
    # Fixed = 1200 * (1.10^0) / 12 = 100; variable = 1m * 1.20% / 12 = 1000.
    ck("source formula M1 uses YearIndex=0 and beginning AUC + M1 EOP for period-average AUC",
       _eq(sfa[0], 1_100.0))
    sf_fee, sf_opex = fee_stream_q(
        _stream("pool-source-formula", recovery=1.0, markup=.20), 1,
        {"cost_pool": {"pool-source-formula": sfa[0]}}, ppy=12)
    ck("exact source-formula parity: YearIndex=0 fixed cost + average-AUC variable cost + markup",
       _eq(sf_fee, 1_320.0) and _eq(sf_opex, 0.0))

    # Keep the alternate authoring semantic auditable without confusing it with workbook parity.
    # Declaring the same 1,200 as a prior-period base intentionally escalates once into Year 1.
    sf_prior = copy.deepcopy(sfm)
    sf_prior["cost_pools"][0]["components"][0]["flow_spec"]["base_position"] = "prior_period"
    prior_pool = cost_pool_series(sf_prior["cost_pools"][0], sf_prior, 12, 12)
    prior_fee = fee_stream_q(_stream("pool-source-formula", recovery=1.0, markup=.20), 1,
                             {"cost_pool": {"pool-source-formula": prior_pool[0]}}, ppy=12)[0]
    ck("prior-period fixed-cost authoring remains available but is not source-workbook parity",
       _eq(prior_pool[0], 1_110.0) and _eq(prior_fee, 1_332.0))

    # Year 2 should apply the first 10% escalation to the original 1,200 annual base.
    sf24 = source_formula_assumptions(12, 24)
    sf24["cac_feeds"]["Primary managed notional"]["channels"][0]["params"]["new_customers_by_year"] = [1.0, 0.0]
    sf24a = cost_pool_series(sf24["cost_pools"][0], sf24, 24, 12)
    # Isolate the fixed component to assert the exact annual escalation timing transparently.
    fixed_only = copy.deepcopy(sf24); fixed_only["cost_pools"][0]["components"] = [fixed_only["cost_pools"][0]["components"][0]]
    fixed24 = cost_pool_series(fixed_only["cost_pools"][0], fixed_only, 24, 12)
    ck("source-formula fixed base uses ^0 in Year 1 and ^1 in Year 2",
       _eq(fixed24[0], 100.0) and _eq(fixed24[12], 110.0)
       and _eq(sum(fixed24[:12]), 1_200.0) and _eq(sum(fixed24[12:24]), 1_320.0))

    sfq = source_formula_assumptions(4, 4)
    sfqa = cost_pool_series(sfq["cost_pools"][0], sfq, 4, 4)
    ck("quarterly source-formula cost pool sums canonical monthly accruals",
       _eq(sfqa[0], sum(sfa[:3])) and _eq(sfqa[0], 3_900.0))
    # Q1 quarter-end AUC is 1.5m. The forbidden proxy would be 1.5m * 1.2% / 4 = 4,500
    # variable cost, while exact monthly-average accrual is 3,600 variable + 300 fixed = 3,900.
    ck("quarterly average-AUC economics do not collapse to quarter-end AUC × annual rate / 4",
       not _eq(sfqa[0], (1_500_000.0 * .012 / 4.0) + (1_200.0 / 4.0)))
    ck("source-formula annual economics are monthly/quarterly cadence-equivalent",
       _eq(sum(sfa), sum(sfqa)) and _eq(sum(sfa), 26_400.0))

    # Balance-source catalog advertises only canonical monthly sources, not generic quarterly
    # balances whose intra-quarter path Foundry would have to invent.
    sfm["cac_feeds"]["Primary managed notional"]["customer_count_series_id"] = "cac-count-platform"
    bcat = cost_pool_balance_source_catalog(sfm)
    ck("cost-pool balance source catalog exposes only hard-typed canonical monthly AUC Series",
       bcat == [{"source_kind": "managed_notional", "series_id": "cac-auc-platform",
                "name": "Primary managed notional", "feed": "Primary managed notional",
                "owner_module": "customer_acquisition", "semantic_type": "auc_end",
                "measure_semantic": "canonical_monthly_balance"}]
       and all(x.get("series_id") != "cac-count-platform" for x in bcat))

    wrong_count_source = copy.deepcopy(sfm)
    wrong_count_source["cost_pools"][0]["components"][1]["source_series_id"] = "cac-count-platform"
    try: cost_pool_series(wrong_count_source["cost_pools"][0], wrong_count_source, 12, 12); count_as_auc_failed = False
    except ValueError as e: count_as_auc_failed = "customer-count Series" in str(e) and "canonical AUC" in str(e)
    ck("balance-derived cost rejects CAC customer-count Series even when it belongs to the same feed", count_as_auc_failed)

    # Rising, flat, and falling AUC must all preserve monthly economics when presentation is quarterly.
    shape_parity = True
    for shape in ("rising", "flat", "falling"):
        mm = source_formula_assumptions(12, 12, shape=shape)
        qq = source_formula_assumptions(4, 4, shape=shape)
        ma0 = cost_pool_series(mm["cost_pools"][0], mm, 12, 12)
        qa0 = cost_pool_series(qq["cost_pools"][0], qq, 4, 4)
        shape_parity = shape_parity and _eq(sum(ma0), sum(qa0)) and all(
            _eq(qa0[q], sum(ma0[q*3:(q+1)*3])) for q in range(4))
    ck("rising / flat / falling AUC all preserve monthly-to-quarterly cost-pool economics", shape_parity)

    # Period-end remains a valid explicit measure, but it is intentionally different from the
    # workbook's period-average convention when the balance is moving.
    eop_case = copy.deepcopy(sfm)
    eop_case["cost_pools"][0]["components"] = [eop_case["cost_pools"][0]["components"][1]]
    eop_case["cost_pools"][0]["components"][0]["measure"] = "period_end"
    eop_m1 = cost_pool_series(eop_case["cost_pools"][0], eop_case, 12, 12)[0]
    ck("balance-derived cost supports explicit period-end vs period-average measure semantics",
       _eq(eop_m1, 1_100.0) and not _eq(eop_m1, 1_000.0))

    bad_balance = copy.deepcopy(sfm)
    bad_balance["cost_pools"][0]["components"][1]["source_series_id"] = "missing-auc"
    try: cost_pool_series(bad_balance["cost_pools"][0], bad_balance, 12, 12); bad_balance_failed = False
    except ValueError as e: bad_balance_failed = "expected exactly one" in str(e)
    ck("balance-derived cost fails closed on missing canonical monthly balance source", bad_balance_failed)

    bad_base_position = copy.deepcopy(manual)
    bad_base_position["cost_pools"][0]["components"][0]["flow_spec"]["base_position"] = "prior_period"
    try: cost_pool_series(bad_base_position["cost_pools"][0], bad_base_position, 12, 12); bad_bp_failed = False
    except ValueError as e: bad_bp_failed = "requires trajectory=growth" in str(e)
    ck("prior-growth-period base timing is allowed only for Growth cost-base trajectories", bad_bp_failed)

    # --- pricing: recovery and markup stay separate; pool is not /ppy periodized again ---
    s = _stream()
    inc, opex = fee_stream_q(s, 1, {"cost_pool": {"pool-platform": 18_000.0}}, ppy=12)
    ck("cost recovery applies pool × recovery × (1 + markup)", _eq(inc, 17_820.0))
    ck("cost recovery observational link posts no fee-product expense", _eq(opex, 0.0))

    # Identical annual source economics in monthly vs quarterly cadence.
    aq = _assumptions(4, 4); am = _assumptions(12, 12)
    pq = cost_pool_series(aq["cost_pools"][0], aq, 4, 4)
    pm = cost_pool_series(am["cost_pools"][0], am, 12, 12)
    fq = sum(fee_stream_q(s, q, {"cost_pool": {"pool-platform": pq[q-1]}}, ppy=4)[0] for q in range(1, 5))
    fm = sum(fee_stream_q(s, q, {"cost_pool": {"pool-platform": pm[q-1]}}, ppy=12)[0] for q in range(1, 13))
    # annual eligible pool = 30k*4*.8 + 300k*.4 = 216k; fee = 216k*.9*1.1 = 213,840
    ck("cost recovery annual economics are quarterly/monthly cadence-stable",
       _eq(fq, 213_840.0) and _eq(fm, 213_840.0) and _eq(fq, fm))

    # Markup is a dimensionless Series level, including growth / explicit paths.
    growth_markup = {
        "value": .10, "trajectory": "growth",
        "growth_spec": {"rate": .50, "period": "year", "method": "step", "anchor": "model_year"},
    }
    sg = _stream(markup_obj=growth_markup)
    g1 = fee_stream_q(sg, 1, {"cost_pool": {"pool-platform": 100.0}}, ppy=4)[0]
    g5 = fee_stream_q(sg, 5, {"cost_pool": {"pool-platform": 100.0}}, ppy=4)[0]
    ck("markup Growth uses the standard Series level path without annualizing the cost pool",
       _eq(g1, 99.0) and _eq(g5, 103.5))
    explicit_markup = {
        "value": .10, "trajectory": "explicit_schedule", "period": "year", "resolution": "step",
        "schedule": {"1": .10, "2": .20},
    }
    se = _stream(markup_obj=explicit_markup)
    ck("explicit markup schedule changes pricing while preserving source dollars",
       _eq(fee_stream_q(se, 1, {"cost_pool": {"pool-platform": 100.0}}, ppy=12)[0], 99.0)
       and _eq(fee_stream_q(se, 24, {"cost_pool": {"pool-platform": 100.0}}, ppy=12)[0], 108.0))

    # --- fail-closed contract ---
    bad = copy.deepcopy(s); bad["basis"] = "balance"
    try: _validate_fee_stream_shape(bad); raised_basis = False
    except ValueError: raised_basis = True
    ck("cost_pool cannot masquerade as balance basis", raised_basis)

    bad = copy.deepcopy(s); bad["driver"]["trajectory"] = "derived"
    try: _validate_fee_stream_shape(bad); raised_traj = False
    except ValueError: raised_traj = True
    ck("cost_pool rejects derived coefficient semantics that would periodize recovery", raised_traj)

    bad = copy.deepcopy(s); bad["cost"] = {"kind": "per_unit", "params": {"per_unit": 1}}
    try: _validate_fee_stream_shape(bad); raised_cost = False
    except ValueError as e: raised_cost = "already posted" in str(e)
    ck("cost recovery rejects a second fee-product expense posting", raised_cost)

    bad = copy.deepcopy(s); bad["rate"]["params"]["recovery_pct"] = 1.25
    try: _validate_fee_stream_shape(bad); raised_recovery = False
    except ValueError: raised_recovery = True
    ck("recovery percentage fails closed outside 0..100%", raised_recovery)

    missing_ctx = False
    try: fee_stream_q(s, 1, {"cost_pool": {}}, ppy=12)
    except ValueError as e: missing_ctx = "unavailable" in str(e)
    ck("missing cost-pool evaluator context fails closed", missing_ctx)

    circular = copy.deepcopy(a)
    circular["nie_detail"]["workforce"]["roles"][0]["activation"] = {
        "metric": "managed_notional_end", "source": "Platform services", "operator": ">=", "value": 1,
    }
    try: cost_pool_series(circular["cost_pools"][0], circular, 12, 12); raised_circular = False
    except ValueError as e: raised_circular = "metric-triggered" in str(e) or "circular" in str(e)
    ck("metric-triggered Workforce expense is excluded from cost pools to avoid circularity", raised_circular)

    dup = copy.deepcopy(a)
    dup["cost_pools"][0]["components"].append(copy.deepcopy(dup["cost_pools"][0]["components"][0]))
    try: cost_pool_series(dup["cost_pools"][0], dup, 12, 12); duplicate_failed = False
    except ValueError as e: duplicate_failed = "duplicates" in str(e)
    ck("cost pool rejects duplicate inclusion of the same upstream Series", duplicate_failed)

    # --- full engine: linked pool creates fee income only; original NIE remains owned upstream ---
    def engine_pair(ppy):
        cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
        aa = cfg["assumptions"]
        aa.update(_assumptions(ppy, ppy))
        # Isolate the observational cost-pool contract from balance-sheet-sensitive
        # regulatory assessments: fee income legitimately changes assets, which can
        # change FDIC/OCC assessments without re-posting the linked upstream expense.
        aa["nie_detail"]["fdic_bp_ann"] = 0.0
        aa["nie_detail"]["occ_bp_ann"] = 0.0
        aa["obs_exposures"] = []
        base = copy.deepcopy(cfg)
        aa["obs_exposures"] = [{
            "name": "Affiliate Platform Services", "call_report_line": "obs", "_fee_product": True,
            "managed_notional": {"day1": 0, "trajectory": "flat"},
            "fee_streams": [_stream()],
        }]
        return run_v2(base)["financials"], run_v2(cfg)["financials"]

    bq, wq = engine_pair(4)
    bm, wm = engine_pair(12)
    # financial statement arrays are $000s, so annual fee delta should be 213.84.
    dq = sum(wq["is"]["fees"]) - sum(bq["is"]["fees"])
    dm = sum(wm["is"]["fees"]) - sum(bm["is"]["fees"])
    ck("full engine posts cost-recovery fee income in quarterly cadence", _eq(dq, 213.84, 1e-5))
    ck("full engine posts cost-recovery fee income in monthly cadence", _eq(dm, 213.84, 1e-5))
    ck("full engine cost-recovery fee is cadence-equivalent", _eq(dq, dm, 1e-5))
    ck("linked cost pool does not re-post upstream expense into Fee Product Costs",
       _eq(sum(wq["is"]["feeOpex"]) - sum(bq["is"]["feeOpex"]), 0.0)
       and _eq(sum(wm["is"]["feeOpex"]) - sum(bm["is"]["feeOpex"]), 0.0))
    # Because base and with-fee runs share identical Opex/Workforce assumptions, overhead
    # should remain identical; the only cost-recovery change is fee income.
    ck("linked cost pool leaves original Opex/Workforce expense posting unchanged",
       all(_eq(x, y, 1e-7) for x, y in zip(wq["is"]["overhead"], bq["is"]["overhead"]))
       and all(_eq(x, y, 1e-7) for x, y in zip(wm["is"]["overhead"], bm["is"]["overhead"])))

    # Full-engine assumption-driven cost-plus: no corresponding bank expense is invented.
    def manual_engine(ppy):
        cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
        aa = cfg["assumptions"]
        aa["periods_per_year"] = ppy; aa["n_periods"] = ppy
        aa["cost_pools"] = [{
            "series_id": "pool-manual", "owner_module": "cost_pool", "name": "Entered pricing cost base",
            "components": [{"kind": "assumption_cost_base", "series_id": "cost-base-manual",
                            "name": "Platform cost base", "allocation_pct": 1.0,
                            "flow_spec": {"trajectory": "flat", "value": 1_200_000.0, "period": "year"}}],
        }]
        base = copy.deepcopy(cfg); base["assumptions"]["obs_exposures"] = []
        aa["obs_exposures"] = [{
            "name": "Affiliate platform services", "call_report_line": "obs", "_fee_product": True,
            "managed_notional": {"day1": 0, "trajectory": "flat"},
            "fee_streams": [_stream("pool-manual", recovery=1.0, markup=.10)],
        }]
        return run_v2(cfg)["financials"], run_v2(base)["financials"]
    mm, mb = manual_engine(12); mqf, qb = manual_engine(4)
    md = sum(mm["is"]["fees"]) - sum(mb["is"]["fees"]); qd = sum(mqf["is"]["fees"]) - sum(qb["is"]["fees"])
    ck("assumption-driven cost-plus fee produces 100% recovery plus markup in full engine",
       _eq(md, 1320.0, 1e-5) and _eq(qd, 1320.0, 1e-5) and _eq(md, qd, 1e-5))
    ck("assumption-driven cost base does not invent Fee Product operating expense",
       _eq(sum(mm["is"]["feeOpex"]) - sum(mb["is"]["feeOpex"]), 0.0, 1e-8)
       and _eq(sum(mqf["is"]["feeOpex"]) - sum(qb["is"]["feeOpex"]), 0.0, 1e-8))

    # Full-engine exact source formula. Both cost components are pricing-only; the fee is the
    # only financial-statement posting introduced by this mechanic.
    def source_formula_engine(ppy):
        cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
        aa = cfg["assumptions"]
        sf = source_formula_assumptions(ppy, ppy)
        aa["periods_per_year"] = ppy; aa["n_periods"] = ppy
        aa["cac_feeds"] = sf["cac_feeds"]; aa["cost_pools"] = sf["cost_pools"]
        aa.setdefault("nie_detail", {})["fdic_bp_ann"] = 0.0; aa["nie_detail"]["occ_bp_ann"] = 0.0
        base = copy.deepcopy(cfg); base["assumptions"]["obs_exposures"] = []
        aa["obs_exposures"] = [{
            "name": "Affiliate platform services", "call_report_line": "obs", "_fee_product": True,
            "managed_notional": {"day1": 0, "trajectory": "flat"},
            "fee_streams": [_stream("pool-source-formula", recovery=1.0, markup=.20)],
        }]
        # Public run is rounded to cents of $000s for reporting; raw engine output retains
        # dollar precision and is the authoritative integration parity check.  Keep the full
        # public result as well because resolved cost pools are an audit surface, not a posting.
        public = run_v2(cfg); public_base = run_v2(base)
        return run_pf_a(cfg), run_pf_a(base), public["financials"], public_base["financials"], public
    sfm_raw, sfm_raw_base, sfm_fin, sfm_base, sfm_public = source_formula_engine(12)
    sfq_raw, sfq_raw_base, sfq_fin, sfq_base, sfq_public = source_formula_engine(4)
    def _affiliate_fees(raw):
        return next(p["fees"] for p in raw["products"] if p.get("name") == "Affiliate platform services")
    sfm_raw_fee = _affiliate_fees(sfm_raw); sfq_raw_fee = _affiliate_fees(sfq_raw)
    ck("full engine reproduces literal source formula including first-month YearIndex=0 fee dollars",
       _eq(sfm_raw_fee[0], 1_320.0, 1e-6) and _eq(sfq_raw_fee[0], 3_900.0 * 1.20, 1e-6))
    ck("full-engine source formula is cadence-equivalent over the year before presentation rounding",
       _eq(sum(sfm_raw_fee), 31_680.0, 1e-5) and _eq(sum(sfq_raw_fee), 31_680.0, 1e-5))
    ck("source-formula cost-pool components do not post Fee Product operating expense",
       _eq(sum(sfm_fin["is"]["feeOpex"]) - sum(sfm_base["is"]["feeOpex"]), 0.0, 1e-8)
       and _eq(sum(sfq_fin["is"]["feeOpex"]) - sum(sfq_base["is"]["feeOpex"]), 0.0, 1e-8))
    ck("public audit output surfaces resolved eligible cost without changing its non-posting semantic",
       sfm_public.get("cost_pools", {}).get("series", {}).get("pool-source-formula", [None])[0] == 1.1
       and sfq_public.get("cost_pools", {}).get("series", {}).get("pool-source-formula", [None])[0] == 3.9
       and sfm_public.get("cost_pools", {}).get("posting_semantic") == "non_posting_pricing_source"
       and sfm_public.get("cost_pools", {}).get("units") == "$000s / engine period")

    # Config-level stable-ID/ref validation.
    valid_cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    valid_cfg["assumptions"].update(_assumptions(4, 4))
    valid_cfg["assumptions"]["obs_exposures"] = [{
        "name": "Affiliate Platform Services", "call_report_line": "obs", "_fee_product": True,
        "managed_notional": {"day1": 0, "trajectory": "flat"}, "fee_streams": [_stream()],
    }]
    try: validate_config_v2(valid_cfg); valid_ok = True
    except ConfigErrorV2 as e:
        print("validation error", e); valid_ok = False
    ck("full config accepts stable cost-pool link", valid_ok)
    broken = copy.deepcopy(valid_cfg)
    broken["assumptions"]["obs_exposures"][0]["fee_streams"][0]["driver"]["ref"] = "missing-pool"
    try: validate_config_v2(broken); broken_failed = False
    except ConfigErrorV2 as e: broken_failed = "missing-pool" in str(e)
    ck("full config fails closed on broken cost-pool ref", broken_failed)
    empty = copy.deepcopy(valid_cfg)
    empty["assumptions"]["cost_pools"][0]["components"] = []
    try: validate_config_v2(empty); empty_failed = False
    except ConfigErrorV2 as e: empty_failed = "at least one eligible expense component" in str(e)
    ck("referenced empty cost pool fails closed instead of silently producing zero revenue", empty_failed)

    source_cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    source_cfg["assumptions"].update(source_formula_assumptions(4, 4))
    source_cfg["assumptions"]["obs_exposures"] = [{
        "name": "Affiliate platform services", "call_report_line": "obs", "_fee_product": True,
        "managed_notional": {"day1": 0, "trajectory": "flat"},
        "fee_streams": [_stream("pool-source-formula", recovery=1.0, markup=.20)],
    }]
    try: validate_config_v2(source_cfg); source_valid = True
    except ConfigErrorV2 as e: print("source validation error", e); source_valid = False
    ck("full config validates heterogeneous entered + balance-derived cost-pool components", source_valid)

    # New cost-pool components own stable Series IDs and must not collide with any other
    # Foundry Series identity.
    colliding = copy.deepcopy(source_cfg)
    colliding["assumptions"]["cost_pools"][0]["components"][0]["series_id"] = "cac-auc-platform"
    try: validate_config_v2(colliding); collision_failed = False
    except ConfigErrorV2 as e: collision_failed = "series_id values must be unique" in str(e)
    ck("cost-pool component stable IDs participate in global Series uniqueness", collision_failed)

    # Actual dependency-cycle guard: valid one-way CAC -> AUC -> pool -> fee remains allowed,
    # while fee-linked Opex cannot feed back into the same pool directly or through CAC.
    direct_cycle = copy.deepcopy(valid_cfg)
    direct_cycle["assumptions"]["nie_detail"]["categories"][0]["linked_components"] = [
        {"driver": "fee_income", "rate_spec": {"source": "entered", "trajectory": "flat", "value": .10}}
    ]
    try: validate_config_v2(direct_cycle); direct_cycle_failed = False
    except ConfigErrorV2 as e: direct_cycle_failed = "circular dependency" in str(e)
    ck("cost pool fails closed on direct Opex -> pool -> fee -> same-Opex loop", direct_cycle_failed)

    cac_cycle = copy.deepcopy(source_cfg)
    cac_cycle["assumptions"].setdefault("nie_detail", {})["categories"] = [{
        "series_id": "opex-acq", "owner_module": "operating_expense", "name": "Acquisition",
        "flow_spec": {"trajectory": "flat", "value": 120_000.0, "period": "year"},
        "linked_components": [{"driver": "fee_income",
                               "rate_spec": {"source": "entered", "trajectory": "flat", "value": .05}}],
    }]
    fd = cac_cycle["assumptions"]["cac_feeds"]["Primary managed notional"]
    fd["channels"] = [{
        "name": "Paid acquisition", "method": "spend_cac",
        "params": {"cac": 1000.0}, "avg_auc_per_customer": 100_000.0,
        "driver_specs": {"spend": {"source": "link", "link": {
            "kind": "operating_expense_category", "series_id": "opex-acq", "aggregation": "sum"}}},
    }]
    try: validate_config_v2(cac_cycle); cac_cycle_failed = False
    except ConfigErrorV2 as e: cac_cycle_failed = "circular dependency" in str(e)
    ck("cost pool fails closed on Opex -> CAC -> AUC -> pool -> fee -> Opex loop", cac_cycle_failed)

    unused_spec = copy.deepcopy(cac_cycle)
    # Switch the selected acquisition equation to explicit params. The stale spend link is now
    # unused and must not create a false-positive dependency cycle.
    unused_spec["assumptions"]["cac_feeds"]["Primary managed notional"]["channels"][0].update({
        "method": "explicit", "params": {"new_customers_by_year": [1.0], "spend": 0.0},
        "avg_auc_per_customer": 100_000.0,
    })
    try: validate_config_v2(unused_spec); unused_ok = True
    except ConfigErrorV2 as e: print("unused-spec validation error", e); unused_ok = False
    ck("cycle guard follows active CAC equation operands instead of stale unused links", unused_ok)

    # Guide Me maps the generic mechanic without inventing Reg W or a sixth basis.
    from .fee_guide import validate_guide_plan, render_guide_plan, fee_guide_manifest
    guide_stream = {
        "name": "Platform services fee", "basis": "transaction",
        "driver_source": "cost_pool", "driver_trajectory": "flat",
        "driver_period": "not_applicable", "driver_resolution": "not_applicable",
        "stock_multiplier_trajectory": "not_applicable", "stock_multiplier_period": "not_applicable",
        "stock_multiplier_resolution": "not_applicable",
        "pricing_trajectory": "flat", "pricing_period": "not_applicable",
        "pricing_resolution": "not_applicable",
        "coefficient_kind": "not_applicable", "coefficient_period": "not_applicable",
        "coefficient_trajectory": "not_applicable", "flat_amount_trajectory": "not_applicable",
        "rate_behavior": "cost_recovery", "cost_kind": "none",
    }
    gplan = {"status": "plan", "product_label": "Affiliate platform services",
             "managed_notional_source": "not_needed", "streams": [guide_stream],
             "questions": [], "unsupported_mechanics": []}
    try:
        gv = validate_guide_plan(gplan); guide_ok = True
    except Exception as e:
        print("guide validation error", e); guide_ok = False; gv = None
    ck("Guide Me accepts cost_pool + transaction + cost_recovery without a new basis",
       guide_ok and gv["streams"][0]["basis"] == "transaction")
    rendered = render_guide_plan(gplan) if guide_ok else {"stream_guides": []}
    gst = " ".join(rendered.get("stream_guides", [{}])[0].get("steps", [])) if guide_ok else ""
    ck("Guide Me instructions preserve separate pool allocation, recovery, and markup controls",
       "Eligible / allocated" in gst and "Recovery" in gst and "Markup" in gst)
    ck("Guide Me recognizes heterogeneous non-posting cost bases without Reg W ontology",
       "entered cost base" in gst.lower() and "balance-linked cost" in gst.lower() and "pricing-only" in gst.lower())
    mf = fee_guide_manifest()
    ck("Guide Me manifest exposes generic cost mechanics rather than Reg W ontology",
       any(x["id"] == "cost_pool" for x in mf["driver_sources"])
       and any(x["id"] == "cost_recovery" for x in mf["rate_behaviors"])
       and all(x["id"] != "reg_w" for x in mf["bases"]))

    # Browser contract: compact authoring keeps pool allocation, recovery, markup, and no-cost guard visible.
    html = Path("web/console_v2.html").read_text()
    ck("Fee Product UI exposes linked cost-pool source", "Cost pool — eligible cost base" in html)
    ck("Fee Product UI supports assumption-driven non-posting eligible cost bases",
       "+ entered cost base" in html and "Entered cost base · non-posting" in html and "Pricing assumption only" in html)
    ck("Fee Product UI gives entered cost bases Flat/Growth/Explicit natural-period authoring",
       "feeCostPoolEnteredTrajectory" in html and "feeCostPoolEnteredPeriod" in html and "_feeSetCostPoolEnteredSchedule" in html)
    ck("Fee Product UI exposes explicit first-period vs prior-growth-period base timing",
       "feeCostPoolEnteredBasePosition" in html and "Prior growth period (escalate once into model)" in html)
    ck("Fee Product UI supports hard-typed non-posting AUC-derived eligible costs with source preview",
       "+ balance-linked cost" in html and "Balance-linked cost · non-posting" in html
       and "Period average" in html and "canonical monthly balance path" in html
       and "Selected balance Series" in html and "before multiplier" in html
       and "Client-count Series are not valid balance sources" in html)
    ck("Fee Product UI keeps pricing basis distinct from driver source", "Basis (calculation)" in html and "Basis (what it\'s charged on)" not in html)
    ck("Fee Product UI separates pool allocation from downstream recovery", "Eligible / allocated" in html and "Recovery (% of eligible cost pool)" in html)
    ck("Fee Product UI exposes Series-style Markup path", "Markup path" in html and "Markup schedule (%)" in html)
    ck("Fee Product UI keeps Reg W/transfer-pricing rationale as optional memo context, not ontology",
       "Pricing / regulatory memo (optional)" in html and "pricing_memo" in html)
    ck("Fee Product UI makes non-posting cost-base guard explicit",
       "cost base is non-posting here" in html and "double-count or invent expense" in html)
    ck("Fee Product UI safely unwinds cost-pool-only state when basis changes", "feeStreamBasisChange" in html and 'st.driver.source==="cost_pool"&&v!=="transaction"' in html)
    ck("Fee Product UI provides a safe single-reference shared-pool delete path", "feeCostPoolDeleteFromStream" in html and "Delete pool" in html)

    # Execute the shipped renderer for an authored cost-recovery stream (not just string inventory).
    ha = html.index("function _feeCoeffScheduleText("); hb = html.index("function fieldsFor(", ha)
    fa = html.index("function fieldsFor("); fb = html.index("function lineOptionsFor", fa)
    hjs, fjs = html[ha:hb], html[fa:fb]
    node = (
        "const cfg={assumptions:{cac_feeds:{},nie_detail:{categories:[{series_id:'opex-tech',name:'Technology'}],workforce:{roles:[{series_id:'wf-count',compensation_series_id:'wf-comp',expense_series_id:'wf-exp',role:'Platform Ops',hire_period:1}]}},cost_pools:[{series_id:'pool-platform',owner_module:'cost_pool',name:'Platform Services Eligible Costs',components:[{kind:'operating_expense_category',series_id:'opex-tech',allocation_pct:.8},{kind:'workforce_role_expense',series_id:'wf-exp',allocation_pct:.4},{kind:'assumption_cost_base',series_id:'cost-base-entered',name:'Entered platform base',allocation_pct:1,flow_spec:{trajectory:'flat',value:1200000,period:'year'}}]}],obs_exposures:[]}};\n"
        "function esc(x){return String(x==null?'':x);} function PLAB(k){return k==='full'?'month':'Mth';} function PPY(){return 12;}\n"
        "function numInput(){return '<input>'; } function growthSpecInline(){return '<growth>'; } function _qGrowthToPeriod(x){return x||0;} function _pf(x){return +(String(x).replace(/,/g,''))||0;} function _seriesId(p){return p+'-stub';} function _ensureLinkableSeriesIds(){} function _feeBasisTileHtml(){return '<tile>'; } function renderContent(){} function refresh(){} function appStatus(){} function alert(){}\n"
        + hjs + fjs +
        "\nconst p={name:'Affiliate Platform Services',_fee_product:true,managed_notional:{day1:0,trajectory:'flat'},fee_streams:[{name:'Platform services fee',basis:'transaction',driver:{source:'cost_pool',ref:'pool-platform',trajectory:'flat',params:{}},rate:{behavior:'cost_recovery',params:{recovery_pct:.9,markup:{value:.1,trajectory:'flat',period:'year',resolution:'step'}}},cost:{kind:'none',params:{}},timing:{start_period:1}}]};"
        "\ncfg.assumptions.obs_exposures=[p]; const out=fieldsFor('obs',p,'assumptions.obs_exposures.0'); console.log(JSON.stringify({ok:out.includes('Platform Services Eligible Costs')&&out.includes('Operating Expense: Technology')&&out.includes('Workforce expense: Platform Ops')&&out.includes('Recovery (% of eligible cost pool)')&&out.includes('Markup path')&&out.includes('Entered platform base')&&out.includes('Entered cost base · non-posting')&&out.includes('cost base is non-posting here')}));"
    )
    nr = subprocess.run(["node", "-e", node], text=True, capture_output=True)
    no = {}
    if nr.returncode == 0 and nr.stdout.strip():
        try: no = json.loads(nr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("cost-recovery Fee Product renders end-to-end without browser-runtime error",
       nr.returncode == 0 and no.get("ok") is True, nr.stderr.strip())

    # Execute the entered-cost-base authoring callbacks, including explicit schedule parsing.
    node2 = (
        "const cfg={assumptions:{cost_pools:[{series_id:'pool-manual',owner_module:'cost_pool',name:'Manual',components:[]}],nie_detail:{categories:[],workforce:{roles:[]}},obs_exposures:[],cac_feeds:{}}};\n"
        "function _pf(x){return +(String(x).replace(/,/g,''))||0;} function _seriesId(p){return p+'-id-'+Math.random().toString(36).slice(2);} function _ensureLinkableSeriesIds(){} function renderContent(){} function refresh(){} function appStatus(){} function alert(){} function fmtComma(x){return String(x);}\n"
        + hjs +
        "\nfeeCostPoolAddEntered('pool-manual'); feeCostPoolEnteredTrajectory('pool-manual',0,'explicit'); feeCostPoolEnteredPeriod('pool-manual',0,'year'); _feeSetCostPoolEnteredSchedule('pool-manual',0,'1,200\t1,500'); const c=cfg.assumptions.cost_pools[0].components[0]; console.log(JSON.stringify({kind:c.kind,alloc:c.allocation_pct,period:c.flow_spec.period,vals:c.flow_spec.values}));"
    )
    nr2 = subprocess.run(["node", "-e", node2], text=True, capture_output=True)
    no2 = {}
    if nr2.returncode == 0 and nr2.stdout.strip():
        try: no2 = json.loads(nr2.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("entered cost-base UI callbacks author and persist a non-posting Explicit annual Series",
       nr2.returncode == 0 and no2.get("kind") == "assumption_cost_base" and no2.get("period") == "year"
       and no2.get("vals") == [1_200_000, 1_500_000], nr2.stderr.strip())

    node3 = (
        "const cfg={assumptions:{cost_pools:[{series_id:'pool-b',owner_module:'cost_pool',name:'Balance pool',components:[]}],nie_detail:{categories:[],workforce:{roles:[]}},obs_exposures:[],cac_feeds:{Wealth:{series_id:'cac-auc-ui',customer_count_series_id:'cac-count-ui',beginning_auc:0,channels:[]}}}};\n"
        "function esc(x){return String(x);} function _pf(x){return +(String(x).replace(/,/g,''))||0;} function _seriesId(p){return p+'-id';} function _ensureLinkableSeriesIds(){} function renderContent(){} function refresh(){} let statusMsg=''; function appStatus(_k,m){statusMsg=String(m||'');} function alert(){} function fmtComma(x){return String(x);} const lastRes={customer_acquisition:{Wealth:{aucEndByMonth:[83333.333,166666.667,250000],customerEndByMonth:[70,140,210],customerAverageByPeriod:[35,105,175]}}};\n"
        + hjs +
        "\nfeeCostPoolAddBalance('pool-b'); feeCostPoolBalanceMeasure('pool-b',0,'period_average'); feeCostPoolBalanceRate('pool-b',0,'1.2'); feeCostPoolBalanceRatePeriod('pool-b',0,'year'); const c=cfg.assumptions.cost_pools[0].components[0]; const preview=_feeCostPoolBalancePreviewHtml(c.source_series_id,c.measure); feeCostPoolBalanceSource('pool-b',0,'cac-count-ui'); console.log(JSON.stringify({c:c,preview:preview,status:statusMsg}));"
    )
    nr3 = subprocess.run(["node", "-e", node3], text=True, capture_output=True)
    no3 = {}
    if nr3.returncode == 0 and nr3.stdout.strip():
        try: no3 = json.loads(nr3.stdout.strip().splitlines()[-1])
        except Exception: pass
    c3 = no3.get("c") or {}
    ck("balance-linked cost UI hard-binds AUC semantics, previews the selected measure, and rejects client-count IDs",
       nr3.returncode == 0 and c3.get("kind") == "balance_derived_cost"
       and c3.get("source_series_id") == "cac-auc-ui" and c3.get("source_semantic") == "auc_end"
       and c3.get("source_owner_module") == "customer_acquisition" and c3.get("measure") == "period_average"
       and c3.get("rate_period") == "year" and _eq((c3.get("rate_spec") or {}).get("value"), .012)
       and "M1 41666.6665" in str(no3.get("preview") or "") and "M2 125000" in str(no3.get("preview") or "")
       and "M1 35" not in str(no3.get("preview") or "")
       and "before multiplier" in str(no3.get("preview") or "")
       and "Client-count Series are not valid balance sources" in str(no3.get("status") or ""),
       nr3.stderr.strip())

    print(f"\n{P} passed, {F} failed")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
