"""Stream display order does not alter dependency evaluation or economic results."""
import copy,itertools
from .tests_fee_quantity_links import fixture,source,linked,product
from .run_q import run_v2

def economic_output(r):
    return {'financials':r['financials'],'ratios':r.get('ratios'),'products':{p['name']:p for p in r['products']},'quantities':r.get('fee_stream_quantities',{}).get('series',{})}

def test_reorder():
    for external in (False,True):
        c=fixture();root=source();middle=linked('migration','tpv',.5);last=linked('final','migration',.2)
        if not external:
            middle['driver']['source']='stream_ref';middle['driver']['ref']='TPV';middle['name']='Migration';last['driver']['source']='stream_ref';last['driver']['ref']='Migration'
        c['assumptions']['obs_exposures']=[product('Activity',[root,middle,last])]
        baseline=economic_output(run_v2(c))
        for order in itertools.permutations(range(3)):
            moved=copy.deepcopy(c);moved['assumptions']['obs_exposures'][0]['fee_streams']=[copy.deepcopy([root,middle,last][i]) for i in order]
            assert economic_output(run_v2(moved))==baseline,(external,order)
    print('PASS all six stream orders retain exact financials, ratios, product results and quantities for named and stable-ID dependencies')

if __name__=='__main__':test_reorder()
