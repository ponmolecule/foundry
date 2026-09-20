"""Regression gate for source-model interest balances and their zero-default UI."""
import copy, json
from pathlib import Path

from .engine_q_a import run_pf_a


def _cfg():
    c=json.loads(Path("foundry/fixtures/universal_template_bank.json").read_text())
    a=c["assumptions"]; a["periods_per_year"]=12; a["n_periods"]=4
    a["cash_yield"]=0; a["cash_target_pct_deposits"]=0
    a["interest_balance_model"]={
        "enabled":True,
        "mab_spec":{"source":"entered","trajectory":"flat","value":10},
        "scenario_rate_spec":{"source":"entered","trajectory":"flat","value":.12},
        "deposit_attach_rate_spec":{"source":"entered","trajectory":"flat","value":.90},
        "avg_noninterest_balance_per_mab_spec":{"source":"entered","trajectory":"flat","value":25000},
        "boost_attach_rate_spec":{"source":"entered","trajectory":"flat","value":.10},
        "avg_interest_balance_per_mab_spec":{"source":"entered","trajectory":"flat","value":150000},
        "customer_cost_rate_spec":{"source":"entered","trajectory":"flat","value":.035},
        "operating_cash_ratio_spec":{"source":"entered","trajectory":"flat","value":.30},
        "operating_cash_yield_spec":{"source":"entered","trajectory":"flat","value":.01},
        "frb_stock_ratio_spec":{"source":"entered","trajectory":"flat","value":.03},
        "frb_stock_yield_spec":{"source":"entered","trajectory":"flat","value":.005},
    }
    return c


def main():
    p=f=0
    def ck(name, ok):
        nonlocal p,f
        if ok: p+=1; print("  PASS ",name)
        else: f+=1; print("  FAIL ",name)

    base=_cfg(); del base["assumptions"]["interest_balance_model"]
    legacy=run_pf_a(copy.deepcopy(base))
    ck("absent model preserves legacy result shape", "operatingCash" not in legacy["bs"])
    r=run_pf_a(_cfg()); bs=r["bs"]; inc=r["is"]
    ck("M1 equity-linked operating cash and FRB stock are zero",
       bs["operatingCash"][1]==0 and bs["frbStock"][1]==0)
    ck("later operating cash and FRB stock use prior-period equity",
       all(abs(bs["operatingCash"][q]-.30*bs["equity"][q-1])<1e-6 and
               abs(bs["frbStock"][q]-.03*bs["equity"][q-1])<1e-6 for q in range(2,5)))
    ck("fiduciary AUA equations use raw-dollar balances per MAB",
       all(abs(x-225000)<1e-9 for x in bs["fiduciaryAuaNonInterest"][1:]) and
       all(abs(x-150000)<1e-9 for x in bs["fiduciaryAuaInterest"][1:]))
    ck("fiduciary income and customer expense periodize annual rates once",
       all(abs(x-3750)<1e-8 for x in inc["fiduciaryAuaInt"]) and
       all(abs(x-437.5)<1e-8 for x in inc["fiduciaryDepExp"]))
    ck("cash interest is the exact sum of its disclosed components",
       all(abs(inc["cashInt"][i]-sum(inc[k][i] for k in
           ("affiliatedCashInt","operatingCashInt","fiduciaryAuaInt","frbStockInt")))<1e-6
           for i in range(4)))
    ck("cash splits exactly between affiliated bank and operating cash",
       all(abs(bs["cash"][q]-bs["affiliatedCash"][q]-bs["operatingCash"][q])<1e-6
           for q in range(5)))
    linked=_cfg(); linked["assumptions"]["interest_balance_model"]["mab_source"]={
        "source":"fee_stream_quantity","series_id":"fee-qty-migrated-universal"}
    lr=run_pf_a(linked)
    ck("MAB can consume the canonical Migrated-account fee-stream quantity",
       lr["bs"]["mabCount"][1:]==[100.0]*4)
    delayed=_cfg(); delayed["assumptions"]["interest_balance_model"]["affiliated_cash_interest_start_period"]=2
    dr=run_pf_a(delayed)
    ck("affiliated-bank interest start period suppresses unsupported M1 income",
       dr["is"]["affiliatedCashInt"][0]==0 and dr["is"]["affiliatedCashInt"][1]>0)
    ck("FRB stock is included in total assets",
       all(abs(bs["totalAssets"][q]-(bs["cash"][q]+bs["sec"][q]+bs["afsBook"][q]+
           bs["htmBook"][q]+bs["netLoans"][q]+r["fixed_assets"]["net"][q]+
           _cfg()["assumptions"]["intangibles"]+_cfg()["assumptions"]["other_assets"]+
           bs["prepaidOpex"][q]+bs["msr"][q]+bs["frbStock"][q]))<1e-5 for q in range(5)))
    html=Path("web/console_v2.html").read_text()
    ck("UI states per-MAB values are dollars and exposes canonical links",
       "Per-MAB paste values are dollars, not $000s" in html and
       "Link Customer Acquisition" in html and "Link Fee Stream quantity" in html and
       "Affiliated-bank interest begins" in html)
    print(f"\n{p} passed, {f} failed")
    if f: raise SystemExit(1)


if __name__=="__main__": main()
