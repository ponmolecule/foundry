"""r440: a funded-flow distributed_balance fee is rejected by the validator unless the product publishes a distributed
balance (allocation group or repayment profile), so a config the validator accepts can always run."""
import copy,json
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .tests_repayment_profiles import product

FEE={'name':'Distributed','quantity_series_id':'distributed-fee','basis':'balance','driver':{'source':'distributed_balance','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'rate_path':{'trajectory':'flat','period':'year','value':.12}}},'cost':{'kind':'none','params':{}}}

def cfg_with(p):
 c=json.load(open('foundry/fixtures/core_bank_test_base.json'));c['assumptions']['lending_products']=[p];return c

def main():
 n=0
 def ck(label,ok):
  nonlocal n
  assert ok,label;n+=1;print('PASS',label)
 p=product();p['target_retention_share']=.75;p['fee_streams']=[copy.deepcopy(FEE)]
 c=cfg_with(p);ck('profiled funded-flow product with a distributed fee validates',not validate_errors_v2(c))
 r=run_v2(c);ck('and runs, earning the distributed fee',sum(r['products'][0]['fees'])>0)
 q=copy.deepcopy(p);q.pop('repayment_profile');c=cfg_with(q);errs=validate_errors_v2(c)
 ck('without a repayment profile it is rejected before the engine runs',any('distributed_balance requires an allocation group or a repayment profile' in str(e) for e in errs))
 print(n,'checks passed')
if __name__=='__main__':main()
