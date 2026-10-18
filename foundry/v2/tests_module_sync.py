"""Authoring module sync retains OBS fees alongside deposit-free lending."""
import copy,json,subprocess
from pathlib import Path
from .tests_portfolio_paydowns import setup
from .tests_fee_quantity_links import source
from .validate_q import validate_errors_v2
from .run_q import run_v2

def sync(cfg):
    html=Path('web/console_v2.html').read_text();a=html.index('function syncModules(){');b=html.index('\n}',a)+2
    js='let cfg='+json.dumps(cfg)+';\n'+html[a:b]+'\nsyncModules();console.log(JSON.stringify(cfg));'
    return json.loads(subprocess.check_output(['node'],input=js,text=True))

def main():
    cfg,_=setup();a=cfg['assumptions'];a['deposit_products']=[]
    st=source('purchases',[100000]*36,price=.022)
    a['obs_exposures']=[{'name':'Independent fee product','_fee_product':True,'fee_streams':[st]}]
    p=a['lending_products'][0];p['fee_streams']=[];p['fee_yield_ann']=0;p['yield_ann']=0
    p['funded_flow_driver']={'source':'fee_stream_quantity','series_id':'purchases','input_stage':'funded_volume','start_period':1}
    cfg['step_0']['modules']=['balance_driven_lending']
    assert any('no funding or fee side' in x['message'] for x in validate_errors_v2(copy.deepcopy(cfg)))
    fixed=sync(cfg);assert set(fixed['step_0']['modules'])=={'balance_driven_lending','balance_driven_obs'}
    assert not validate_errors_v2(copy.deepcopy(fixed)),validate_errors_v2(copy.deepcopy(fixed))
    result=run_v2(fixed);assert result['fee_stream_quantities']['series']['purchases']
    assert fixed['assumptions']==cfg['assumptions']
    fee_only=copy.deepcopy(fixed);fee_only['assumptions']['lending_products']=[];fee_only['assumptions']['nie_detail']={'enabled':False};assert sync(fee_only)['step_0']['modules']==['balance_driven_obs']
    empty=copy.deepcopy(fee_only);empty['assumptions']['obs_exposures']=[];assert sync(empty)['step_0']['modules']==[]
    lending_only=copy.deepcopy(cfg);lending_only['assumptions']['obs_exposures']=[]
    assert 'balance_driven_obs' not in sync(lending_only)['step_0']['modules']
    print('PASS module sync: reproduces funding gate, deposit-free linked lending + separate fees runs with quantities, fee-only/empty/removal, authored assumptions preserved')
if __name__=='__main__':main()
