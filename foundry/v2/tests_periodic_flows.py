"""Golden contract for Configuration recurring-flow natural-period semantics.
Run: python3 -m foundry.v2.tests_periodic_flows
"""
import sys, json
sys.path.insert(0, ".")

from foundry.v2.periodic_flows import resolve_periodic_flow
from foundry.v2.income_modules import nie_category_series, simple_overhead_series
from foundry.v2.engine_q_a import run_pf_a


def _annual(arr, ppy):
    return [sum(arr[i:i+ppy]) for i in range(0, len(arr), ppy)]


def main():
    P = F = 0
    def ck(name, cond):
        nonlocal P, F
        if cond:
            P += 1; print(f"  PASS  {name}")
        else:
            F += 1; print(f"  FAIL  {name}")

    flat_y = {"trajectory":"flat","value":360_000,"period":"year"}
    flat_q = {"trajectory":"flat","value":90_000,"period":"quarter"}
    flat_m = {"trajectory":"flat","value":30_000,"period":"month"}
    for ppy, n in ((12,24),(4,8)):
        y = resolve_periodic_flow(flat_y,n,ppy)
        q = resolve_periodic_flow(flat_q,n,ppy)
        m = resolve_periodic_flow(flat_m,n,ppy)
        ck(f"flat 360/year == 90/quarter == 30/month at ppy={ppy}", y == q == m)
        ck(f"flat annual totals stay 360 at ppy={ppy}", all(abs(v-360_000)<1e-8 for v in _annual(y,ppy)))

    gs_step={"rate":.03,"period":"year","method":"step","anchor":"model_year"}
    specs_step=[{"trajectory":"growth","value":360_000,"period":"year","growth_spec":gs_step},
                {"trajectory":"growth","value":90_000,"period":"quarter","growth_spec":gs_step},
                {"trajectory":"growth","value":30_000,"period":"month","growth_spec":gs_step}]
    msets=[resolve_periodic_flow(s,24,12) for s in specs_step]
    qsets=[resolve_periodic_flow(s,8,4) for s in specs_step]
    ck("step natural-unit variants are identical in monthly engine", msets[0]==msets[1]==msets[2])
    ck("step natural-unit variants are identical in quarterly engine", qsets[0]==qsets[1]==qsets[2])
    exp=[360_000,370_800]
    ck("step annual totals are Y1 360 / Y2 370.8", all(abs(a-b)<1e-8 for a,b in zip(_annual(msets[0],12),exp)))
    ck("step monthly and quarterly engines preserve same annual economics", all(abs(a-b)<1e-8 for a,b in zip(_annual(msets[0],12),_annual(qsets[0],4))))

    gs_smooth={"rate":.03,"period":"year","method":"smooth","anchor":"model_year"}
    sm_y={"trajectory":"growth","value":360_000,"period":"year","growth_spec":gs_smooth}
    sm_m={"trajectory":"growth","value":30_000,"period":"month","growth_spec":gs_smooth}
    sm12=resolve_periodic_flow(sm_y,24,12); sm4=resolve_periodic_flow(sm_y,8,4)
    ck("smooth 360/year == 30/month", sm12==resolve_periodic_flow(sm_m,24,12))
    ck("smooth monthly/quarterly engines have identical annual totals",
       all(abs(a-b)<1e-8 for a,b in zip(_annual(sm12,12),_annual(sm4,4))))
    ck("smooth quarterly periods are sums of the canonical monthly path",
       all(abs(sm4[i]-sum(sm12[i*3:i*3+3]))<1e-8 for i in range(8)))

    ann_vals=[360_000,370_800]
    q_vals=[90_000]*4+[92_700]*4
    m_vals=[30_000]*12+[30_900]*12
    ex_y={"trajectory":"explicit","period":"year","values":ann_vals}
    ex_q={"trajectory":"explicit","period":"quarter","values":q_vals}
    ex_m={"trajectory":"explicit","period":"month","values":m_vals}
    for ppy,n in ((12,24),(4,8)):
        a=resolve_periodic_flow(ex_y,n,ppy); b=resolve_periodic_flow(ex_q,n,ppy); c=resolve_periodic_flow(ex_m,n,ppy)
        ck(f"explicit annual/quarter/month flow schedules reconcile at ppy={ppy}", a==b==c)

    # Opex periodic-flow authoring owns amount/period/growth only. Timing belongs to the
    # separate recognition contract; the short-lived r60 start_period axis is intentionally ignored.
    no_start_axis=resolve_periodic_flow({"trajectory":"flat","value":120_000,"period":"year","start_period":35},12,12)
    ck("periodic-flow resolver does not carry a separate Opex commencement axis",
       no_start_axis==[10_000.0]*12)

    # Legacy fallback remains exact: no flow_spec means native-engine-period semantics.
    legacy={"per_period":30_000,"trajectory":"growth","growth_spec":gs_step}
    lg=nie_category_series(legacy,24,12)
    ck("legacy NIE per_period contract remains exact when flow_spec absent",
       lg[:12]==[30_000]*12 and lg[12:]==[30_900]*12)
    new={"flow_spec":{"trajectory":"growth","value":360_000,"period":"year","growth_spec":gs_step}}
    ck("new NIE flow_spec reproduces intended legacy monthly economics", nie_category_series(new,24,12)==lg)

    legacy_a={"overhead_per_period":30_000,"overhead_growth_spec":gs_step}
    new_a={"overhead_flow_spec":{"trajectory":"growth","value":360_000,"period":"year","growth_spec":gs_step}}
    ck("simple overhead new annual flow reproduces legacy monthly 30k path",
       simple_overhead_series(legacy_a,24,12)==simple_overhead_series(new_a,24,12))

    # Full engine integration: one authored annual Opex assumption must produce the same
    # annual economics under monthly and quarterly computational cadence.
    def _engine(ppy, detailed=True):
        c=json.load(open("foundry/fixtures/universal_template_bank.json"))
        a=c["assumptions"]; a["periods_per_year"]=ppy; a["n_periods"]=2*ppy
        a["premises_equipment"]=0; a["premises_depreciation_annual"]=0; a.pop("fixed_assets",None)
        fs={"trajectory":"growth","value":360_000,"period":"year","growth_spec":gs_step}
        if detailed:
            a["nie_detail"]={"categories":[{"name":"BD","flow_spec":fs}],
                             "other_gross_up_rate":0,"fdic_bp_ann":0,"occ_bp_ann":0,
                             "workforce":{"mode":"roles","roles":[]}}
            a.pop("overhead_flow_spec",None)
        else:
            a.pop("nie_detail",None); a["overhead_flow_spec"]=fs
        return run_pf_a(c)["is"]
    em=_engine(12,True); eq=_engine(4,True)
    ck("full engine detailed Opex preserves Y1/Y2 economics across cadence",
       all(abs(x-y)<1e-6 for x,y in zip(_annual(em["otherOpex"],12),_annual(eq["otherOpex"],4)))
       and all(abs(x-y)<1e-6 for x,y in zip(_annual(em["otherOpex"],12),[360_000,370_800])))
    smi=_engine(12,False); sqi=_engine(4,False)
    ck("full engine simple Opex preserves Y1/Y2 economics across cadence",
       all(abs(x-y)<1e-6 for x,y in zip(_annual(smi["overhead"],12),_annual(sqi["overhead"],4)))
       and all(abs(x-y)<1e-6 for x,y in zip(_annual(smi["overhead"],12),[360_000,370_800])))

    bad=False
    try:
        resolve_periodic_flow({"trajectory":"flat","value":1,"period":"week"},12,12)
    except ValueError:
        bad=True
    ck("unsupported natural period fails closed", bad)

    print(f"\n{P} passed, {F} failed")
    return 0 if F==0 else 1

if __name__ == "__main__":
    sys.exit(main())
