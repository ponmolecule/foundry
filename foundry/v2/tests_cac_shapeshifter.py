"""Golden tests for cadence-agnostic, N-channel Customer Acquisition authoring.

The customer-base feeder must accept explicit annual driver schedules without learning
engagement-specific channel names.  Legacy scalar+growth configs remain unchanged.
"""
import copy
import json
import math

from . import run_q
from .cac_feeder import cac_auc_rollforward, channel_new_customers, channel_avg_auc, channel_spend


def _eq(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def main():
    P = F = 0
    def ck(name, cond, detail=""):
        nonlocal P, F
        if cond:
            P += 1; print("  PASS ", name)
        else:
            F += 1; print("  FAIL ", name, detail)

    # 1) Legacy semantics are frozen.
    legacy = {"name":"Affiliate","method":"pool_conversion",
              "params":{"pool":1000,"pool_growth":0.10,"conversion_rate":0.02,"conversion_growth":0.0},
              "avg_auc_per_customer":500000,"avg_auc_growth":0.05}
    ck("legacy pool x conversion Y1 unchanged", _eq(channel_new_customers(legacy,1),20.0))
    ck("legacy pool growth Y2 unchanged", _eq(channel_new_customers(legacy,2),22.0))
    ck("legacy avg AUC growth Y2 unchanged", _eq(channel_avg_auc(legacy,2),525000.0))

    # 2) Explicit annual schedules override the legacy scalar/growth values generically.
    scheduled = copy.deepcopy(legacy)
    scheduled["driver_specs"] = {
        "pool": {"mode":"explicit","cadence":"year","values":[1000,1600,2200]},
        "conversion_rate": {"mode":"explicit","cadence":"year","values":[0.02,0.03,0.04]},
        "avg_auc_per_customer": {"mode":"explicit","cadence":"year","values":[500000,600000,750000]},
    }
    ck("explicit pool/conversion Y2", _eq(channel_new_customers(scheduled,2),48.0))
    ck("explicit avg AUC Y3", _eq(channel_avg_auc(scheduled,3),750000.0))

    # 3) Same generic schedule contract works for spend/CAC and spend audit.
    direct = {"name":"Anything the user calls it","method":"spend_cac",
              "params":{"spend":1,"cac":1},"avg_auc_per_customer":1,
              "driver_specs":{
                  "spend":{"mode":"explicit","cadence":"year","values":[1000000,1500000,2100000]},
                  "cac":{"mode":"explicit","cadence":"year","values":[1000,750,700]},
                  "avg_auc_per_customer":{"mode":"explicit","cadence":"year","values":[250000,300000,350000]},
              }}
    ck("spend/CAC explicit Y2", _eq(channel_new_customers(direct,2),2000.0))
    ck("spend audit uses same schedule", _eq(channel_spend(direct,3),2100000.0))

    # 4) FTE productivity uses the same driver vocabulary; no named channel special case.
    sales = {"name":"RIA referrals","method":"fte_productivity","params":{},"avg_auc_per_customer":0,
             "driver_specs":{
                 "ftes":{"mode":"explicit","cadence":"year","values":[2,3,4]},
                 "per_fte":{"mode":"explicit","cadence":"year","values":[20,25,30]},
                 "comp_per_fte":{"mode":"explicit","cadence":"year","values":[120000,125000,130000]},
                 "avg_auc_per_customer":{"mode":"explicit","cadence":"year","values":[400000,450000,500000]},
             }}
    ck("FTE productivity explicit Y3", _eq(channel_new_customers(sales,3),120.0))
    ck("FTE spend explicit Y2", _eq(channel_spend(sales,2),375000.0))

    # 5) Feed-level attrition is itself a generic annual driver schedule.
    feed = {"channels":[scheduled,direct,sales],"beginning_auc":0,"beginning_customers":0,
            "attrition_rate":0.99,
            "driver_specs":{"attrition_rate":{"mode":"explicit","cadence":"year","values":[0.0,0.10,0.20]}},
            "intra_year_shape":"linear"}
    rf = cac_auc_rollforward(feed, 36, 12)
    ck("N-channel feed aggregates three arbitrary channels", len(rf["annual"][0]["channels"]) == 3)
    ck("feed-level explicit attrition Y1 overrides scalar", _eq(rf["annual"][0]["cust_lost"],0.0))
    ck("feed-level explicit attrition Y2 applies", _eq(rf["annual"][1]["cust_lost"],rf["annual"][0]["end_cust"]*0.10))

    # 6) Seven annual source columns resolve to either monthly or quarterly engine cadence
    # with the same year-end AUC economics.
    seven = {"channels":[{
        "name":"Partner referrals","method":"pool_conversion","params":{},"avg_auc_per_customer":0,
        "driver_specs":{
            "pool":{"mode":"explicit","cadence":"year","values":[1000,1200,1500,1800,2200,2600,3000]},
            "conversion_rate":{"mode":"explicit","cadence":"year","values":[.02,.025,.03,.032,.035,.037,.04]},
            "avg_auc_per_customer":{"mode":"explicit","cadence":"year","values":[100000,110000,120000,130000,140000,150000,160000]},
        }}],
        "driver_specs":{"attrition_rate":{"mode":"explicit","cadence":"year","values":[0,.02,.03,.04,.04,.05,.05]}},
        "series_id":"cac-auc-seven","customer_count_series_id":"cac-count-seven",
        "beginning_auc":0,"beginning_customers":0,"intra_year_shape":"linear"}
    mo = cac_auc_rollforward(seven, 84, 12)
    qu = cac_auc_rollforward(seven, 28, 4)
    ck("seven-year source schedule accepted", len(mo["annual"]) == 7 and len(qu["annual"]) == 7)
    ck("monthly and quarterly annual customer economics match",
       all(_eq(mo["annual"][i]["end_cust"],qu["annual"][i]["end_cust"]) for i in range(7)))
    ck("monthly and quarterly year-end AUC match",
       all(_eq(mo["year_end_auc"][i],qu["year_end_auc"][i]) for i in range(7)))
    ck("monthly period-end series lands exactly on each annual ending AUC",
       all(_eq(mo["auc_end_by_period"][(i+1)*12-1],mo["year_end_auc"][i]) for i in range(7)))
    ck("canonical monthly AUC path is identical in monthly and quarterly models",
       len(qu["auc_end_by_month"]) == 84 and
       all(_eq(mo["auc_end_by_period"][i], qu["auc_end_by_month"][i]) for i in range(84)))
    ck("quarterly AUC is sampled from canonical month-end M3/M6/M9/M12",
       all(_eq(qu["auc_end_by_period"][q], qu["auc_end_by_month"][(q+1)*3-1]) for q in range(28)))
    ck("canonical monthly customer-count path is identical in monthly and quarterly models",
       len(qu["customer_end_by_month"]) == 84 and
       all(_eq(mo["customer_end_by_period"][i], qu["customer_end_by_month"][i]) for i in range(84)))
    ck("quarterly customer EOP is sampled from canonical M3/M6/M9/M12",
       all(_eq(qu["customer_end_by_period"][q], qu["customer_end_by_month"][(q+1)*3-1]) for q in range(28)))
    ck("quarterly Account-fee customer level averages the three canonical monthly levels",
       all(_eq(qu["customer_level_by_period"][q],
               sum(qu["customer_end_by_month"][q*3:(q+1)*3])/3.0) for q in range(28)))
    ck("CAC publishes customer-count Derived Series beside AUC",
       "cac-count-seven" in mo["derived_series"] and
       mo["derived_series"]["cac-count-seven"]["semantic_type"] == "customer_count_level")
    # A monthly balance-linked annualized rate must aggregate identically whether the
    # presentation engine is monthly or quarterly.  This is the exact seam needed by
    # future AUC-linked Opex (e.g. annual fraud provision rate on period-end AUC).
    annual_rate = 0.0001
    mo_exp = [v * annual_rate / 12.0 for v in mo["auc_end_by_month"]]
    qu_exp = [sum(qu["auc_end_by_month"][q*3:(q+1)*3]) * annual_rate / 12.0 for q in range(28)]
    ck("monthly AUC-linked expense aggregates exactly to quarterly presentation",
       all(_eq(sum(mo_exp[q*3:(q+1)*3]), qu_exp[q]) for q in range(28)))

    # 7) Explicit schedules can intentionally extend by holding the last authored value.
    hold = copy.deepcopy(scheduled)
    hold["driver_specs"]["pool"] = {"mode":"explicit","cadence":"year","values":[1000,1500],"extend":"hold"}
    hold["driver_specs"]["conversion_rate"] = {"mode":"flat","value":0.02,"cadence":"year"}
    ck("explicit hold-last extension", _eq(channel_new_customers(hold,5),30.0))

    # 8) A generic growth spec is available in the same driver contract.
    gs = {"name":"Organic","method":"pool_conversion","params":{},"avg_auc_per_customer":0,
          "driver_specs":{
              "pool":{"mode":"growth","base":1000,"growth_spec":{"rate":0.10,"period":"year","method":"step","anchor":"model_year"}},
              "conversion_rate":{"mode":"flat","value":0.02},
              "avg_auc_per_customer":{"mode":"flat","value":500000},
          }}
    ck("generic driver growth mode Y3", _eq(channel_new_customers(gs,3),24.2))

    # 9) Public run output exposes the calculated customer-base roll-forward for audit/UI use.
    cfg=json.load(open("foundry/fixtures/universal_template_bank.json"))
    cfg["assumptions"]["periods_per_year"]=12; cfg["assumptions"]["n_periods"]=84
    cfg["assumptions"]["cac_feeds"]={"growth":copy.deepcopy(seven)}
    out=run_q.run_v2(cfg)
    ca=((out.get("customer_acquisition") or {}).get("growth") or {})
    ck("public result surfaces seven-year customer-base audit", len(ca.get("annual") or [])==7)
    ck("public customer-base monetary audit uses Foundry $000s units",
       ca.get("moneyUnits")=="$000s" and _eq(ca["annual"][0]["end_auc"],mo["annual"][0]["end_auc"]/1000.0))
    ck("public customer counts remain natural counts",
       ca.get("customerUnits")=="count" and _eq(ca["annual"][0]["end_cust"],mo["annual"][0]["end_cust"]))
    cfgq=copy.deepcopy(cfg); cfgq["assumptions"]["periods_per_year"]=4; cfgq["assumptions"]["n_periods"]=28
    outq=run_q.run_v2(cfgq); caq=((outq.get("customer_acquisition") or {}).get("growth") or {})
    ck("quarterly public result retains canonical monthly AUC path",
       len(caq.get("aucEndByMonth") or [])==84 and
       all(_eq(caq["aucEndByMonth"][i], ca.get("aucEndByPeriod")[i]) for i in range(84)))
    ck("public result surfaces canonical customer-count path and explicit downstream measures",
       len(caq.get("customerEndByMonth") or [])==84 and len(caq.get("customerLevelByPeriod") or [])==28
       and len(caq.get("customerAverageByPeriod") or [])==28 and len(caq.get("customerAnnualCountByPeriod") or [])==28
       and caq.get("aucIntraYearShape")=="linear" and caq.get("customerIntraYearShape")=="linear")

    # 10) A Fee Product can consume the CAC-owned customer book directly without re-authoring
    # another count path. The downstream stream must name WHICH customer semantic it consumes.
    # "annual_count" applies the model-year count to the full annual price; active-client measures
    # instead observe CAC's independently-authored client stock path.
    platform_feed={
        "series_id":"cac-auc-platform","customer_count_series_id":"cac-count-platform",
        "beginning_auc":0,"beginning_customers":0,"attrition_rate":0,"intra_year_shape":"linear",
        "customer_intra_year_shape":"linear",
        "channels":[{"name":"Client adds","method":"explicit",
                     "params":{"new_customers_by_year":[10,10],"spend":0},
                     "avg_auc_per_customer":1}]}
    platform_stream={
        "name":"Platform Integration & API access",
        "basis":"account",
        "driver":{"source":"customer_acquisition_count","ref":"cac-count-platform",
                  "measure":"annual_count","trajectory":"flat","params":{}},
        "rate":{"behavior":"flat","params":{"unit_fee":{"value":5000.0,"period":"year","trajectory":"flat"}}},
        "cost":{"kind":"none","params":{}},"timing":{"start_period":1}}
    def _platform_cfg(ppy):
        pc=json.load(open("foundry/fixtures/universal_template_bank.json"))
        pa=pc["assumptions"]; pa["periods_per_year"]=ppy; pa["n_periods"]=2*ppy; pa["capital_raises"]=[]
        pa["cac_feeds"]={"platform":copy.deepcopy(platform_feed)}
        pa["obs_exposures"]=[{"name":"Platform","_fee_product":True,
                              "fee_streams":[copy.deepcopy(platform_stream)]}]
        return pc
    pm=_platform_cfg(12); pq=_platform_cfg(4)
    bm=copy.deepcopy(pm); bq=copy.deepcopy(pq); bm["assumptions"]["obs_exposures"]=[]; bq["assumptions"]["obs_exposures"]=[]
    rm=run_q.run_v2(pm); rq=run_q.run_v2(pq); rbm=run_q.run_v2(bm); rbq=run_q.run_v2(bq)
    fm=[x-y for x,y in zip(rm["financials"]["is"]["fees"],rbm["financials"]["is"]["fees"])]
    fq=[x-y for x,y in zip(rq["financials"]["is"]["fees"],rbq["financials"]["is"]["fees"])]
    ck("CAC-count Account fee produces $50k in Year 1 and $100k in Year 2",
       _eq(sum(fm[:12]),50.0,.05) and _eq(sum(fm[12:24]),100.0,.05), fm)
    ck("CAC-count Account fee preserves annual economics across monthly and quarterly engines",
       _eq(sum(fq[:4]),50.0,.05) and _eq(sum(fq[4:8]),100.0,.05) and
       _eq(sum(fm[:12]),sum(fq[:4]),.05) and _eq(sum(fm[12:24]),sum(fq[4:8]),.05), fq)

    # The 38-client case that exposed r68's opacity: all three supported measures are explicit and
    # intentionally produce different economics while remaining cadence-stable.
    probe_feed={
        "series_id":"cac-auc-probe","customer_count_series_id":"cac-count-probe",
        "beginning_auc":0,"beginning_customers":0,"attrition_rate":0,
        "intra_year_shape":"linear","customer_intra_year_shape":"linear",
        "channels":[{"name":"Client adds","method":"explicit",
                     "params":{"new_customers_by_year":[38],"spend":0},
                     "avg_auc_per_customer":1}]}
    def _probe_cfg(ppy,measure):
        pc=json.load(open("foundry/fixtures/universal_template_bank.json"))
        pa=pc["assumptions"]; pa["periods_per_year"]=ppy; pa["n_periods"]=ppy; pa["capital_raises"]=[]
        pa["cac_feeds"]={"probe":copy.deepcopy(probe_feed)}
        st=copy.deepcopy(platform_stream); st["driver"]["ref"]="cac-count-probe"; st["driver"]["measure"]=measure
        pa["obs_exposures"]=[{"name":"Platform","_fee_product":True,"fee_streams":[st]}]
        return pc
    def _fee_delta(cfg):
        base=copy.deepcopy(cfg); base["assumptions"]["obs_exposures"]=[]
        r=run_q.run_v2(cfg); b=run_q.run_v2(base)
        return [x-y for x,y in zip(r["financials"]["is"]["fees"],b["financials"]["is"]["fees"])]
    am=_fee_delta(_probe_cfg(12,"annual_count")); aq=_fee_delta(_probe_cfg(4,"annual_count"))
    em=_fee_delta(_probe_cfg(12,"period_end")); eq=_fee_delta(_probe_cfg(4,"period_end"))
    xm=_fee_delta(_probe_cfg(12,"period_average")); xq=_fee_delta(_probe_cfg(4,"period_average"))
    ck("38-client annual-count fee applies all 38 clients to the full model-year price",
       _eq(am[0],15.83,.011) and _eq(sum(am),190.0,.05) and _eq(sum(aq),190.0,.05), am)
    ck("38-client monthly-EOP fee can intentionally ramp active clients through the year",
       _eq(em[0],1.32,.011) and _eq(sum(em),102.9166666667,.05)
       and _eq(sum(eq),sum(em),.05), em)
    ck("38-client period-average fee accrues on average active-client exposure",
       _eq(xm[0],.66,.011) and _eq(sum(xm),95.0,.05)
       and _eq(sum(xq),sum(xm),.05), xm)

    # AUC and active-client within-year shapes must be independently authorable.
    split=copy.deepcopy(probe_feed); split["intra_year_shape"]="linear"; split["customer_intra_year_shape"]="stepped"
    sr=cac_auc_rollforward(split,12,12)
    ck("CAC client timing is independent from AUC timing",
       _eq(sr["auc_end_by_month"][0],sr["year_end_auc"][0]/12.0)
       and _eq(sr["customer_end_by_month"][0],38.0)
       and sr["auc_end_by_month"][0] != sr["year_end_auc"][0])

    bad_shape=copy.deepcopy(probe_feed); bad_shape["customer_intra_year_shape"]="opaque"
    try: cac_auc_rollforward(bad_shape,12,12); bad_shape_raised=False
    except ValueError: bad_shape_raised=True
    ck("unsupported client within-year shape fails closed", bad_shape_raised)

    opening=copy.deepcopy(probe_feed); opening["beginning_customers"]=10
    orr=cac_auc_rollforward(opening,12,12)
    ck("period-average active clients retain the true opening customer book",
       _eq(orr["customer_average_by_period"][0],(10.0+orr["customer_end_by_month"][0])/2.0))

    # Saved r68 streams with no measure retain their old canonical-month EOP behavior.
    legacy_cfg=_probe_cfg(12,"period_end"); del legacy_cfg["assumptions"]["obs_exposures"][0]["fee_streams"][0]["driver"]["measure"]
    legacy=_fee_delta(legacy_cfg)
    ck("r68 CAC-count streams without measure preserve prior EOP-level economics",
       all(_eq(a,b,.0001) for a,b in zip(legacy,em)))

    print(f"\n{P} passed, {F} failed")
    return 0 if F == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
