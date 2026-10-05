"""Numerical accounting tests independent of engagement-specific formulas."""
import copy
import json
import math
import random
import unittest
from .tax_interim import InterimTaxLedger, validate_tax_policy


def cfg(ppy=12, opening="2028-01-01", detail=None, policy=None, n=None):
    return {"charter_profile": {"target_opening": opening},
            "assumptions": {"periods_per_year": ppy, "n_periods": n or ppy,
                            "tax_rate": .25, "tax_detail": detail or {}, "tax_policy": policy or {}}}


def run_path(values, c=None):
    ledger = InterimTaxLedger(c or cfg(n=max(12, len(values))))
    rows = []
    for i, value in enumerate(values, 1):
        row = ledger.evaluate(i, value)
        ledger.commit(row)
        rows.append(row)
    return rows


class TaxInterimTests(unittest.TestCase):
    def test_same_year_loss_is_not_80_percent_limited(self):
        rows = run_path([-100, 50, 100] + [0]*9)
        self.assertEqual([r["tax"] for r in rows[:3]], [0, 0, 12.5])
        self.assertEqual([r["nol"] for r in rows], [0]*12)
        self.assertEqual(rows[1]["currentYearTaxLoss"], 50)

    def test_profitable_annual_outlook_recognizes_loss_even_with_full_future_va(self):
        c = cfg(detail={"enabled": True, "va_mode": "auto"}, policy={
            "interim_method": "annual_effective_rate", "annual_income_estimates": {"2028": 50}})
        rows = run_path([-100, 50, 100] + [0]*9, c)
        self.assertEqual([r["tax"] for r in rows[:3]], [-25, 12.5, 25])
        self.assertEqual([r["dtaNet"] for r in rows[:3]], [25, 12.5, 0])
        self.assertEqual([r["taxCurrent"] for r in rows[:3]], [0, 0, 12.5])
        self.assertEqual(rows[0]["dtaVA"], 0)
        self.assertEqual(sum(r["tax"] for r in rows), 12.5)

    def test_future_dta_recognition_full_partial_and_none(self):
        for mode, fraction, expected in [("none", 0, 25), ("pct", .5, 12.5), ("full", 1, 0), ("auto", 1, 0)]:
            c = cfg(detail={"enabled": True, "va_mode": mode, "va_pct": fraction})
            r = run_path([-100]+[0]*11, c)
            self.assertEqual(r[0]["tax"], -expected)
            self.assertEqual(r[-1]["dtaNet"], expected)
            self.assertEqual(r[-1]["nol"], 100)
            self.assertEqual(r[0]["nol"], 0)
            self.assertEqual(r[-1]["dtaGross"]-r[-1]["dtaVA"], expected)

    def test_loss_becomes_nol_only_at_actual_tax_year_end(self):
        c = cfg(n=24)
        rows = run_path([-100]+[0]*11+[50]+[0]*11, c)
        self.assertEqual(rows[10]["nol"], 0)
        self.assertEqual(rows[11]["nol"], 100)
        self.assertEqual(rows[12]["nolUsedYtd"], 40)
        self.assertEqual(rows[12]["tax"], 2.5)
        self.assertEqual(rows[23]["nol"], 60)

    def test_reversing_income_restores_provisional_prior_year_deduction(self):
        c=cfg(policy={"opening_nol":100})
        r=run_path([100,-50,100]+[0]*9,c)
        self.assertEqual([x["nol"] for x in r[:3]], [20,60,0])
        self.assertEqual([x["tax"] for x in r[:3]], [5,-2.5,10])

    def test_withheld_benefit_is_absorbed_before_later_tax(self):
        r=run_path([-100,75,25,20]+[0]*8)
        self.assertEqual([x["tax"] for x in r[:4]], [0,0,0,5])

    def test_profitable_month_followed_by_loss_reverses_provision(self):
        r=run_path([100,-150,25,50]+[0]*8)
        self.assertEqual([x["tax"] for x in r[:4]], [25,-25,0,6.25])

    def test_supported_annual_loss_uses_recognizable_benefit_rate(self):
        for mode, fraction, expected in [("full",0,0),("none",0,.25),("pct",.6,.1)]:
            c=cfg(detail={"enabled":True,"va_mode":mode,"va_pct":fraction}, policy={
                "interim_method":"annual_effective_rate", "annual_income_estimates":{"2028":-100}})
            r=run_path([100,-200]+[0]*10,c)
            self.assertAlmostEqual(r[0]["tax"],100*expected)
            self.assertAlmostEqual(r[1]["tax"],-200*expected)
            self.assertAlmostEqual(sum(x["tax"] for x in r),-100*expected)

    def test_annual_estimate_revision_catches_up_ytd_and_year_end_uses_actual(self):
        c=cfg(policy={"opening_nol":100,"interim_method":"annual_effective_rate",
                      "annual_income_estimates":{"2028":100},"estimate_overrides":{"2":200}})
        r=run_path([50,50]+[20]*10,c)
        self.assertAlmostEqual(r[0]["tax"],2.5)
        self.assertEqual(r[1]["tax"],10)
        self.assertEqual(sum(x["tax"] for x in r),50)
        self.assertEqual(r[-1]["legalCurrentYtd"],50)

    def test_recognized_prior_year_dta_is_consumed_not_double_benefited(self):
        c=cfg(detail={"enabled":True,"va_mode":"none"},policy={"opening_nol":100})
        r=run_path([50]+[0]*11,c)
        self.assertEqual(r[0]["taxCurrent"],2.5)
        self.assertEqual(r[0]["taxDeferred"],10)
        self.assertEqual(r[0]["tax"],12.5)
        self.assertEqual(r[0]["dtaNet"],15)

    def test_opening_allowance_release_is_discrete(self):
        c=cfg(detail={"enabled":True,"va_mode":"none"},policy={"opening_nol":100,
              "opening_nol_dta_net":0,"interim_method":"annual_effective_rate",
              "annual_income_estimates":{"2028":200}})
        r=run_path([50]+[0]*11,c)
        self.assertEqual(r[0]["effectiveRate"],.25)
        self.assertEqual(r[0]["tax"],-12.5)  # 12.5 ordinary expense less 25 discrete release
        self.assertEqual(r[0]["taxDeferred"],-15)
        self.assertEqual(r[0]["taxCurrent"],2.5)
        self.assertEqual(sum(x["tax"] for x in r),-12.5)

    def test_fiscal_year_and_midyear_opening_follow_calendar(self):
        c=cfg(opening="2028-10-01",n=12,policy={"fiscal_year_end_month":6})
        r=run_path([-100]+[0]*8+[50,0,0],c)
        self.assertEqual(r[0]["year"],2029)
        self.assertTrue(r[8]["yearEnd"])
        self.assertEqual(r[8]["nol"],100)
        self.assertEqual(r[9]["year"],2030)
        self.assertEqual(r[9]["tax"],2.5)
        self.assertFalse(r[-1]["yearEnd"])

    def test_horizon_end_is_not_a_tax_year_end(self):
        r=run_path([-100]+[0]*11,cfg(opening="2028-05-01"))
        self.assertTrue(r[7]["yearEnd"])
        self.assertFalse(r[-1]["yearEnd"])
        self.assertEqual(r[-1]["year"],2029)

    def test_preview_is_pure_and_duplicate_commit_rejected(self):
        l=InterimTaxLedger(cfg())
        a=l.evaluate(1,-100)
        self.assertEqual(l.evaluate(1,-100),a)
        self.assertEqual(l.nol,0)
        l.commit(a)
        with self.assertRaises(ValueError):l.commit(a)

    def test_monthly_and_quarterly_provisions_tie_at_quarter_end(self):
        vals=[-100,20,30,50,60,-20,-10,30,40,20,-30,50]
        for detail in ({},{"enabled":True,"va_mode":"none"},{"enabled":True,"va_mode":"pct","va_pct":.6}):
            for method in ("ytd_actual","annual_effective_rate"):
                p={"opening_nol":75,"interim_method":method,"annual_income_estimates":{"2028":sum(vals)}}
                m=run_path(vals,cfg(detail=detail,policy=p))
                q=run_path([sum(vals[i:i+3]) for i in range(0,12,3)],cfg(ppy=4,detail=detail,policy=p))
                for i in range(4):
                    self.assertAlmostEqual(sum(x["tax"] for x in m[i*3:i*3+3]),q[i]["tax"])
                    self.assertAlmostEqual(m[i*3+2]["dtaNet"],q[i]["dtaNet"])
                    self.assertAlmostEqual(m[i*3+2]["nol"],q[i]["nol"])

    def test_random_paths_preserve_annual_tax_and_nol_conservation(self):
        rng=random.Random(740270)
        for _ in range(100):
            n=rng.uniform(0,1000);recognition=rng.choice([0,.4,1]);income=[rng.uniform(-100,100) for _ in range(36)]
            c=cfg(n=36,detail={"enabled":True,"va_mode":"pct","va_pct":1-recognition},policy={"opening_nol":n})
            rows=run_path(income,c);previous_dta=n*.25*recognition
            for y in range(3):
                block=rows[y*12:y*12+12];b=sum(income[y*12:y*12+12]);used=min(n,.8*max(b,0))
                current=(max(b,0)-used)*.25;n=n-used+max(-b,0);dta=n*.25*recognition
                self.assertAlmostEqual(sum(r["tax"] for r in block),current+previous_dta-dta)
                self.assertAlmostEqual(sum(r["taxCurrent"] for r in block),current)
                self.assertAlmostEqual(block[-1]["nol"],n)
                previous_dta=dta

    def test_invalid_assessments_fail_closed(self):
        policies=[{"opening_nol":-1},{"opening_nol":True},{"opening_nol":math.nan},
                  {"fiscal_year_end_month":13},{"interim_method":"bogus"},
                  {"interim_method":"annual_effective_rate"},
                  {"annual_income_estimates":{"2028":0}},
                  {"estimate_overrides":{"13":10}},{"pre_2018_nol":1},
                  {"annual_income_estimates":[]},{"estimate_overrides":[]},
                  {"annual_income_estimates":{"02028":10}},
                  {"estimate_overrides":{"02":10}}]
        for p in policies:
            with self.subTest(p=p),self.assertRaises(ValueError):InterimTaxLedger(cfg(policy=p))
        for bad in (math.nan, math.inf, -.1, 1.1, True):
            c=cfg();c["assumptions"]["tax_rate"]=bad
            with self.subTest(rate=bad),self.assertRaises(ValueError):InterimTaxLedger(c)
        for key in ("tax_policy", "tax_detail"):
            for bad in ([], False, ""):
                c=cfg();c["assumptions"][key]=bad
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):InterimTaxLedger(c)
        with self.assertRaises(ValueError):InterimTaxLedger(cfg(ppy=4,policy={"fiscal_year_end_month":5}))
        with self.assertRaises(ValueError):InterimTaxLedger(cfg(detail={"va_mode":"pct","va_pct":1.1}))

    def test_large_early_loss_with_supported_annual_profit(self):
        c=cfg(policy={"interim_method":"annual_effective_rate","annual_income_estimates":{"2028":60_000_000}})
        r=run_path([-1_600_000,1_500_000],c)
        self.assertAlmostEqual(r[0]["tax"],-400_000)
        self.assertAlmostEqual(r[1]["tax"],375_000)
        self.assertAlmostEqual(r[1]["taxProvisionYtd"],-25_000)
        self.assertAlmostEqual(r[1]["dtaNet"],25_000)


if __name__=="__main__":unittest.main()
