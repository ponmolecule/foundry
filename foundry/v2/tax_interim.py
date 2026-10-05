"""Tax-year ledger and ASC 740-270 interim provision for one ordinary-income pool.

Amounts are dollars, not $000s. Book ordinary income is assumed to equal taxable
income before NOLs. No cash-payment schedule, temporary differences, tax credits,
pre-2018 losses, section 382 limitation, or multi-jurisdiction consolidation is
inferred. Recognition is an analyst assessment, never inferred from cumulative
earnings. See docs/R284_TAX_METHOD.md for the supported accounting contract.

evaluate() is pure with respect to the ledger: an endogenous balance-sheet solver
may call it repeatedly. Only commit() advances a period.
"""
from __future__ import annotations

from math import isfinite
from .timebase import model_period_end_date
from .regparams import REG_PARAMS


MONEY_SERIES = ("taxCurrent", "taxDeferred", "dtaGross", "dtaVA", "dtaNet",
                "taxIncomeYtd", "taxCurrentYtd", "taxProvisionYtd",
                "currentYearTaxLoss", "nolUsedYtd", "dtaCurrentYear", "dtaPriorYear")


def tax_year(cfg, period, ppy, end_month=12):
    """Label a tax year by the calendar year in which it ENDS."""
    d = model_period_end_date(cfg, period, ppy)
    return d.year + int(d.month > end_month), d.month == end_month


def _number(v, name, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v):
        raise ValueError(f"{name} must be a finite number")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ValueError(f"{name} is out of range")
    return float(v)


def validate_tax_policy(a, cfg):
    tp = a.get("tax_policy")
    td = a.get("tax_detail")
    tp = {} if tp is None else tp
    td = {} if td is None else td
    if not isinstance(tp, dict) or not isinstance(td, dict):
        raise ValueError("tax_policy and tax_detail must be objects")
    if "enabled" in td and not isinstance(td["enabled"], bool):
        raise ValueError("tax_detail.enabled must be boolean")
    unknown = set(tp) - {"interim_method", "fiscal_year_end_month", "opening_nol",
                         "opening_nol_dta_net", "annual_income_estimates",
                         "estimate_overrides", "recognition_note", "nol_utilization_limit_pct"}
    if unknown:
        raise ValueError("unsupported tax_policy fields: " + ", ".join(sorted(unknown)))
    method = tp.get("interim_method", "ytd_actual")
    if method not in {"ytd_actual", "annual_effective_rate"}:
        raise ValueError("interim_method must be ytd_actual or annual_effective_rate")
    end = tp.get("fiscal_year_end_month", 12)
    if isinstance(end, bool) or not isinstance(end, int) or not 1 <= end <= 12:
        raise ValueError("fiscal_year_end_month must be an integer from 1 to 12")
    ppy = a.get("periods_per_year") or 4
    if ppy == 4 and end not in {3, 6, 9, 12}:
        raise ValueError("quarterly runs require a quarter-end tax year; use monthly cadence for other year-ends")
    if td.get("va_mode", "auto") not in {"auto", "full", "none", "pct"}:
        raise ValueError("va_mode must be full, auto (legacy full allowance), none, or pct")
    _number(td.get("va_pct", 0.0), "va_pct", 0, 1)
    _number(td.get("nol_utilization_limit_pct", REG_PARAMS["tax"]["nol_utilization_limit_pct"]),
            "nol_utilization_limit_pct", 0, 1)
    if "nol_utilization_limit_pct" in tp:
        _number(tp["nol_utilization_limit_pct"], "tax_policy.nol_utilization_limit_pct", 0, 1)
    rate = _number(a.get("tax_rate"), "tax_rate", 0, 1)
    n = _number(tp.get("opening_nol", 0.0), "opening_nol", 0)
    if tp.get("opening_nol_dta_net") is not None:
        net = _number(tp["opening_nol_dta_net"], "opening_nol_dta_net", 0, n * rate)
        if not td.get("enabled", bool(td)) and net:
            raise ValueError("opening_nol_dta_net requires deferred-tax recognition enabled")
    estimates = tp.get("annual_income_estimates", {})
    if not isinstance(estimates, dict):
        raise ValueError("annual_income_estimates must be keyed by tax-year ending year")
    for y, v in estimates.items():
        if not isinstance(y, str) or not y.isdigit() or str(int(y)) != y or not 1900 <= int(y) <= 9999:
            raise ValueError("annual income estimate keys must be tax-year ending years")
        _number(v, f"annual_income_estimates.{y}")
        if v == 0:
            raise ValueError("a zero annual-income estimate has no reliable effective rate; select YTD actual")
    overrides = tp.get("estimate_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("estimate_overrides must be keyed by model period")
    horizon = a.get("n_periods") or 12
    for p, v in overrides.items():
        if not isinstance(p, str) or not p.isdigit() or str(int(p)) != p or not 1 <= int(p) <= horizon:
            raise ValueError("estimate override period is outside the model horizon")
        _number(v, f"estimate_overrides.{p}")
        if v == 0:
            raise ValueError("a zero annual-income estimate has no reliable effective rate")
    if method == "annual_effective_rate":
        years = {tax_year(cfg, p, ppy, end)[0] for p in range(1, horizon + 1)}
        missing = sorted(y for y in years if str(y) not in estimates)
        if missing:
            raise ValueError("annual effective rate requires supported full-tax-year income estimates for "
                             + ", ".join(map(str, missing)))


class InterimTaxLedger:
    def __init__(self, cfg, assumptions=None, ppy=None):
        self.cfg = cfg
        self.a = assumptions if assumptions is not None else cfg["assumptions"]
        validate_tax_policy(self.a, cfg)
        self.policy = self.a.get("tax_policy") or {}
        self.detail = self.a.get("tax_detail") or {}
        self.enabled = bool(self.detail) and self.detail.get("enabled") is not False
        self.rate = float(self.a["tax_rate"])
        self.ppy = ppy or self.a.get("periods_per_year") or 4
        self.end_month = self.policy.get("fiscal_year_end_month", 12)
        self.method = self.policy.get("interim_method", "ytd_actual")
        self.limit = float(self.policy.get("nol_utilization_limit_pct", self.detail.get("nol_utilization_limit_pct",
                                           REG_PARAMS["tax"]["nol_utilization_limit_pct"])))
        mode = self.detail.get("va_mode", "auto")
        self.recognized = (0.0 if not self.enabled or mode in {"auto", "full"}
                           else 1.0 - float(self.detail.get("va_pct", 0)) if mode == "pct" else 1.0)
        self.nol = float(self.policy.get("opening_nol", 0))
        self.dta = float(self.policy.get("opening_nol_dta_net", self.nol * self.rate * self.recognized))
        self.opening_dta = self.dta
        self.year = None
        self.income = self.total = self.current = 0.0
        self.year_open_nol = self.nol
        self.year_open_dta = self.dta
        self.estimate = None
        self.last_period = 0
        self.rows = []

    def evaluate(self, period, pretax):
        if period != self.last_period + 1:
            raise ValueError("tax ledger periods must be evaluated and committed in order")
        year, closing = tax_year(self.cfg, period, self.ppy, self.end_month)
        new_year = year != self.year
        n = self.nol if new_year else self.year_open_nol
        opening_dta = self.dta if new_year else self.year_open_dta
        old_income = 0.0 if new_year else self.income
        old_total = 0.0 if new_year else self.total
        old_current = 0.0 if new_year else self.current
        ytd = old_income + _number(pretax, "ordinary pretax income")
        # Only prior-year NOLs are subject to the configured annual limitation.
        used = min(n, self.limit * max(0.0, ytd))
        remaining = max(0.0, n - used)
        loss = max(0.0, -ytd)
        annual = (self.policy.get("annual_income_estimates") or {}).get(str(year))
        estimate = annual if new_year else self.estimate
        estimate = (self.policy.get("estimate_overrides") or {}).get(str(period), estimate)
        # At the real tax-year end, actual results replace estimates. A horizon
        # endpoint in another month must NEVER create an artificial tax year.
        annual_method = self.method == "annual_effective_rate" and not closing
        # A YTD loss is a provisional tax loss, NOT a prior-year carryforward.
        # A supported profitable annual outlook establishes same-year recovery
        # independently of the allowance on carryforwards dependent on later years.
        gross_dta = (remaining + loss) * self.rate
        prior_dta = remaining * self.rate * self.recognized
        current_year_dta = loss * self.rate * (1.0 if annual_method and estimate > 0 else self.recognized)
        net_dta = prior_dta + current_year_dta
        legal_current_ytd = (max(0.0, ytd) - used) * self.rate
        if annual_method:
            if estimate > 0:
                annual_used = min(n, self.limit * estimate)
                etr = self.rate * (1.0 - (1.0 - self.recognized) * annual_used / estimate)
            else:
                etr = self.rate * self.recognized
            ordinary_total = ytd * etr
            if ytd < 0:
                # 25-9 / 30-30: recoverable this year, or recognizable at year-end.
                recover_in_year = min(loss, max(0.0, estimate - ytd))
                benefit_cap = self.rate * (recover_in_year + (loss - recover_in_year) * self.recognized)
                ordinary_total = max(ordinary_total, -benefit_cap)
            # A change to the BEGINNING DTA's allowance is discrete (25-7),
            # excluded from the AETR. This single-pool module supports a fixed
            # future-realization assessment; it never fabricates a judgment change.
            discrete = opening_dta - n * self.rate * self.recognized
            total_ytd = ordinary_total + discrete
            basis = "estimated annual effective rate"
        else:
            # ASC 740-270-30-18 actual-YTD fallback; also exact annual true-up.
            # Full VA means no benefit on a YTD loss and no tax on subsequent
            # income until that same-year loss has been absorbed (25-11).
            total_ytd = legal_current_ytd + opening_dta - net_dta
            etr = total_ytd / ytd if ytd else 0.0
            basis = "tax-year-end actual true-up" if closing else "actual YTD (annual estimate unavailable)"
        deferred = self.dta - net_dta
        total = total_ytd - old_total
        current = total - deferred
        current_ytd = old_current + current
        end_nol = remaining + (loss if closing else 0.0)
        return {
            "tax": total, "nol": end_nol,
            "taxCurrent": current, "taxDeferred": deferred,
            "dtaGross": gross_dta, "dtaVA": gross_dta - net_dta, "dtaNet": net_dta,
            "taxIncomeYtd": ytd, "taxCurrentYtd": current_ytd,
            "taxProvisionYtd": total_ytd, "currentYearTaxLoss": loss,
            "nolUsedYtd": used, "dtaCurrentYear": current_year_dta, "dtaPriorYear": prior_dta,
            "year": year, "yearEnd": closing, "annualEstimate": estimate,
            "effectiveRate": etr, "basis": basis,
            "legalCurrentYtd": legal_current_ytd, "yearOpeningNol": n,
            "yearOpeningDta": opening_dta, "period": period,
        }

    def commit(self, row):
        if row["period"] != self.last_period + 1:
            raise ValueError("tax ledger cannot commit a period twice")
        self.year = row["year"]
        self.year_open_nol = row["yearOpeningNol"]
        self.year_open_dta = row["yearOpeningDta"]
        self.income = row["taxIncomeYtd"]
        self.total = row["taxProvisionYtd"]
        self.current = row["taxCurrentYtd"]
        self.nol = row["nol"]
        self.dta = row["dtaNet"]
        self.estimate = row["annualEstimate"]
        self.last_period = row["period"]
        self.rows.append(dict(row))

    def audit(self):
        return {"method": self.method, "fiscal_year_end_month": self.end_month,
                "book_tax_assumption": "ordinary book income equals taxable income before NOLs",
                "valuation_assessment": "analyst-entered; auto maps to full allowance on unrealized carryforwards",
                "rows": self.rows}
