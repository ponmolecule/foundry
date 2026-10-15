"""Entered liability stocks: cadence, posting, audit and fail-closed validation."""
import copy
from .tests_other_liabilities import _cfg, _activate
from .other_liabilities import prepare_other_liabilities, other_liability_period, other_liability_audit_payload
from .engine_q_a import run_pf_a
from .audit_workbook import calculation_audit_workbook
from .validate_q import validate_errors_v2

def flat(v): return {'source':'entered','trajectory':'flat','value':v}
def main():
    a=_cfg()['assumptions'];_activate(a,12,6)
    a['other_liabilities_model']={'opening_balance':0,'base_spec':flat(25),'components':[{'component_id':'ap','name':'Accounts payable','terms':[{'term_id':'ap-level','driver_spec':{'source':'entered','trajectory':'explicit','cadence':'month','values':[0,0,777100,800000,900000,950000]},'multiplier_spec':flat(1)}]}]}
    p=prepare_other_liabilities(a,6,12)
    rows=[other_liability_period(p,i) for i in range(6)]
    assert [r['total'] for r in rows]==[25,25,777125,800025,900025,950025]
    q=prepare_other_liabilities(a,2,4)
    assert [other_liability_period(q,i)['total'] for i in range(2)]==[777125,950025], 'stock must use quarter end, not sum'
    payload=other_liability_audit_payload(p,[r['total'] for r in rows],rows)
    assert payload['components'][0]['terms'][0]['driver'][2]==777100
    cfg=_cfg();_activate(cfg['assumptions'],12,12);cfg['assumptions']['other_liabilities_model']=copy.deepcopy(a['other_liabilities_model'])
    assert not validate_errors_v2(cfg),validate_errors_v2(cfg)
    with_ap=run_pf_a(cfg)
    zero=copy.deepcopy(cfg);zero['assumptions']['other_liabilities_model']['components']=[]
    without=run_pf_a(zero)
    assert abs(with_ap['bs']['otherLiab'][3]-without['bs']['otherLiab'][3]-777100)<1e-6
    fund=lambda r:r['bs']['cash'][3]+r['bs']['sec'][3]-r['bs']['borrow'][3]
    assert fund(with_ap)>fund(without), "added liability must increase available funding"
    from .run_q import run_v2
    wb=calculation_audit_workbook(cfg,run_v2(cfg))
    audit_rows=list(wb['Other Liabilities'].values)
    assert any('$000s · entered liability level' in r for r in audit_rows)
    import io,openpyxl
    from .fiw import build_fiw,diff_import
    b,_=build_fiw(cfg);fw=openpyxl.load_workbook(io.BytesIO(b))
    assert any('Entered liability level' in str(r) for r in fw['ASSM_OTHER_LIAB'].values)
    bad=copy.deepcopy(a);bad['other_liabilities_model']['components'][0]['terms'][0]['driver_spec']=flat(-100)
    try:other_liability_period(prepare_other_liabilities(bad,6,12),0)
    except ValueError:pass
    else:raise AssertionError('negative aggregate liability must fail')
    print('PASS entered monthly stocks, quarter ends, audit operands, validation, cash posting and negative aggregate rejection')
if __name__=='__main__':main()
