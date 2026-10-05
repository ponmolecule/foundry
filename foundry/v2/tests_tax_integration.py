"""Production engine, authoring, balance identity and exact audit tax checks."""
import copy
import json
import re
import subprocess
import unittest
from pathlib import Path
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import calculation_audit_workbook


def controlled(ppy=12, annual=False, detail=None, profile="pf_a"):
    c=json.loads(Path("foundry/fixtures/core_bank_test_base.json").read_text())
    c["pre_opening"]={"expenses":[]}
    c["parity_profile"]=profile
    c["charter_profile"]={"target_opening":"2028-01-01"}
    c["step_0"]["modules"]=["balance_driven_obs"]
    c["target_state"]["initial_capital"]=1_000_000
    a=c["assumptions"]
    for key in ("lending_products","deposit_products","securities_afs","securities_htm","capital_raises","scheduled_borrowings"):
        a[key]=[]
    for key in ("nie_detail","fixed_assets","interest_bearing_balances","managed_securities_portfolios","cac_feeds","tax_detail","overhead_q","overhead_per_period"):
        a.pop(key,None)
    a.update(periods_per_year=ppy,n_periods=ppy,tax_rate=.25,cash_yield=0,securities_yield=0,
             sweep_securities_yield=0,borrow_rate_ann=0,premises_equipment=0,
             premises_depreciation_annual=0,intangibles=0,other_assets=0,other_liabilities=0,
             aoci_sensitivity_annual=0,surplus_allocation_policy="cash",alll_floor_pct_loans=0,
             treasury_alloc_to_sweep=0)
    a["tax_policy"]={"interim_method":"annual_effective_rate" if annual else "ytd_actual"}
    if annual:a["tax_policy"]["annual_income_estimates"]={"2028":50_000}
    if detail:a["tax_detail"]=detail
    flows=[200_000,50_000,0]+[100_000]*9
    if ppy==4:flows=[sum(flows[i:i+3]) for i in range(0,12,3)]
    a["overhead_flow_spec"]={"trajectory":"explicit","values":flows,"period":"month" if ppy==12 else "quarter"}
    if profile=="pf_a":
        a["obs_exposures"]=[{"name":"Test service","_fee_product":True,"call_report_line":"obs","notional":0,
             "growth_per_period":0,"fee_streams":[{"name":"Test revenue","basis":"flat",
             "rate":{"params":{"amount_per_period":100_000*12/ppy}},"timing":{"start_period":1},
             "cost":{"kind":"none"}}]}]
    else:
        # Profile B's original balance-based fee grammar: 4.8m x 25% / 4 = 300k.
        a["obs_exposures"]=[{"name":"Test service","call_report_line":"obs","notional":4_800_000,
                             "growth_per_period":0,"fee_yield_ann":.25}]
    return c


class TaxIntegrationTests(unittest.TestCase):
    def test_actual_ytd_production_engine(self):
        c=controlled();self.assertEqual(validate_errors_v2(c),[])
        r=run_pf_a(c)
        self.assertEqual(r["is"]["pretax"][:3],[-100_000,50_000,100_000])
        self.assertEqual(r["is"]["tax"][:3],[0,0,12_500])
        self.assertEqual(r["is"]["nol"],[0]*12)

    def test_annual_loss_benefit_posts_as_asset_not_cash(self):
        for detail in (None,{"enabled":True,"va_mode":"full"},{"enabled":True,"va_mode":"none"}):
            c=controlled(annual=True,detail=detail)
            self.assertEqual(validate_errors_v2(c),[])
            r=run_pf_a(c);bs=r["bs"];is_=r["is"]
            self.assertEqual(is_["tax"][:3],[-25_000,12_500,25_000])
            self.assertEqual(bs["dta"][1:4],[25_000,12_500,0])
            self.assertAlmostEqual(bs["cash"][1],900_000,places=3)
            self.assertAlmostEqual(bs["equity"][1],925_000,places=3)
            self.assertAlmostEqual(bs["totalAssets"][1],925_000,places=3)
            self.assertEqual(sum(is_["tax"]),12_500)
            for p in range(13):
                liabilities=bs["deposits"][p]+bs["borrow"][p]+bs["borrowSched"][p]
                self.assertAlmostEqual(bs["totalAssets"][p],liabilities+bs["equity"][p],places=3)

    def test_quarterly_and_monthly_annual_totals_match(self):
        for annual in (False,True):
            m=run_pf_a(controlled(12,annual));q=run_pf_a(controlled(4,annual))
            self.assertEqual(sum(m["is"]["pretax"]),sum(q["is"]["pretax"]))
            self.assertEqual(sum(m["is"]["tax"]),sum(q["is"]["tax"]))
            self.assertAlmostEqual(m["bs"]["equity"][-1],q["bs"]["equity"][-1])

    def test_profile_b_uses_same_tax_year_ledger(self):
        c=controlled(4,annual=True,profile="pf_b")
        r=run_pf_b(c)
        self.assertEqual(r["is"]["pretax"],[50_000,0,0,0])
        self.assertEqual(r["is"]["tax"],[12_500,0,0,0])
        self.assertEqual(r["tax_interim"]["rows"][-1]["year"],2028)
        self.assertTrue(r["tax_interim"]["rows"][-1]["yearEnd"])

    def test_profile_b_loss_asset_and_balance_identity(self):
        c=controlled(4,annual=True,profile="pf_b")
        c["assumptions"]["overhead_flow_spec"]["values"]=[400_000,200_000,300_000,300_000]
        r=run_pf_b(c)
        self.assertEqual(r["is"]["tax"],[-25_000,25_000,0,0])
        self.assertEqual(r["bs"]["dta"],[25_000,0,0,0])
        self.assertEqual(r["bs"]["cash"][0],900_000)
        self.assertEqual(r["bs"]["equity"][0],925_000)
        for i in range(4):self.assertAlmostEqual(r["bs"]["totalAssets"][i],r["bs"]["equity"][i])

    def test_public_and_exact_audit_match_and_preserve_year_rate_units(self):
        c=controlled(annual=True);r=run_v2(c)
        self.assertEqual(r["tax_interim"]["rows"][0]["year"],2028)
        self.assertEqual(r["tax_interim"]["rows"][0]["effectiveRate"],.25)
        self.assertEqual(r["financials"]["is"]["tax"][0],-25)
        self.assertEqual(r["financials"]["bs"]["dta"][1],25)
        w=calculation_audit_workbook(c,r);ws=w["Income Taxes"]
        rows={row[2]:row for row in ws.iter_rows(values_only=True) if len(row)>2}
        self.assertEqual(rows["tax_interim.year"][4],2028)
        self.assertEqual(rows["tax_interim.effectiveRate"][4],.25)
        self.assertEqual(rows["tax_interim.tax"][4],-25)
        self.assertEqual(rows["tax_interim.dtaNet"][4],25)
        self.assertEqual(rows["tax_interim.dtaCurrentYear"][4],25)
        keys={row[2] for row in w["All Series"].iter_rows(values_only=True) if len(row)>2}
        self.assertIn("financials.is.currentYearTaxLoss",keys)
        self.assertIn("financials.is.nolUsedYtd",keys)

    def test_tax_assets_reconcile_in_endogenous_interest_solver(self):
        c=controlled(annual=True)
        c["assumptions"]["cash_yield"]=.04
        r=run_pf_a(c)
        self.assertGreater(r["bs"]["dta"][1],0)
        self.assertGreater(r["is"]["cashInt"][0],0)
        for p in range(1,13):
            self.assertAlmostEqual(r["bs"]["totalAssets"][p],r["bs"]["equity"][p],places=2)
            self.assertAlmostEqual(r["is"]["tax"][p-1],r["is"]["taxCurrent"][p-1]+r["is"]["taxDeferred"][p-1])

    def test_call_report_contains_tax_asset_and_ties(self):
        from .callreport import build_call_report, code_for_result
        c=controlled(4,annual=True)
        c["assumptions"]["overhead_flow_spec"]["values"]=[400_000,200_000,300_000,300_000]
        r=run_v2(c);rc={str(x["item"]):x["values"] for x in build_call_report(r,c)["RC"]["rows"]}
        self.assertEqual(rc["11"][0],25)
        for p in range(4):
            self.assertAlmostEqual(sum(rc[k][p] for k in ("1","2.a","2.b","4.a","4.d","6","10","11")),rc["12"][p],places=2)
        for key in ("dta","taxCurrent","taxDeferred","currentYearTaxLoss","nolUsedYtd"):
            self.assertIsNotNone(code_for_result(key))

    def test_missing_annual_estimate_rejected_by_public_validator(self):
        c=controlled(annual=True);c["assumptions"]["tax_policy"]["annual_income_estimates"]={}
        self.assertTrue(any("supported full-tax-year" in e["message"] for e in validate_errors_v2(c)))

    def test_browser_card_and_authoring_handlers(self):
        html=Path("web/console_v2.html").read_text()
        lo=html.index("function taxPolicySet(");hi=html.index("function _cfgModuleSelected(",lo)
        helpers=html[lo:hi]
        lo=html.index("function _isoUTC(");hi=html.index("function _interpDated(",lo)
        calendar=html[lo:hi]
        lo=html.index('  h += `<div class="cfgcard" id="card-tax">');hi=html.index('  h += `<div class="cfgcard" id="card-cecl">',lo)
        card=html[lo:hi]
        c=controlled(annual=True)
        js="let cfg="+json.dumps(c)+";let renders=0,previews=0;function renderContent(){renders++}function refresh(){previews++}function PPY(){return cfg.assumptions.periods_per_year}function NP(){return cfg.assumptions.n_periods}function _pf(v){return parseFloat(v)||0}const ICONS={percent:'%'};\n"+helpers+calendar+"\nfunction renderTax(){let h='';const A=cfg.assumptions;"+card+";return h;}\n"+"""
const initial=renderTax();
if(!initial.includes('Tax year 2028 supported annual income')||initial.includes('Legacy treatment'))throw Error('tax card mismatch');
taxEstimateSet('2028','');if(cfg.assumptions.tax_policy.annual_income_estimates['2028']!=null)throw Error('blank estimate not cleared');
taxEstimateSet('2028','50');if(cfg.assumptions.tax_policy.annual_income_estimates['2028']!==50000)throw Error('units wrong');
taxNolLimitSet('80');if(cfg.assumptions.tax_detail)throw Error('limit switched on deferred tax');
taxPolicySet('fiscal_year_end_month',6);cfg.charter_profile.target_opening='2028-10-01';
if(!renderTax().includes('Tax year 2029 supported annual income'))throw Error('fiscal calendar mismatch');
console.log('PASS tax authoring, unit conversion, blank clear, fiscal dates and unchanged recognition toggle');
"""
        result=subprocess.run(["node","-e",js],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=="__main__":unittest.main()
