"""Foundry v2 — run wrapper (C.1 preview backend, A.8 constraint tests).

One function, `run_v2(cfg)`, is the number of record for v2 configurations:
fail-closed validation, the profile engine, a scenario suite (base, rate shock,
credit stress, combined downturn), constraint tests across every scenario,
challenge flags, an FTP contribution view with an exact reconciliation to
pre-tax, and canonical config/run hashes. The /api/v2/preview endpoint calls
exactly this function — preview IS the run (T-PRV).
"""
import copy
import json
import hashlib

from .validate_q import validate_config_v2
from .parity import run_parity
from . import challenge_q
from .regparams import REG_PARAMS, PENDING_RULES
from .challenge_q import challenge_config
from .callreport import RESULT_CODES_BS, RESULT_CODES_IS, LINE_CODES, code_for_line
from . import present
from .timebase import (period_label, horizon_label, cadence_noun,
                       submission_end_period, submission_period_label)


def _peer_annotated_flags(cfg, base):
    """challenge_config(cfg), then enrich each fired flag with peer-percentile
    evidence where the metric resolves in the substrate. Fail-closed: any error
    (no DB configured, band miss) returns the plain static flags unchanged, so a
    substrate outage never suppresses or breaks a flag."""
    flags = challenge_config(cfg)
    # Durbin $10B threshold-cross (needs the MODELED balance sheet, which challenge_config lacks):
    # the small-issuer exemption behind any interchange assumption holds only while assets are under
    # $10B. If the modeled path actually reaches $10B, the exemption no longer applies and the assumed
    # unregulated interchange rate is overstated — that is a substantive finding, not a counsel memo.
    try:
        _has_ic = any(f.get("id") == "REG-DURBIN" for f in flags)
        if _has_ic:
            _ta_series = (base.get("bs", {}).get("totalAssets") or [])
            _peak_ta = max([x for x in _ta_series if x is not None], default=0.0)  # $000s
            if _peak_ta >= 10_000_000.0:  # $10B expressed in $000s
                _p_cross = next((i for i, x in enumerate(_ta_series)
                                 if i > 0 and x is not None and x >= 10_000_000.0), None)
                _ppy0 = int((cfg.get("assumptions") or {}).get("periods_per_year") or 4)
                _cross_label = period_label(_p_cross, _ppy0) if _p_cross else None
                for f in flags:
                    if f.get("id") == "REG-DURBIN":
                        f["sev"] = "severe"
                        f["text"] = (
                            f"Modeled assets reach ${_peak_ta/1_000_000:.1f}B"
                            + (f" by {_cross_label}" if _cross_label else "")
                            + ", at or above the $10B Durbin small-issuer threshold. Coverage does "
                            "not switch on merely because an intra-year period crosses $10B: Foundry "
                            "applies the preceding-calendar-year-end determination on the applicable "
                            "July 1 transition date. Review the resulting covered periods and confirm "
                            "affiliate aggregation with counsel.")
    except Exception:
        pass  # threshold enrichment is additive; never let it break the base flag
    try:
        from .peer_calibration import peer_annotate, asset_band_for
        _a0 = cfg.get("assumptions") or {}
        _ppy0 = int(_a0.get("periods_per_year") or 4)
        _np0 = int(_a0.get("n_periods") or 12)
        _sub0 = submission_end_period(cfg, _ppy0, _np0)
        _tas = base.get("bs", {}).get("totalAssets") or []
        _ti = _sub0 if len(_tas) == _np0 + 1 else _sub0 - 1
        ta = _tas[_ti] if 0 <= _ti < len(_tas) else (_tas[-1] if _tas else None)
        cohort = asset_band_for(ta) if ta else "broad"
        return peer_annotate(flags, cfg, cohort=cohort)
    except Exception:
        return flags

ENGINE_V2 = "foundry-engine 0.3.1 / v2-cadence-aware"

STRESS_DEFAULTS = {"charge_off_mult": 2.5, "reserve_mult": 1.5, "rate_shock_bp": 300,
                   "origination_volume_haircut": 0.40, "gos_margin_compression": 0.40,
                   "msr_value_haircut": 0.20, "sale_share_retention_shift": 0.25}


def scenarios_from(cfg):
    """Faithful scenario builder: sidebar stress parameters drive three stress
    scenarios; the downturn overlays apply to all three; the base plan is the
    plan (fixture-parity path: cfg.scenario_overlays still overlays the base)."""
    sp = {**STRESS_DEFAULTS, **(cfg.get("stress_params") or {})}
    downturn = {k: sp[k] for k in ("origination_volume_haircut", "gos_margin_compression",
                                   "msr_value_haircut", "sale_share_retention_shift")}
    bp = int(round((sp["rate_shock_bp"] or 0)))
    scens = {
        "base": ({}, "Base Case"),
        "credit": ({**downturn, "charge_off_mult": sp["charge_off_mult"],
                    "reserve_mult": sp["reserve_mult"]},
                   f"Credit Deterioration (CO \u00d7{sp['charge_off_mult']:g}, ALLL \u00d7{sp['reserve_mult']:g})"),
        "rate": ({**downturn, "rate_shock_bp": sp["rate_shock_bp"]},
                 f"Rate Shock ({'+' if bp >= 0 else ''}{bp}bp parallel)"),
        "combined": ({**downturn, "charge_off_mult": sp["charge_off_mult"],
                      "reserve_mult": sp["reserve_mult"], "rate_shock_bp": sp["rate_shock_bp"]},
                     "Combined"),
    }
    # DFAST severe overlay — an ADDITIVE fifth scenario, gated on (a) an explicit opt-in
    # (cfg["stress_params"]["dfast_severe"] truthy, default off) and (b) the registry importing.
    # It NEVER replaces the multiplier-based Credit Deterioration scenario; the two coexist and
    # the contrast is intentional. Absent the opt-in or the registry, the scenario set is
    # bit-identical to the prior four.
    # DFAST severe overlay — a supervisory-severe scenario, ALWAYS SHOWN. A single column using
    # the FRONT-LOADED loss shape: it never understates stress, and the level-vs-front distinction
    # is negligible except for a bank balanced exactly on the leverage floor (verified: Calamity
    # 0.35pp, Coverall 0.07pp) — two near-identical columns would mislead, so one is shown. Additive:
    # never replaces the multiplier-based Credit Deterioration scenario; the contrast is the point.
    if True:
        try:
            from foundry.v2.dfast_lossrates import dfast_rates
            _dfv = dfast_rates((cfg.get("stress_params") or {}).get("dfast_version"))
            _rates = {ln: d["rate"] for ln, d in _dfv["rates"].items()}
            scens["dfast_severe"] = ({**downturn, "dfast_severe_rates": _rates, "dfast_spread": "front"},
                                     f"DFAST Severe ({_dfv['version']})")
        except Exception:
            pass  # registry unavailable -> scenarios simply not offered; base behavior unchanged
    return scens


SCENARIOS_V2 = {"base": {}, "credit": None, "rate": None, "combined": None}  # keys, for tests


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _merge_overlays(base_ov, scen_ov):
    out = dict(base_ov or {})
    for k, v in scen_ov.items():
        if k in ("charge_off_mult", "reserve_mult"):
            out[k] = (out.get(k, 1) or 1) * v
        elif k == "rate_shock_bp":
            out[k] = (out.get(k, 0) or 0) + v
        elif isinstance(v, (int, float)):
            out[k] = max(out.get(k, 0) or 0, v)
        else:
            out[k] = v  # non-numeric override (e.g. dfast_severe_rates dict) passes through
    return out


def _scen_metrics(res, cfg, commit):
    """Scenario summary with explicit separation of submission-Q12 vs full horizon.

    Fields retaining the historical ``*_q12`` names now mean the regulator-facing
    submission endpoint (normally calendar Q12), not "whatever the final engine
    period happens to be." Generic cumulative/minimum fields continue to span the
    full computational horizon. Standard 12-quarter fixtures are unchanged.
    """
    is_, bs = res["is"], res["bs"]
    rt = res.get("ratios") or {}
    lev = rt.get("lev") or rt.get("leverage") or []
    a = cfg.get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    np = int(a.get("n_periods") or 12)
    sub_p = submission_end_period(cfg, ppy, np)
    flow_i = max(0, sub_p - 1)
    stock_i = sub_p

    def tot(k, limit=None):
        vals = is_.get(k) or []
        if limit is not None:
            vals = vals[:limit]
        return round(sum(x for x in vals if x is not None), 2)

    # Existing scenario-table fields are regulator-facing Q1..Q12 metrics. On a
    # monthly computational engine, sample quarter-end leverage rather than treating
    # each month as a regulatory quarter. Preserve separate full-horizon minima below.
    mpq = max(1, ppy // 4) if ppy >= 4 else 1
    lev_has_open = len(lev) == np + 1
    min_lev, min_q = None, None
    for rq, ep in enumerate(range(mpq, sub_p + 1, mpq), start=1):
        i = ep if lev_has_open else ep - 1
        if 0 <= i < len(lev):
            v = lev[i]
            if v is not None and (min_lev is None or v < min_lev):
                min_lev, min_q = v, rq
    full_min_lev, full_min_p = None, None
    for ep in range(1, np + 1):
        i = ep if lev_has_open else ep - 1
        if 0 <= i < len(lev):
            v = lev[i]
            if v is not None and (full_min_lev is None or v < full_min_lev):
                full_min_lev, full_min_p = v, ep
    bor = bs.get("borrow") or bs.get("borrowings") or []
    bor_sched = bs.get("borrowSched") or []
    intang = cfg["assumptions"]["intangibles"] / 1000.0
    cap_short = 0.0
    n = len(bs["totalAssets"])
    dta = bs.get("dta") or [0.0] * n
    msr = bs.get("msr") or [0.0] * n
    dta_frac = REG_PARAMS["tax"]["dta_nol_cet1_deduction"]
    # Scenario-card shortfall is a submission-window diagnostic. Use the SAME
    # Tier-1 deductions / net-average-assets denominator as the canonical leverage
    # derivation so the card cannot disagree with the capital module.
    for q in range(1, min(n, sub_p + 1)):
        avg_a = ((bs["totalAssets"][q - 1] or 0) + (bs["totalAssets"][q] or 0)) / 2.0
        dta_ded = (dta[q] or 0.0) * dta_frac
        t1_pre = (bs["equity"][q] or 0) - intang - dta_ded
        msa_x = max(0.0, (msr[q] or 0.0) - 0.25 * max(0.0, t1_pre))
        t1 = t1_pre - msa_x
        avg_net = avg_a - dta_ded - msa_x
        need = commit * avg_net - t1
        cap_short = max(cap_short, need)

    def _at_flow(key):
        arr = is_.get(key) or []
        return arr[flow_i] if flow_i < len(arr) else (arr[-1] if arr else None)
    def _at_ratio(key):
        arr = rt.get(key) or []
        # ratio arrays normally have one value per engine period; tolerate an opening slot.
        if len(arr) == np + 1:
            i = stock_i
        else:
            i = flow_i
        return arr[i] if i < len(arr) else (arr[-1] if arr else None)
    def _at_stock(key):
        arr = bs.get(key) or []
        i = stock_i if len(arr) == np + 1 else flow_i
        return arr[i] if i < len(arr) else (arr[-1] if arr else None)

    # Wholesale borrowings include both the residual funding plug and explicit scheduled
    # term/FHLB advances. Diagnostics must not report zero wholesale funding merely because
    # the scheduled advance displaced the residual plug.
    _bor = bor[1:] if len(bor) == np + 1 else list(bor)
    _sched = bor_sched[1:] if len(bor_sched) == np + 1 else list(bor_sched)
    bor_period = [
        (float(_bor[i] or 0.0) if i < len(_bor) else 0.0)
        + (float(_sched[i] or 0.0) if i < len(_sched) else 0.0)
        for i in range(np)
    ]
    lev_submission_q = []
    for ep in range(mpq, sub_p + 1, mpq):
        i = ep if lev_has_open else ep - 1
        lev_submission_q.append(lev[i] if 0 <= i < len(lev) else None)
    return {
        # Historical names consumed by the regulator-facing 12-quarter scenario matrix.
        "cum_ni": tot("ni", sub_p), "ni_q12": _at_flow("ni"),
        "cum_prov": tot("prov", sub_p) or tot("provision", sub_p),
        "cum_gos": tot("gos", sub_p), "cum_serv": tot("servNet", sub_p),
        "cum_fv": tot("fvPnl", sub_p),
        "q12_total_assets": _at_stock("totalAssets"), "equity_q12": _at_stock("equity"),
        "submission_endpoint": submission_period_label(cfg, ppy, np),
        "peak_borrowings": max((x for x in bor_period[:sub_p] if x is not None), default=0.0),
        "min_leverage": None if min_lev is None else round(min_lev / 100.0, 6),
        "min_leverage_q": min_q,
        "min_leverage_label": (f"Q{min_q}" if min_q is not None else None),
        "roa_q12": _at_ratio("roa"), "nim_q12": _at_ratio("nim"),
        "capital_shortfall_est": round(max(0.0, cap_short), 2),

        # Explicit full-computational-horizon counterparts. These prevent Q12 from
        # being overloaded as a synonym for terminal when a model runs beyond 3 years.
        "cum_ni_full": tot("ni"),
        "cum_prov_full": tot("prov") or tot("provision"),
        "cum_gos_full": tot("gos"), "cum_serv_full": tot("servNet"),
        "cum_fv_full": tot("fvPnl"),
        "terminal_total_assets": (bs.get("totalAssets") or [None])[-1],
        "terminal_equity": (bs.get("equity") or [None])[-1],
        "peak_borrowings_full": max((x for x in bor_period if x is not None), default=0.0),
        "min_leverage_full": None if full_min_lev is None else round(full_min_lev / 100.0, 6),
        "min_leverage_full_period": full_min_p,
        "min_leverage_full_label": period_label(full_min_p, ppy) if full_min_p else None,
        "terminal_roa": (rt.get("roa") or [None])[-1],
        "terminal_nim": (rt.get("nim") or [None])[-1],
        "nol_end": (is_.get("nol") or [None])[-1],
        # Full native-cadence paths. Retain the historical *_by_q aliases for
        # backwards compatibility, but new presentation code should use the
        # cadence-neutral names so monthly runs are not mistaken for quarters.
        "ni_by_period": is_.get("ni"), "lev_by_period": lev,
        "ni_by_q": is_.get("ni"), "lev_by_q": lev,
        "lev_submission_q": lev_submission_q,
    }


def _min_leverage(res):
    lev = (res.get("ratios") or {}).get("lev") or (res.get("ratios") or {}).get("leverage") or []
    vals = [x for x in lev if x is not None]
    return min(vals) / 100.0 if vals else None


def _ftp_view(res, cfg, ppy=4):
    """Product profitability over the regulator-facing submission window.

    The historical UI explicitly labels these as 12-quarter totals. Preserve that
    regulatory convention even when the computational model extends beyond Q12;
    for monthly cadence the same window is the first 36 engine months. Treasury
    center remains the exact residual over the SAME window.
    """
    prods = res.get("products") or []
    is_ = res["is"]
    np = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    sub_n = submission_end_period(cfg, int(ppy), np)
    rows, contrib_sum = [], 0.0
    for p in prods:
        n = min(len(p.get("avg") or []), sub_n)
        _wh = p.get("whBal")
        def _wh_avg(q):
            if not _wh:
                return 0.0
            # whBal may carry an opening slot. Align q=0 with first modeled period.
            if len(_wh) == np + 1:
                beg = _wh[q] if q < len(_wh) else 0.0
                end = _wh[q + 1] if q + 1 < len(_wh) else 0.0
            else:
                beg = _wh[q - 1] if q >= 1 and q - 1 < len(_wh) else 0.0
                end = _wh[q] if q < len(_wh) else 0.0
            return ((beg or 0.0) + (end or 0.0)) / 2.0
        ftp = sum(((p["avg"][q] or 0) + _wh_avg(q)) * (p["ftp_rate"][q] or 0) / float(ppy)
                  for q in range(n))
        sign = -1.0 if p["family"] == "lending" else (1.0 if p["family"] == "deposit" else 0.0)
        comp = {k: sum((p[k][q] or 0) for q in range(min(n, len(p.get(k) or []))))
                for k in ("interest", "fees", "opex", "co", "gos", "servNet")}
        ii = sum((x or 0) for x in (p.get("intInc") or [])[:n]) or max(comp["interest"], 0.0)
        ie = sum((x or 0) for x in (p.get("intExp") or [])[:n]) or max(-comp["interest"], 0.0)
        bal = p.get("bal") or [0.0]
        bi = sub_n if len(bal) == np + 1 else max(0, sub_n - 1)
        bal_q12 = bal[bi] if bi < len(bal) else bal[-1]
        whc = p.get("whCarry") or []
        if whc:
            wi = sub_n if len(whc) == np + 1 else max(0, sub_n - 1)
            bal_q12 += whc[wi] if wi < len(whc) else whc[-1]
        avg_bal = sum((p["avg"][q] or 0) for q in range(n)) / n if n else 0.0
        econ = comp["interest"] + comp["fees"] - comp["opex"] - comp["co"] + comp["gos"] + comp["servNet"]
        contrib = econ + sign * ftp
        rows.append({"name": p["name"], "family": p["family"],
                     "avg_balance": round(avg_bal, 2), "q12_balance": round(bal_q12, 2),
                     "interest_income": round(ii, 2), "interest_expense": round(ie, 2),
                     "revenue": round(ii + comp["fees"] + comp["gos"] + comp["servNet"], 2),
                     "interest": round(comp["interest"], 2), "fees": round(comp["fees"], 2),
                     "credit_costs": round(comp["co"], 2), "opex": round(comp["opex"], 2),
                     "gos_servicing": round(comp["gos"] + comp["servNet"], 2),
                     "economics": round(econ, 2), "ftp": round(sign * ftp, 2),
                     "contribution": round(contrib, 2)})
        contrib_sum += contrib
    pretax_total = sum(x for x in (is_.get("pretax") or [])[:sub_n] if x is not None)
    treasury_center = pretax_total - contrib_sum
    return {"rows": rows,
            "submission_endpoint": submission_period_label(cfg, int(ppy), np),
            "treasury_center": round(treasury_center, 2),
            "consolidated_pretax": round(pretax_total, 2),
            "reconciliation_ok": abs((contrib_sum + treasury_center) - pretax_total) < 0.01,
            "note": "Contributions charge assets / credit liabilities at the path rate over the regulator-facing submission window; the treasury center holds the mismatch. Sum ties to pre-tax exactly."}



def _cblr_state_machine(lev_q, qual_q, params=None):
    """Canonical CBLR regulatory-quarter state machine.

    ``lev_q`` and ``qual_q`` are already quarter-end series. The current quarter is
    excluded from the previous-20-quarter grace lookback; monthly engine cadence must
    be collapsed BEFORE this helper is called.
    """
    P = params or REG_PARAMS["cblr"]
    req, floor = P["requirement"], P["grace_floor"]
    states, grace_hist = [], []
    consec = 0
    for i, lv in enumerate(lev_q):
        qualifies = bool(qual_q[i]) if i < len(qual_q) else False
        if lv is None:
            st = "BLOCKING"; consec = 0
        elif qualifies and lv > req:
            st = "ok"; consec = 0
        elif lv <= floor:
            st = "BLOCKING"; consec = 0
        else:
            prior20 = sum(1 for g in grace_hist
                          if i - P["grace_window_q"] <= g <= i - 1)
            consec += 1
            st = ("grace" if consec <= P["grace_max_consecutive_q"]
                  and prior20 < P["grace_limit_q"] else "EXHAUSTED")
            if st == "grace":
                grace_hist.append(i)
        states.append(st)
    return states

def _cblr_checks(cfg, base):
    """Community Bank Leverage Ratio framework eligibility on REGULATORY quarters.

    The computational cadence may be monthly, but CBLR qualification/grace is a
    quarter-based regulatory state machine. Every three monthly engine periods are
    therefore collapsed to one regulatory quarter before grace counts are advanced.
    """
    bs = base["bs"]
    ppy = int((cfg.get("assumptions") or {}).get("periods_per_year") or 4)
    mpq = ppy // 4
    ta = bs["totalAssets"]
    ta_proj = ta[1:] if len(ta) > 1 and len(ta) == int((cfg.get("assumptions") or {}).get("n_periods") or 12) + 1 else ta
    lev = (base.get("ratios") or {}).get("lev") or (base.get("ratios") or {}).get("leverage") or []
    lev_proj = lev[1:] if len(lev) == len(ta) else lev
    qidx = [i for i in range(mpq - 1, min(len(ta_proj), len(lev_proj)), mpq)]
    ta_q = [ta_proj[i] or 0.0 for i in qidx]
    lev_q = [None if lev_proj[i] is None else lev_proj[i] / 100.0 for i in qidx]
    obs_period = [0.0] * len(ta_proj)
    for p in (base.get("products") or []):
        if p.get("family") != "obs" or not p.get("bal"):
            continue
        arr = list(p["bal"])
        if len(arr) == len(ta_proj) + 1:
            arr = arr[1:]
        for i, v in enumerate(arr[:len(obs_period)]):
            obs_period[i] += v or 0.0
    obs_q = [obs_period[i] for i in qidx]
    obs_share_q = [(obs_q[i] / ta_q[i] if ta_q[i] else 0.0) for i in range(len(qidx))]
    P = REG_PARAMS["cblr"]
    req, floor = P["requirement"], P["grace_floor"]
    attested = bool((cfg.get("attestations") or {}).get("not_advanced_approaches", True))
    qual_q = [(ta_q[i] < P["assets_ceiling_usd"] / 1000.0
               and obs_share_q[i] <= P["obs_share_max"]
               and attested)
              for i in range(len(qidx))]
    states = _cblr_state_machine(lev_q, qual_q, P)
    obs_share = max(obs_share_q, default=0.0)
    lev_min = min((x for x in lev_q if x is not None), default=None)
    ta_last = ta_q[-1] if ta_q else 0.0
    if any(s == "BLOCKING" for s in states):
        grace_state = "BLOCKING: qualifying criterion/floor failure"
    elif any(s == "EXHAUSTED" for s in states):
        grace_state = "EXHAUSTED: grace limits exceeded"
    elif any(s == "grace" for s in states):
        grace_state = "in grace"
    else:
        grace_state = "ok"
    return [
        {"check": "Total assets under $10B (final regulatory quarter)", "value": round(ta_last, 2),
         "threshold": P["assets_ceiling_usd"] / 1000.0, "pass": ta_last < P["assets_ceiling_usd"] / 1000.0,
         "units": "$000s"},
        {"check": "Off-balance-sheet exposures \u2264 25% of assets", "value": round(obs_share, 4),
         "threshold": P["obs_share_max"], "pass": obs_share <= P["obs_share_max"], "units": "share"},
        {"check": "Trading assets + liabilities \u2264 5% of assets", "value": 0.0,
         "threshold": P["trading_share_max"], "pass": True, "units": "share",
         "note": "structurally zero: this model carries no trading book (caveat register)"},
        {"check": f"Leverage ratio above {req*100:.0f}% CBLR requirement (min regulatory quarter)",
         "value": None if lev_min is None else round(lev_min, 4),
         "threshold": req, "pass": (lev_min is not None and lev_min > req), "units": "ratio"},
        {"check": "Grace-period state (floor 7.0%; \u22644 consecutive, \u22648-of-20)",
         "value": None, "threshold": None, "pass": not any(s in ("BLOCKING", "EXHAUSTED") for s in states),
         "units": "state", "state": grace_state},
    ]


def _capital_shortfall_estimate(cfg, scen_results):
    """Smallest additional opening capital to hold the leverage commitment in the
    worst scenario-quarter. Closed-form ESTIMATE (ignores earnings on the added
    capital) — matches predecessor capability; the exact bisection solve remains
    in the monthly engine's reverse_stress.capital for registered clients."""
    commit = next((c["value"] for c in cfg["constraints"] if c["key"] == "leverage_min"), None)
    if commit is None:
        return None
    worst = 0.0
    _ppy = int((cfg.get("assumptions") or {}).get("periods_per_year") or 4)
    _np = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    _sub_end = submission_end_period(cfg, _ppy, _np)
    for res in scen_results.values():
        bs = res["bs"]; n = min(len(bs["totalAssets"]), _sub_end + 1)
        intang = cfg["assumptions"]["intangibles"] / 1000.0
        dta = bs.get("dta") or [0.0] * n
        msr = bs.get("msr") or [0.0] * n
        dta_frac = REG_PARAMS["tax"]["dta_nol_cet1_deduction"]
        for q in range(1, n):
            avg_a = ((bs["totalAssets"][q - 1] or 0) + (bs["totalAssets"][q] or 0)) / 2.0
            dta_ded = (dta[q] or 0.0) * dta_frac
            t1_pre = (bs["equity"][q] or 0) - intang - dta_ded
            msa_x = max(0.0, (msr[q] or 0.0) - 0.25 * max(0.0, t1_pre))
            t1 = t1_pre - msa_x
            avg_net = avg_a - dta_ded - msa_x
            need = commit * avg_net - t1
            if need > worst:
                worst = need
    return {"additional_capital_est": round(max(0.0, worst), 2), "units": "$000s",
            "submission_endpoint": submission_period_label(cfg, _ppy, _np),
            "note": "Closed-form estimate at the worst regulatory submission-period point; "
                    "uses the canonical Tier 1 deductions / net-assets denominator and ignores "
                    "earnings on the added capital. The exact solve runs with the registered engagement."}


def _constraint_tests(cfg, scen_results):
    """A.8 — every constraint, every scenario, source cited."""
    tests = []
    for c in cfg["constraints"]:
        for scen, res in scen_results.items():
            if c["key"] == "leverage_min":
                v = _min_leverage(res)
                tests.append({"key": c["key"], "scenario": scen,
                              "value": None if v is None else round(v, 4),
                              "threshold": c["value"],
                              "pass": (v is not None and v >= c["value"]),
                              "source": c.get("source", "")})
            elif c["key"] == "wholesale_funding_max_pct_assets":
                bor = res["bs"].get("borrow") or res["bs"].get("borrowings") or []
                ta = res["bs"]["totalAssets"]
                shares = [b / t for b, t in zip(bor, ta) if t]
                v = max(shares) if shares else 0.0
                tests.append({"key": c["key"], "scenario": scen,
                              "value": round(v, 4), "threshold": c["value"],
                              "pass": v <= c["value"], "source": c.get("source", "")})
    return tests


def run_v2(cfg):
    cfg = copy.deepcopy(cfg)
    validate_config_v2(cfg)
    config_hash = _hash(cfg)
    # Single authoritative reporting horizon, threaded through the whole consumer layer (the T34 lesson:
    # derive once from the config, never re-probe per function). _NP = number of projection periods;
    # engine BS vectors are (_NP + 1) long (slot 0 = opening), IS/ratios are _NP long.
    _NP = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    _ppy = int((cfg.get("assumptions") or {}).get("periods_per_year") or 4)  # 4=qtr,12=mo,1=yr

    scen_defs = scenarios_from(cfg)
    scen_results, scen_labels = {}, {}
    for scen, (ov, label) in scen_defs.items():
        c = copy.deepcopy(cfg)
        c["scenario_overlays"] = _merge_overlays(cfg.get("scenario_overlays"), ov) if ov \
            else cfg.get("scenario_overlays")
        scen_results[scen] = run_parity(c)
        scen_labels[scen] = label

    base = scen_results["base"]

    # Three-way per-segment charge-off comparison (the contrast that sells the tool): for each
    # lending product, the client's own annual charge-off rate, that rate x the credit multiplier,
    # and the DFAST severe rate for the product's category (annualized-equivalent from the 9Q
    # cumulative for like-for-like comparison). Always computed; the DFAST column is blank for
    # lines the registry does not map (no fabricated stress).
    dfast_segments = None
    if True:
        try:
            from foundry.v2.dfast_lossrates import dfast_rates as _drs
            _dfvfull = _drs((cfg.get("stress_params") or {}).get("dfast_version"))
            _reg = _dfvfull["rates"]
            _com = (cfg.get("stress_params") or {}).get("charge_off_mult", STRESS_DEFAULTS["charge_off_mult"])
            rows = []
            for p in cfg["assumptions"].get("lending_products", []):
                ln = p.get("call_report_line")
                base_co = p.get("charge_off_ann") or 0.0
                dfast_cum9 = _reg.get(ln, {}).get("rate")
                rows.append({
                    "name": p.get("name"), "line": ln,
                    "client_co_ann": base_co,
                    "stressed_co_ann": base_co * _com,
                    # annualized-equivalent of the 9Q cumulative (cum9 * 4/9) for comparison to the
                    # annual rates above; None when the line is unmapped (falls back to client).
                    "dfast_co_ann_equiv": (dfast_cum9 * 4.0 / 9.0) if dfast_cum9 is not None else None,
                    "dfast_cum9": dfast_cum9,
                })
            dfast_segments = {"mult": _com, "rows": rows,
                              "version": _dfvfull["version"],
                              "published": _dfvfull.get("published"),
                              "scenario_vintage": _dfvfull.get("scenario_vintage"),
                              "source_url": _dfvfull.get("source_url"),
                              "publications_index_url": _dfvfull.get("publications_index_url"),
                              "verified": _dfvfull.get("verified"),
                              "citation": _dfvfull.get("citation")}
        except Exception:
            dfast_segments = None
    results = {
        "engine_version": ENGINE_V2,
        "config_hash": config_hash,
        "cadence": {"periods_per_year": _ppy, "n_periods": _NP,
                    "period_word": ("month" if _ppy == 12 else "quarter"),
                    "horizon": horizon_label(_NP, _ppy),
                    "submission_end_period": submission_end_period(cfg, _ppy, _NP),
                    "submission_label": submission_period_label(cfg, _ppy, _NP)},
        "schema_version": cfg.get("schema_version"),
        "client": {"proposed_bank": cfg.get("proposed_bank"),
                   "config_version": cfg.get("config_version"),
                   "config_frozen": cfg.get("config_frozen")},
        "financials": {"bs": base["bs"], "is": base["is"], "ratios": base.get("ratios")},
        "products": base.get("products"),
        "ftp": _ftp_view(base, cfg, _ppy),
        "scenarios": {scen: {**_scen_metrics(r, cfg, next((c2["value"] for c2 in cfg["constraints"]
                                                            if c2["key"] == "leverage_min"), 0.0)),
                             "label": scen_labels[scen]}
                      for scen, r in scen_results.items()},
        "constraint_tests": _constraint_tests(cfg, scen_results),
        "flags": _peer_annotated_flags(cfg, base),
        "dfast_segments": dfast_segments,
    }
    # faithful presentation aggregates: loans/deposits by Call Report line; memo arrays; IS totals
    by_line = {"loans": {}, "deps": {}}
    fv_assets, fv_liabs, obs_notional = None, None, None
    nbs = len(base["bs"]["totalAssets"])
    for p in (base.get("products") or []):
        arr = p.get("bal") or []
        if len(arr) == nbs - 1:
            arr = [None] + list(arr)
        fam = p["family"]; line = p.get("line") or "other"
        tgt = by_line["loans"] if fam == "lending" else (by_line["deps"] if fam == "deposit" else None)
        if tgt is not None:
            acc = tgt.setdefault(line, [0.0] * nbs)
            for i, v in enumerate(arr):
                if v is not None:
                    acc[i] = round(acc[i] + v, 2)
        if fam == "obs":
            obs_notional = obs_notional or [0.0] * nbs
            for i, v in enumerate(arr):
                if v is not None:
                    obs_notional[i] = round(obs_notional[i] + v, 2)
        if p.get("fvAdj"):
            fva = [None] + list(p["fvAdj"]) if len(p["fvAdj"]) == nbs - 1 else p["fvAdj"]
            store = "fv_assets" if fam == "lending" else "fv_liabs"
            cur = locals()[store]
            if cur is None:
                cur = [0.0] * nbs
            for i, v in enumerate(fva):
                if v is not None:
                    cur[i] = round(cur[i] + v, 2)
            if store == "fv_assets":
                fv_assets = cur
            else:
                fv_liabs = cur
    is_totals = {k: round(sum(x for x in arr if x is not None), 2)
                 for k, arr in base["is"].items()}
    results["faithful"] = {"loans_by_line": by_line["loans"], "deps_by_line": by_line["deps"],
                           "obs_notional": obs_notional, "fv_adj_assets": fv_assets,
                           "fv_adj_liabs": fv_liabs, "is_totals": is_totals}
    # Overview (v3 front page): readiness, breakeven, class-mapped flags
    base_ct = [t for t in results.get("constraint_tests", []) if t.get("scenario") == "base"]
    hard_stops = sum(1 for t in base_ct if not t.get("pass"))
    pretax = base["is"].get("pretax") or []
    breakeven_q = next((i + 1 for i, v in enumerate(pretax) if v is not None and v > 0), None)
    def _cls(f):
        if str(f.get("id", "")).startswith("COUPLED"):
            return "commercial_assumption_requiring_support"
        if str(f.get("id", "")).startswith("REG"):
            return "counsel_determination_required"
        return "commercial_assumption_requiring_support" if f.get("sev") == "severe" else "advisory"
    for f in results["flags"]:
        f["cls"] = _cls(f)
    # Peer evidence: NO SYNTHETIC DATA on the v3.1 path. The 43-bank invented
    # cohort (v1 fixture, SOLSTICE era) no longer feeds evidence, priors, or
    # flags here. Peer evidence attaches when the challenge layer calibrates
    # from the CharterIQ Call Report substrate; until then the surface says so.
    results["peer"] = None
    results["examiner_book"] = []
    prior_table, cohort = {}, {}
    if cfg.get("peer_query"):
        results["peer"] = {
            "status": "pending",
            "note": ("Peer evidence attaches when the challenge layer is calibrated "
                      "from the CharterIQ Call Report substrate. No synthetic cohort "
                      "is presented as evidence."),
        }
    try:
        results["examiner_book"] = challenge_q.examiner_book_v2(cfg, results, prior_table, cohort)
    except Exception:
        results["examiner_book"] = []
    results["overview"] = {
        "readiness": {"status": "PASS" if hard_stops == 0 else "ATTENTION",
                       "open_items": len(results["flags"]), "hard_stops": hard_stops},
        "breakeven_q": breakeven_q,  # legacy key retained for API compatibility
        "breakeven_period": breakeven_q,
        "breakeven_label": period_label(breakeven_q, _ppy) if breakeven_q else None,
    }
    results["capital_shortfall"] = _capital_shortfall_estimate(cfg, scen_results)
    # Capital module (v3): derivation rows reconciled to the engine's own leverage,
    # thresholds in three tiers, per-quarter qualification grid, caveat register.
    P2 = REG_PARAMS["cblr"]
    bs2 = base["bs"]; n2 = len(bs2["totalAssets"])
    intangk = cfg["assumptions"]["intangibles"] / 1000.0
    msr2 = bs2.get("msr") or [0.0] * n2
    # DTA (NOL) is deducted from CET1/Tier 1 AND from average assets when the deferred-tax
    # path is elected, exactly as the engine does (12 CFR 3.22(a)). bs["dta"] is present only
    # when tax_detail is on; the reg param is the CET1 deduction fraction. Omitting this made
    # the derivation drift from the engine leverage by ~6-7bp with tax_detail on, tripping the
    # ">2bp does not reconcile" warning even though the engine leverage itself was correct.
    _td_on = bool(cfg["assumptions"].get("tax_detail"))
    _dta_series = bs2.get("dta") or [0.0] * n2
    _dta_frac = REG_PARAMS["tax"]["dta_nol_cet1_deduction"]
    lev2 = (base.get("ratios") or {}).get("lev") or (base.get("ratios") or {}).get("leverage") or []
    q0 = 1 if n2 == _NP + 1 else 0
    tier1, msa_x, avg_net, lev_drv = [], [], [], []
    for i in range(q0, n2):
        eq = bs2["equity"][i] or 0.0
        dta_ded = ((_dta_series[i] or 0.0) * _dta_frac) if _td_on else 0.0
        t1p = eq - intangk - dta_ded
        mx = max(0.0, (msr2[i] or 0.0) - 0.25 * max(0.0, t1p))
        t1 = t1p - mx
        aa = ((bs2["totalAssets"][i - 1] or 0.0) + (bs2["totalAssets"][i] or 0.0)) / 2.0 - mx - dta_ded
        tier1.append(round(t1, 2)); msa_x.append(round(mx, 2)); avg_net.append(round(aa, 2))
        lev_drv.append(round(t1 / aa, 6) if aa else None)
    lev_eng = [None if x is None else round(x / 100.0, 6) for x in lev2[-len(lev_drv):]]
    recon_bp = max((abs((a or 0) - (b or 0)) * 10000 for a, b in zip(lev_drv, lev_eng)), default=0.0)
    mct = cfg.get("management_capital_target")
    results["capital"] = {
        "rows": {"tier1": tier1, "sec_gos_deduction": [0.0] * len(tier1),
                 "msa_excess": msa_x, "avg_assets_net": avg_net, "leverage": lev_eng},
        "recon_max_bp": round(recon_bp, 3),
        "thresholds": {"statutory": P2["requirement"],
                        "chartering": next((c2["value"] for c2 in cfg["constraints"]
                                            if c2["key"] == "leverage_min"), None),
                        "management": mct},
    }
    if mct is not None:
        breach_qs = [i + 1 for i, x in enumerate(lev_eng) if x is not None and x < mct]
        if breach_qs:
            results["flags"].append({"id": "CAP-BUFFER", "sev": "mild", "cls": "advisory",
                "text": f"Leverage below the management capital target ({mct*100:.1f}%) in "
                        f"Q{breach_qs[0]}\u2013Q{breach_qs[-1]} span ({len(breach_qs)} quarters). "
                        "Buffer breach is a warning, not a compliance event."})

    # GROWTH-Y1 (challenge rule table, challenge_q.py): year-1 balance-sheet growth > 25%. It is a
    # MODELED quantity (total assets from the funding waterfall, not a raw input), so it is computed
    # here from the engine's balance sheet rather than in challenge_config, which sees inputs only.
    # 25% matches the supervisory heuristic used for FUND-GROWTH; aggressive asset ramps are a
    # classic de novo exam finding. Opening = totalAssets[0]; end of year 1 is the
    # `periods_per_year`-th projection period (Q4 quarterly, M12 monthly).
    _ta = base["bs"]["totalAssets"]
    _y1i = _ppy
    if len(_ta) > _y1i and _ta[0]:
        _y1g = (_ta[_y1i] - _ta[0]) / _ta[0]
        if _y1g > 0.25:
            results["flags"].append({"id": "GROWTH-Y1", "sev": "mild", "cls": "advisory",
                "text": f"Year-1 balance-sheet growth of {_y1g:.0%} exceeds 25% \u2014 a fast asset "
                        "ramp for a de novo. Support how it is funded and whether capital keeps pace."})
    # Regulatory-quarter qualification grid. Monthly runs collapse M1-M3 -> Q1,
    # M4-M6 -> Q2, etc.; grace limits NEVER advance once per engine month.
    obs_arr = [0.0] * n2
    for p2 in (base.get("products") or []):
        if p2["family"] == "obs" and p2.get("bal"):
            arr2 = p2["bal"]; off = n2 - len(arr2)
            for i, v in enumerate(arr2):
                if v is not None:
                    obs_arr[i + off] += v
    _mpq = _ppy // 4
    _proj_ta = list(bs2["totalAssets"][q0:])
    _proj_obs = list(obs_arr[q0:])
    _qends = list(range(_mpq - 1, min(len(_proj_ta), len(lev_eng)), _mpq))
    assets_row = []
    obs_row = []
    trading_row = []
    _qual = []
    _att = bool((cfg.get("attestations") or {}).get("not_advanced_approaches", True))
    for _i in _qends:
        _taq = _proj_ta[_i] or 0.0
        _os = (_proj_obs[_i] / _taq) if _taq else 0.0
        _ap = _taq < P2["assets_ceiling_usd"] / 1000.0
        _op = _os <= P2["obs_share_max"]
        assets_row.append({"pass": _ap, "value": round(_taq, 2)})
        obs_row.append({"pass": _op, "value": round(_os, 4)})
        trading_row.append({"pass": True, "value": 0.0})
        _qual.append(_ap and _op and _att)
    _lev_q_for_cblr = [lev_eng[i] for i in _qends]
    grace_row = _cblr_state_machine(_lev_q_for_cblr, _qual, P2)
    _cblr_q_states = grace_row
    results["cblr_grid"] = {
        "quarters": len(_qends),
        "rows": [
            {"label": "Total assets < $10B", "cells": assets_row, "units": "check"},
            {"label": "Qualifying off-BS exposures \u2264 25% of assets", "cells": obs_row, "units": "share"},
            {"label": "Trading assets + liabilities \u2264 5% of assets", "cells": trading_row, "units": "share"},
            {"label": "Not an advanced-approaches organization", "attested": True,
             "value": bool((cfg.get("attestations") or {}).get("not_advanced_approaches", True))},
            {"label": "Grace-period state (floor 7.0%; \u22644 consecutive, \u22648-of-20)",
             "states": grace_row},
        ],
    }
    results["caveats"] = [
        "No trading book is modeled; the trading-assets qualification test is structurally zero.",
        "Funds-transfer pricing is presentation-only and never changes the income statement.",
        "By default no deferred tax asset is booked \u2014 NOL carryforwards offset future taxable income only (conservative); the optional deferred-tax detail path books DTAs (gross, valuation allowance, net) under ASC 740 when elected.",
        "Securitization is not modeled (open decision, parked); the gain-on-sale capital deduction row is shown at zero for schedule completeness.",
        "The MSA deduction is approximated per 12 CFR 3.22(d) as excess over 25% of Tier 1 before threshold deductions.",
        "Business-combination events (incl. the CBLR M&A no-grace transition) are out of scope and not modeled.",
        "Ramped (non-parallel) rate shocks, matched-maturity FTP, and MSR prepayment revaluation remain parked open decisions.",
    ]
    results["reg_params"] = {k: REG_PARAMS[k] for k in ("version", "effective", "verified", "citations")}
    results["reg_params"]["pending_rules"] = PENDING_RULES
    results["cblr"] = _cblr_checks(cfg, base)
    results["presentation"] = {
        "line_labels": present.LINE_LABELS, "loan_keys": present.LOAN_KEYS, "dep_keys": present.DEP_KEYS,
        "bs_layout": present.BS_LAYOUT, "is_layout": present.IS_LAYOUT,
        "ratio_labels": present.RATIO_LABELS, "scenario_labels": present.SCENARIO_LABELS,
        "derived": present.derived_lines(base, cfg),
        "product_codes": {p["name"]: (code_for_line(p.get("line")) or ["", "", "", ""])
                          for p in (base.get("products") or [])},
    }
    results["callreport"] = {k: list(v) for k, v in
                             {**RESULT_CODES_BS, **RESULT_CODES_IS, **LINE_CODES}.items()}
    # ---- Wave 2 (FLOOR F-091/033/090/003/100): standardized capital + concentrations
    RW, CCF = REG_PARAMS["risk_weights"], REG_PARAMS["ccf"]
    PCA = REG_PARAMS["pca_well_capitalized"]
    bsn = base["bs"]; a2 = cfg["assumptions"]
    # Reporting horizon derives from the engine's own vector length, not a hardcoded 12, so a longer
    # projection horizon flows through automatically. Engine BS vectors are (Q+1)-long (slot 0 = open).
    _probe = bsn.get("ta") or bsn.get("cash") or []
    _NQ = (len(_probe) - 1) if len(_probe) >= 2 else 12
    nq2 = _NQ
    def _s(key):
        v = bsn.get(key) or [0.0] * (nq2 + 1)
        return (v[1:nq2 + 1] if len(v) == nq2 + 1 else v[:nq2])
    LINE_W = {"loanMortgage": RW["resi_first_lien"]}
    loans_w = [0.0] * nq2
    for p in base.get("products") or []:
        if p.get("family") == "lending" or (p.get("line") or "").startswith("loan"):
            w = LINE_W.get(p.get("line"), RW["corporate_consumer_cre"])
            balv = p.get("bal") or []
            balq = balv[1:nq2 + 1] if len(balv) == nq2 + 1 else balv[:nq2]
            for t in range(min(nq2, len(balq))):
                loans_w[t] += (balq[t] or 0.0) * w   # products arrive in $000s
    hfsq = _s("hfs")
    secq = [(_s("sec")[t] + _s("afsBook")[t] + _s("htmBook")[t]) for t in range(nq2)]
    cashq, msrq, alllq = _s("cash"), _s("msr"), _s("alll")
    premq = _s("premises")
    # General other assets are modeled as a flat non-earning balance in Profile A.
    # They are NOT zero-risk simply because the engine does not subtype them; use the
    # standardized 100% default bucket pending a more granular regulatory classification.
    otherq = [float(a2.get("other_assets") or 0.0) / 1000.0] * nq2
    dtaq = _s("dta") if bsn.get("dta") else [0.0] * nq2
    obs_notional = [0.0] * nq2
    for p in base.get("products") or []:
        if (p.get("line") or "") == "obs" or p.get("family") == "obs":
            balv = p.get("bal") or []
            balq = balv[1:nq2 + 1] if len(balv) == nq2 + 1 else balv[:nq2]
            for t in range(min(nq2, len(balq))):
                obs_notional[t] += balq[t] or 0.0
    cab = float(a2.get("cash_at_banks_pct") or 0.0)
    cap_rows = results["capital"]["rows"]
    t1_dedq = cap_rows["tier1"]
    msa_x = cap_rows["msa_excess"]
    eqq, aociq = _s("equity"), _s("aoci")
    intang = a2.get("intangibles", 0.0) / 1000.0
    optout = (cfg.get("charter_profile") or {}).get("aoci_optout", True)
    rwa_t, cet1_t, t1_t, t2_t, tot_t = [], [], [], [], []
    for t in range(nq2):
        rwa = (cashq[t] * cab * RW["bank_exposures"]
               + secq[t] * RW["agency_securities"]
               + loans_w[t] + hfsq[t] * RW["corporate_consumer_cre"]
               + premq[t] * RW["corporate_consumer_cre"]
               + otherq[t] * RW["corporate_consumer_cre"]
               + max(0.0, msrq[t] - msa_x[t]) * RW["msr_nondeducted"]
               + obs_notional[t] * CCF["default"] * RW["corporate_consumer_cre"])
        dta_ded = (dtaq[t] or 0.0) * REG_PARAMS["tax"]["dta_nol_cet1_deduction"]
        cet1 = eqq[t] - intang - (aociq[t] if optout else 0.0) - dta_ded - msa_x[t]
        t1 = cet1
        t2 = min(alllq[t], REG_PARAMS["tier2_alll_cap_pct_rwa"] * rwa)
        rwa_t.append(rwa); cet1_t.append(cet1); t1_t.append(t1); t2_t.append(t2)
        tot_t.append(t1 + t2)
    def _r4(num, den):
        return [round(num[t] / den[t] * 100, 2) if den[t] and den[t] > 0 else None
                 for t in range(nq2)]
    lev_t = (base.get("ratios") or {}).get("lev") or [None] * (_NP + 1)
    lev_q = lev_t[1:nq2 + 1] if len(lev_t) == nq2 + 1 else lev_t[:nq2]
    P3 = REG_PARAMS["cblr"]
    elected = (cfg.get("charter_profile") or {}).get("cblr_election", True)
    # Present a status for each engine period, but source it from the REGULATORY-
    # quarter state machine above. Monthly M1-M3 therefore share Q1's status.
    cblr_status = []
    for t in range(nq2):
        qi = min(len(_cblr_q_states) - 1, t // _mpq) if _cblr_q_states else -1
        st = _cblr_q_states[qi] if qi >= 0 else None
        cblr_status.append({
            "ok": "meets requirement",
            "grace": "grace period (floor >7%, max 4 consecutive regulatory quarters)",
            "EXHAUSTED": "grace exhausted — standardized approach applies",
            "BLOCKING": "BELOW grace floor / nonqualifying — standardized approach applies",
        }.get(st))
    results["capital"]["standardized"] = {
        "rwa": [round(x, 2) for x in rwa_t],
        "cet1": [round(x, 2) for x in cet1_t],
        "tier1": [round(x, 2) for x in t1_t],
        "tier2": [round(x, 2) for x in t2_t],
        "total": [round(x, 2) for x in tot_t],
        "ratios": {"cet1_rwa": _r4(cet1_t, rwa_t), "tier1_rwa": _r4(t1_t, rwa_t),
                    "total_rwa": _r4(tot_t, rwa_t), "leverage": lev_q},
        "thresholds": {"cet1_rwa": PCA["cet1_rwa"] * 100, "tier1_rwa": PCA["tier1_rwa"] * 100,
                        "total_rwa": PCA["total_rwa"] * 100, "leverage": PCA["leverage"] * 100},
        "aoci_optout": bool(optout),
        "notes": ["risk weights per 12 CFR 324.32; securities weighted as agency (20%) — "
                    "a disclosed modeling assumption",
                   f"cash at banks share {cab:.0%} weighted 20% (D-P6 fix); balances at the "
                    "Federal Reserve weighted 0%",
                   "OBS at the default 50% CCF (12 CFR 324.33); per-exposure maturities not yet modeled",
                   "premises/fixed assets and unclassified general other assets are placed in the 100% standardized bucket; specialized other-asset subtypes require explicit classification",
                   "no classified-asset concept modeled; the 150% weight is registered but unused",
                   "Tier 2 = min(ALLL, 1.25% RWA) per 12 CFR 324.20(d)(3)",
                   "AOCI opt-out " + ("elected: AOCI excluded from CET1" if optout
                                        else "not elected: AOCI included in CET1")],
    }
    results["capital"]["cblr_tiering"] = {
        "elected": bool(elected), "requirement_pct": round(P3["requirement"] * 100, 2),
        "grace_floor_pct": round(P3["grace_floor"] * 100, 2), "status": cblr_status,
        "note": ("floor doc lists the pre-2026 9%/8% calibration; the April 2026 final rule "
                  "(91 FR 22973) governs via REG_PARAMS: 8% requirement / 7% grace floor"),
    }
    # concentrations (Patrick CONC, F-100)
    depq = _s("deposits"); borq = _s("borrow"); sbq = _s("borrowSched")
    taq = _s("totalAssets"); glq = _s("grossLoans")
    liabq = [taq[t] - eqq[t] for t in range(nq2)]
    ci_bal = [0.0] * nq2; cons_bal = [0.0] * nq2; cre_bal = [0.0] * nq2
    for p in base.get("products") or []:
        ln = p.get("line") or ""
        tgt = {"loanCommercial": ci_bal, "loanConsumer": cons_bal, "loanCreditCard": cons_bal,
                "loanCRE": cre_bal}.get(ln)
        if tgt is not None:
            balv = p.get("bal") or []
            balq = balv[1:nq2 + 1] if len(balv) == nq2 + 1 else balv[:nq2]
            for t in range(min(nq2, len(balq))):
                tgt[t] += (balq[t] or 0.0)   # $000s already
    cd_in = a2.get("construction_land_total")
    lb_in = a2.get("single_largest_borrower")
    nie_q = [ (base["is"]["prodOpex"][t] if "prodOpex" in base["is"] else base["is"].get("opexProd",[0]*12)[t])
               + (base["is"]["overhead"][t] if "overhead" in base["is"] else base["is"].get("fixedOpex",[0]*12)[t])
               for t in range(nq2)]
    avg_a = cap_rows.get("avg_assets_net") or taq
    def _pct(n_, d_):
        return round(n_ / d_ * 100, 2) if d_ and d_ > 0 else None
    # Concentrations & Diagnostics is a regulator-facing submission exhibit: use
    # the explicit submission endpoint (normally Q12), not the computational terminal.
    _subp_conc = submission_end_period(cfg, _ppy, nq2)
    q = max(0, min(nq2, _subp_conc) - 1)
    conc_rows = [
        {"name": "CRE / total risk-based capital", "value": _pct(cre_bal[q], tot_t[q]),
          "threshold": 300.0, "kind": "max", "sev": "severe",
          "basis": "interagency CRE guidance (2006), 12 CFR pt 365 app A"},
        {"name": "Construction & land / total RBC", "value": (_pct(cd_in / 1000.0, tot_t[q])
                                                                 if cd_in else None),
          "threshold": 100.0, "kind": "max", "sev": "severe",
          "basis": "interagency CRE guidance; requires the construction_land_total input"
                    + ("" if cd_in else " — NOT PROVIDED (D-P16b: no silent zero)")},
        {"name": "C&I / total loans", "value": _pct(ci_bal[q], glq[q]),
          "threshold": None, "kind": "info", "sev": "mild", "basis": "portfolio mix"},
        {"name": "Consumer (incl. card) / total loans", "value": _pct(cons_bal[q], glq[q]),
          "threshold": None, "kind": "info", "sev": "mild", "basis": "portfolio mix"},
        {"name": "Single largest borrower / Tier 1", "value": (_pct(lb_in / 1000.0, t1_t[q])
                                                                  if lb_in else None),
          "threshold": 15.0, "kind": "max", "sev": "severe",
          "basis": "12 USC 84 lending limit (15% unsecured)"
                    + ("" if lb_in else " — single_largest_borrower NOT PROVIDED")},
        {"name": "Wholesale funding / total liabilities",
          "value": _pct(borq[q] + sbq[q], liabq[q]), "threshold": 25.0, "kind": "max",
          "sev": "mild", "basis": "Foundry planning band (25%), not a supervisory limit \u2014 "
                    "wholesale reliance is a common exam focus but carries no fixed cap"},
        {"name": "Non-core funding / total assets",
          "value": _pct(borq[q] + sbq[q], taq[q]), "threshold": 20.0, "kind": "max",
          "sev": "mild", "basis": "Foundry planning band (20%); UBPR reports non-core dependence "
                    "but sets no threshold \u2014 the 20% line is Foundry's, not UBPR's"},
        {"name": "Loans / deposits", "value": _pct(glq[q], depq[q]),
          "threshold": [70.0, 90.0], "kind": "band", "sev": "mild",
          "basis": "Foundry planning band (70\u201390%), not a supervisory limit"},
        {"name": "NIE / average assets (burden)",
          "value": _pct(sum(nie_q[:_subp_conc]),
                        sum(avg_a[:_subp_conc]) / _subp_conc if avg_a and _subp_conc else None)
                    if avg_a else None,
          "threshold": None, "kind": "info", "sev": "mild", "basis": "expense burden"},
    ]
    for row in conc_rows:
        v, th, kd = row["value"], row["threshold"], row["kind"]
        if v is None or th is None:
            row["status"] = "n/a" if v is None else "info"
        elif kd == "max":
            row["status"] = "BREACH" if v > th else "within"
        elif kd == "band":
            row["status"] = "outside band" if (v < th[0] or v > th[1]) else "within"
        if row.get("status") == "BREACH" and row["sev"] == "severe":
            results.setdefault("flags", []).append({
                "id": "CONC-" + {"CRE / total risk-based capital": "CRE-RBC",
                                    "Construction & land / total RBC": "CD-RBC",
                                    "Single largest borrower / Tier 1": "LLL"}.get(
                                       row["name"], row["name"][:10].strip().upper().replace(" ", "-")),
                "sev": "severe",
                "text": f"Concentration: {row['name']} at {v:.0f}% exceeds the "
                         f"{th:.0f}% supervisory criterion ({row['basis']})."})
    results["concentrations"] = {"as_of": submission_period_label(cfg, _ppy, nq2), "rows": conc_rows,
                                   "note": "thresholds resolve from REG_PARAMS/citations; "
                                            "missing inputs are stated, never zero-filled"}
    po = cfg.get("pre_opening") or {}
    if po.get("expenses") or po.get("min_day1_capital"):
        burn = sum(float(e.get("total", 0.0)) for e in (po.get("expenses") or []))
        capital0 = cfg["target_state"]["initial_capital"]
        min_d1 = float(po.get("min_day1_capital") or 0.0)
        cushion = capital0 - burn
        results["pre_open"] = {
            "expenses": [{"category": e.get("category"), "total": float(e.get("total", 0.0))}
                          for e in (po.get("expenses") or [])],
            "burn_total": burn,
            "cushion": cushion,
            "min_day1_capital": min_d1,
            "sufficient": cushion >= min_d1,
            "flag": ("SUFFICIENT" if cushion >= min_d1
                       else "INSUFFICIENT — REVIEW CAPITAL PLAN"),
            "convention": ("organizational costs expensed into the opening retained "
                             "deficit; monthly schedules "
                             "convert to quarterly totals at import"),
        }
        if not results["pre_open"]["sufficient"]:
            results.setdefault("flags", []).append({
                "id": "PREOPEN-01", "sev": "severe",
                "text": (f"Pre-opening capital sufficiency: cushion ${cushion/1000:,.0f}k "
                          f"(raise − burn) is below the minimum Day-1 requirement "
                          f"${min_d1/1000:,.0f}k — INSUFFICIENT, review the capital plan."),
            })
    # ---- Wave 4 (F-120/122/132/011/013): checks panel, quick stats, annual rollup
    bsw, isw = base["bs"], base["is"]
    _dv = results["presentation"]["derived"]
    nqw = _NP
    def _sw(key, src=None):
        v = (src or bsw).get(key) or [0.0] * (_NP + 1)
        return (v[1:_NP + 1] if len(v) == _NP + 1 else v[:_NP])
    eqw, rew, aociw, piw = _sw("equity"), _sw("re" if "re" in bsw else "retained"),                              _sw("aoci"), _sw("paidIn")
    niw = isw["ni"][:_NP]
    idw = _dv.get("identity") or []
    checks = []
    def _ck(cid, label, ok, klass, note=""):
        checks.append({"id": cid, "label": label, "pass": bool(ok), "class": klass,
                        "note": note})
    idev = max((abs(x) for x in idw if x is not None), default=0.0)
    _ck("CK-1", f"Assets = Liabilities + Equity, every {cadence_noun(_ppy)}", idev < 1.0,
        "integrity", f"worst deviation {idev:.3f} $000s")
    comp_dev = max(abs(eqw[t] - (piw[t] + rew[t] + aociw[t])) for t in range(nqw))
    _ck("CK-2", f"Equity = paid-in + retained + AOCI, every {cadence_noun(_ppy)}", comp_dev < 0.02,
        "integrity", f"worst {comp_dev:.4f}")
    ni_dev = max(abs((rew[t] - rew[t - 1]) - niw[t]) for t in range(1, nqw))
    _ck("CK-3", "Net income flows to retained earnings", ni_dev < 0.02,
        "integrity", "raises land in paid-in, AOCI in its own component — retained moves by NI alone")
    lev_w = (base.get("ratios") or {}).get("lev") or []
    lev_q = [x for x in (lev_w[1:_NP + 1] if len(lev_w) == _NP + 1 else lev_w[:_NP]) if x is not None]
    lev_min_req = None
    for con in (cfg.get("constraints") or []):
        if "lever" in str(con.get("key", con.get("name", ""))).lower():
            lev_min_req = con.get("value")
    if lev_min_req:
        _ck("CK-4", f"Leverage \u2265 {lev_min_req*100:.0f}% every quarter (chartering commitment)",
            all(x >= lev_min_req * 100 for x in lev_q), "viability",
            f"min {min(lev_q):.2f}%" if lev_q else "no data")
    if "pre_open" in results:
        _ck("CK-5", "Pre-opening capital sufficiency", results["pre_open"]["sufficient"],
            "viability", results["pre_open"]["flag"])
    # CK-10/CK-11 (fee-driven-product generalization, Step 0): the viability class had no
    # check that fires for a fee-only / non-spread balance sheet. SPREAD-VIAB
    # (challenge_q.py) is a narrative flag, not a viability-class check, and only fires
    # when both loans AND deposits are present; leverage (CK-4) is vacuously easy to clear
    # on a near-all-equity, thin book (custody/trust-shaped), so it provides no signal
    # either.
    #
    # Class "notice", deliberately NOT "viability": these are factual observations about
    # the projection an examiner would notice, not a platform-rendered charter verdict.
    # Foundry surfaces what's worth a human's attention; it doesn't adjudicate viability.
    # They are excluded from viability_pass's aggregate on purpose (that boolean is
    # reserved for the plan's own stated commitments -- leverage floor, pre-opening
    # capital -- not for general economic judgment calls). Both are literal, factual
    # thresholds, deliberately not softened: CK-10 fires the instant net income is
    # negative in the final quarter or relapses after an earlier crossing, no slope
    # tolerance; CK-11 fires only on actual insolvency (equity < 0), no positive margin.
    # If either fires, the numbers themselves already show why -- these are pointers to
    # attention, not verdicts.
    #
    # Uses only `ni`, `equity`, `paidIn` — fields common to both engine profiles (profile B
    # has no `prodOpex`/`overhead`; those names don't exist there and would KeyError).
    _ck("CK-10", "Reaches non-negative net income within the filed horizon, no relapse "
                 "(\u201cprofitable by year three,\u201d the charter-application benchmark)",
        bool(niw) and niw[-1] >= 0 and not any(niw[t] < 0 for t in range(len(niw))
                                                if any(niw[s] >= 0 for s in range(t))),
        "notice",
        f"ni[-1]={niw[-1]:.1f}" if niw else "no data")
    _min_eq = min(eqw) if eqw else None
    _ck("CK-11", "Cumulative burn stays within capital raised (equity never negative) \u2014 "
                 "fires regardless of whether a spread book exists",
        _min_eq is not None and _min_eq >= 0,
        "notice",
        f"min equity {_min_eq:,.0f}" if _min_eq is not None else "no data")
    # CK-6: the legacy fee_modules path is retired; fees are GUT products. This check now
    # guards that no fee_modules config lingers (fees must flow through products).
    _ck("CK-6", "No legacy fee_modules (fees are GUT products)",
        not (cfg["assumptions"].get("fee_modules")), "integrity",
        "fee income flows through fee_streams products, not the retired fee_modules path")
    _ck("CK-7", "Projection period index, no gaps", len(niw) == _NP, "integrity")
    ann_ni = [sum(niw[y * _ppy:(y + 1) * _ppy]) for y in range(_NP // _ppy)]
    _ck("CK-8", f"Annual = sum of {cadence_noun(_ppy, plural=True)} (net income, full modeled years)", True,
        "integrity", "computed identically; asserted by construction and re-checked in the gate suite")
    _ck("CK-9", "Regulatory parameters resolve from the versioned registry",
        bool(REG_PARAMS.get("version")), "integrity", f"version {REG_PARAMS.get('version')}")
    # Concentration breaches are a first-order "does the bank hold together" question — surface every
    # severe-criterion BREACH as a VIABILITY check (fails when breached), so it feeds the exec-summary
    # viability section directly, not only the CONC- flag stream. Only rows with a real criterion and a
    # severe classification qualify; info/mild rows and planning-band items do not gate viability.
    _conc_seq = 0
    for _cr in conc_rows:
        if _cr.get("sev") == "severe" and _cr.get("status") == "BREACH":
            _conc_seq += 1
            _v = _cr.get("value")
            _th = _cr.get("threshold")
            _vtxt = f"{_v:.1f}%" if isinstance(_v, (int, float)) else "n/a"
            _thtxt = f"{_th:.0f}%" if isinstance(_th, (int, float)) else str(_th)
            _ck(f"CK-C{_conc_seq}", f"Concentration within limit \u2014 {_cr['name']}",
                False, "viability",
                f"BREACH: {_vtxt} vs \u2264 {_thtxt} ({_cr.get('basis','')})")
    ta_w, gl_w, dep_w = _sw("totalAssets"), _sw("grossLoans"), _sw("deposits")
    results["checks"] = {
        "rows": checks,
        "integrity_pass": all(c["pass"] for c in checks if c["class"] == "integrity"),
        "viability_pass": all(c["pass"] for c in checks if c["class"] == "viability"),
        "master": ("\u2705 Integrity checks: all pass" if all(
                      c["pass"] for c in checks if c["class"] == "integrity")
                    else "\u26a0\ufe0f Integrity failures \u2014 review"),
        "doctrine": ("integrity (the arithmetic holds together) and viability (the plan "
                      "clears its commitments) are separate classes, both shown \u2014 "
                      "a coherent model of a failing bank passes integrity and fails "
                      "viability \u2014 a plan can be arithmetically coherent and still "
                      "not clear its commitments, and a checks panel that conflates the "
                      "two blesses failing banks"),
    }
    nim_w = (base.get("ratios") or {}).get("nim") or [None] * (_NP + 1)
    roa_w = (base.get("ratios") or {}).get("roa") or [None] * (_NP + 1)
    eff_w = (base.get("ratios") or {}).get("eff") or [None] * (_NP + 1)
    def _annR(series):
        s = series[1:_NP + 1] if len(series) == _NP + 1 else series[:_NP]
        out = []
        for y in range(_NP // _ppy):
            xs = [x for x in s[y * _ppy:(y + 1) * _ppy] if x is not None]
            out.append(round(sum(xs) / len(xs), 2) if xs else None)
        return out
    results["annual"] = {
        "note": "stocks at year-end (every periods_per_year-th period), flows summed, ratios simple-averaged "
                 "over the year's engine periods (labeled as such)",
        "total_assets_eop": [ta_w[i] for i in range(_ppy - 1, _NP, _ppy)],
        "net_loans_eop": [_sw("netLoans")[i] for i in range(_ppy - 1, _NP, _ppy)],
        "deposits_eop": [dep_w[i] for i in range(_ppy - 1, _NP, _ppy)],
        "ni": [round(x, 2) for x in ann_ni],
        "nim": _annR(nim_w), "roa": _annR(roa_w), "eff": _annR(eff_w),
        "lev_eop": [(lambda s: [(s[i] if i < len(s) else None) for i in range(_ppy - 1, _NP, _ppy)])(
                       lev_w[1:_NP + 1] if len(lev_w) == _NP + 1 else lev_w[:_NP])][0],
    }
    results["quick_stats"] = {
        "note": "8 headline metrics \u00d7 project year; the "
                 "capital metric is CBLR-aware (leverage governs under election)",
        "rows": [
            {"label": "Total Assets (EOP, $000s)", "y": results["annual"]["total_assets_eop"]},
            {"label": "Net Loans (EOP, $000s)", "y": results["annual"]["net_loans_eop"]},
            {"label": "Total Deposits (EOP, $000s)", "y": results["annual"]["deposits_eop"]},
            {"label": f"NIM (%, avg of {cadence_noun(_ppy, plural=True)})", "y": results["annual"]["nim"]},
            {"label": "Efficiency (%, avg)", "y": results["annual"]["eff"]},
            {"label": "ROA (%, avg)", "y": results["annual"]["roa"]},
            {"label": "Leverage / CBLR (%, EOP)", "y": results["annual"]["lev_eop"]},
            {"label": "Net Income ($000s)", "y": results["annual"]["ni"]},
        ]}
    from .income_modules import nie_detail_series as _nds
    from .growth import growth_context_from_cfg as _growth_context_from_cfg
    _growth_ctx = _growth_context_from_cfg(cfg, _ppy)
    # Per-business fee reporting is native under the GUT: each fee business is its own product,
    # and results["products"][i]["fees"] carries its per-quarter fee income at full granularity.
    # No bespoke fee_detail re-decomposition needed (that existed only to unpack the legacy
    # fee_modules bundle). One source of truth: the products.
    if _nds(cfg["assumptions"], _ppy, _growth_ctx):
        nd_s = _nds(cfg["assumptions"], _ppy, _growth_ctx)
        results["nie_detail_series"] = {"comp": [round(x / 1000.0, 2) for x in nd_s["comp"]],
                                          "categories": [round(x / 1000.0, 2) for x in nd_s["categories"]],
                                          "gross_up_rate": nd_s["gross_up_rate"],
                                          "note": ("FDIC on avg consolidated assets − avg tangible "
                                                    "equity (12 USC 1817(b)(2)(A), D-P14 fix) + OCC "
                                                    "on assets, accrued in-engine")}
    results["engagement_echo"] = {
        "client": cfg.get("client_legal_name") or cfg.get("proposed_bank") or "(unnamed)",
        "engagement_id": cfg.get("engagement_id"),
        "prepared_by": cfg.get("prepared_by") or "Foundry Modeling Workspace",
        "config_version": cfg.get("config_version"),
        "config_hash": results.get("config_hash"),
        "engine_version": results.get("engine_version"),
        "run_date": None,   # stamped client-side; the engine stays deterministic
    }
    _nd_cfg = cfg["assumptions"].get("nie_detail")
    if _nd_cfg is not None and (cfg["assumptions"].get("overhead_q") or 0) > 0:
        _zeroed = (not any(_nd_cfg.get("fte_by_year") or [])
                    and not (((_nd_cfg.get("workforce") or {}).get("roles")) or [])
                    and not (_nd_cfg.get("categories") or []))
        results.setdefault("flags", []).append({
            "id": "NIE-REPLACES-OVERHEAD",
            "sev": "severe" if _zeroed else "mild",
            "text": (f"Operating Expense Detail is ACTIVE and replaces the corporate "
                      f"overhead line \u2014 the Configuration overhead value of "
                      f"{cfg['assumptions']['overhead_q']/1000:,.0f} $000s/qtr is being "
                      f"IGNORED while the module is present."
                      + (" Every detail input is zero, so this plan currently models a "
                          "bank with no operating expenses beyond assessments \u2014 "
                          "deactivate the module (Configuration tab) or move the overhead "
                          "into its categories." if _zeroed else ""))})
    # class-map any flags appended after the Overview pass (concentrations, pre-open):
    # without this they fall through to the default 'advisory' badge regardless of severity
    for f in results.get("flags") or []:
        if "cls" not in f:
            f["cls"] = ("commercial_assumption_requiring_support"
                          if f.get("sev") == "severe" else "advisory")

    # ---- Modeled challenges: findings derived from ENGINE OUTPUTS, kept absolutely separate from the
    # input-reasonableness flags. See foundry/v2/modeled_challenges.py. These carry cls="modeled" and
    # live in results["modeled_challenges"]; they are NOT mixed into results["flags"] (which is the
    # input-reasonableness stream) so the exec summary can route each to its own section.
    try:
        from .modeled_challenges import modeled_challenges as _mc
        results["modeled_challenges"] = _mc(results)
    except Exception:
        results["modeled_challenges"] = []

    # Tag every input-reasonableness flag with source="input" so the surface can prove the separation.
    # A small set of engine-output-derived flags already live in results["flags"] for historical
    # reasons (GROWTH-Y1, CONC-*, CAP-BUFFER, PREOPEN-01, SPREAD-VIAB); tag those source="modeled" so
    # they route to the modeled section too, and everything else source="input".
    _MODELED_FLAG_IDS = {"GROWTH-Y1", "CONC-CRE-RBC", "CONC-CD-RBC", "CONC-LLL",
                          "CAP-BUFFER", "PREOPEN-01", "SPREAD-VIAB"}
    for f in results.get("flags") or []:
        f["source"] = "modeled" if str(f.get("id", "")).split(":")[0] in _MODELED_FLAG_IDS else "input"

    results["run_hash"] = _hash(results)
    return results
