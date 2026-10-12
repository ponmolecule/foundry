"""Monthly cohort identities, credit integration and opt-in compatibility."""
import copy,json,math
from .loan_balance import normalize_linked_loan_balance,resolve_linked_loan_balance
from .repayment_profiles import resolve,validate
from .run_q import run_v2
from .validate_q import validate_errors_v2

def product():
 return {'measurement':'amortized','name':'Profiled lending','call_report_line':'loanOther','balance_mode':'funded_flow_level','opening_balance':0,'runoff_per_period':0,'runoff_q':0,'charge_off_ann':0,'allowance_mode':'reserve_rate','reserve_rate_pct_bal':.01,'rate_type':'fixed','yield_ann':0,'opex_pct_ann':0,'funded_flow_driver':{'source':'entered','input_stage':'funded_volume','start_period':1,'ramp_periods':1,'take_up_share':1,'flow_path':{'unit_kind':'money_flow','trajectory':'flat','period':'month','value':1000}},'term_days':60,'day_count':360,'reserve_share':0,'target_retention_share':1,'interest_balance_measure':'period_end','repayment_profile':{'cadence':'month','funding_timing':'monthly_bucket','repayment_fractions':[0,0,1],'loss_basis':'annual_balance','loss_balance_measure':'period_begin','loss_rate_spec':{'source':'entered','trajectory':'flat','value':0},'opening_cohorts':[],'opening_distributed_cohorts':[]}}

def main():
 n=0
 def ck(label,ok):
  nonlocal n
  assert ok,label;n+=1;print('PASS',label)
 def rejected(label,p):
  try:r=go(p)
  except (ValueError,TypeError):ck(label,True);return
  raise AssertionError(label)
 def go(p,ppy=12,n=12,a=None):
  a=a or {};normalized=normalize_linked_loan_balance(p,a);return resolve(p,a,n,ppy,normalized)
 p=product();m=go(p);q=go(p,4,4)
 ck('launch balance uses actual funded cohorts, not two times current volume',m['ending_balance'][:3]==[1000,2000,2000])
 ck('repayment occurs at explicit cohort age',m['repayments'][:4]==[0,0,1000,1000])
 ck('quarter preserves monthly ending balances and sums flows',q['ending_balance']==[m['ending_balance'][i] for i in [2,5,8,11]] and q['repayments'][0]==1000)
 ck('quarter interest basis is average of monthly selected exposures',q['interest_basis'][0]==5000/3)
 ck('every cohort and monthly principal identity reconciles',all(abs(r['beginning']+r['funded']-r['charge_offs']-r['repayments']-r['ending'])<1e-8 for r in m['cohorts']))
 ck('fully extinguished cohort repays original principal exactly',sum(r['repayments']+r['charge_offs'] for r in m['cohorts'] if r['cohort']=='funded-1')==1000)
 p=product();p['repayment_profile']['loss_rate_spec']['value']=.12;m=go(p)
 ck('annual beginning balance loss does not charge launch purchases prematurely',m['charge_offs'][:3]==[0,10,19.9])
 ck('loss reduces the cohort and cannot also repay',math.isclose(m['repayments'][2],980.1) and m['ending_balance'][2]==1990)
 p['allowance_mode']='profile_expected_loss';m=go(p)
 ck('remaining allowance uses remaining profile losses',math.isclose(m['allowance'][0],19.9) and math.isclose(m['allowance'][1],29.8))
 ck('provision identity holds across monthly and quarterly endpoints',math.isclose(sum(m['charge_offs'][:3])+m['allowance'][2]-m['opening_allowance'],sum(go(p,4,4)['charge_offs'][:1])+go(p,4,4)['allowance'][0]-go(p,4,4)['opening_allowance']))
 p=product();p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']['value']=.04;p['allowance_mode']='profile_expected_loss';m=go(p)
 ck('lifetime funded-volume loss is recognized by entered age',m['charge_offs'][:3]==[0,40,40] and m['ending_balance'][:3]==[1000,1960,1960])
 ck('future cohort-volume losses appear in allowance',m['allowance'][:3]==[40,40,40])
 ck('completed cohort repayments plus losses equal funded principal',sum(r['repayments']+r['charge_offs'] for r in m['cohorts'] if r['cohort']=='funded-1')==1000)
 p=product();p['repayment_profile']['opening_cohorts']=[{'id':'opening-a','original_principal':1000,'outstanding':800,'repaid_to_date':190,'charged_off_to_date':10,'next_age_month':2}];p['opening_balance']=800;m=go(p)
 ck('explicit opening cohort runs off by its entered age',m['repayments'][0]==800 and m['ending_balance'][0]==1000)
 p['opening_balance']=700;rejected('reject mismatched opening cohort balance',p)
 p=product();p['repayment_profile']['repayment_fractions']=[0,.5];rejected('reject incomplete repayment curve',p)
 p=product();p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,0,0,1]);rejected('reject loss after exposure extinguishes',p)
 p=product();p['allowance_mode']='loss_rate_term';p['repayment_profile']['loss_rate_spec']['value']=.12;ck('remaining repayment exposure replaces fixed days in term allowance',math.isclose(go(p)['allowance'][0],20))
 p=product();p['allocation_group_id']='cap';rejected('direct single-product resolver requires simultaneous shared allocation',p)
 p=product();p['charge_off_ann']=.04;rejected('reject competing legacy loss rate',p)
 p=product();p['runoff_per_period']=.2;rejected('reject competing runoff',p)
 p=product();p['funded_flow_driver']['flow_path'].update(trajectory='explicit_schedule',schedule={str(i+1):1000+i*100 for i in range(12)});m=go(p);q=go(p,4,4)
 ck('growing monthly purchases remain exact in quarterly run',q['ending_balance'][0]==2300 and q['repayments'][0]==1000 and math.isclose(q['interest_basis'][0],(1000+2100+2300)/3))
 # Canonical linked source: subscriber count -> money per subscriber per month.
 from .tests_account_activity import feed,adoption,stream
 active=stream('Active','account','active')
 spend={'name':'Purchases','quantity_series_id':'purchases','basis':'transaction','driver':{'source':'stream_ref','ref':'Active','trajectory':'derived','params':{'coefficient':{'kind':'amount_per_source_unit','value':23000,'period':'month','trajectory':'flat'}}},'rate':{'behavior':'flat','params':{'per_unit':0,'pricing_basis':'pct_of_throughput'}},'cost':{'kind':'none','params':{}}}
 a={'cac_feeds':{'Feed':feed()},'account_adoption':[adoption()],'obs_exposures':[{'fee_streams':[active,spend]}]}
 p=product();p['funded_flow_driver']={'source':'fee_stream_quantity','series_id':'purchases','input_stage':'funded_volume','start_period':1,'ramp_periods':1,'take_up_share':1}
 m=go(p,a=a);q=go(p,4,4,a)
 ck('linked purchase source replays canonical monthly subscriber economics',m['funded_volume'][0]==606*23000 and q['ending_balance'][0]==(612+618)*23000)
 p=product();p['target_retention_share']=.75;m=go(p)
 ck('retained and distributed cohorts split funded principal',m['ending_balance'][:3]==[750,1500,1500] and m['distributed_balance'][:3]==[250,500,500])
 p=product();p['interest_balance_measure']='period_average';m=go(p);q=go(p,4,4)
 ck('average interest uses monthly endpoint observations at both cadences',math.isclose(q['interest_basis'][0],sum(m['interest_basis'][:3])/3))
 p=product();p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[.04,.08]+[.08]*10};m=go(p)
 ck('lifetime quote is locked at each funding cohort',m['charge_offs'][:3]==[0,40,80])
 p=product();p['repayment_profile']['loss_rate_spec']['value']=.12;p['_profile_loss_mult']=2;m=go(p)
 ck('stress multiplier applies to profiled losses',m['charge_offs'][1]==20)
 p=product();p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[1]);p['repayment_profile']['loss_rate_spec']['value']=1;p['_profile_loss_mult']=2;rejected('reject losses above available exposure without clipping',p)
 from .engine_q_a import run_pf_a
 fee_cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'));p=product();p['target_retention_share']=.75;p['yield_ann']=.12
 p['funded_flow_driver']['flow_path'].update(trajectory='explicit_schedule',schedule={str(i+1):1000+i*100 for i in range(12)})
 p['fee_streams']=[{'name':'Interchange','quantity_series_id':'interchange','basis':'transaction','driver':{'source':'product_funded_flow','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'pricing_basis':'pct_of_throughput','per_unit':.022}},'cost':{'kind':'pct_of_throughput_opex','params':{'pct':.0089}}},{'name':'Distributed','quantity_series_id':'distributed-fee','basis':'balance','driver':{'source':'distributed_balance','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'rate_path':{'trajectory':'flat','period':'year','value':.12}}},'cost':{'kind':'none','params':{}}}]
 fee_cfg['assumptions']['lending_products']=[p];fee_cfg['assumptions'].update(periods_per_year=12,n_periods=12)
 mr=run_pf_a(fee_cfg);quarter=copy.deepcopy(fee_cfg);quarter['assumptions'].update(periods_per_year=4,n_periods=4);qr=run_pf_a(quarter)
 mp=mr['products'][0];qp=qr['products'][0]
 ck('profile funded and distributed fees sum monthly economics',math.isclose(qp['fees'][0],86.1) and math.isclose(qp['fees'][0],sum(mp['fees'][:3])))
 ck('profile throughput costs post once at both cadences',math.isclose(qp['passCost'][0],3300*.0089) and math.isclose(qp['passCost'][0],sum(mp['passCost'][:3])))
 ck('profile interest uses canonical monthly balance observations',math.isclose(qp['intInc'][0],40.5) and math.isclose(qp['intInc'][0],sum(mp['intInc'][:3])))
 econ=qr['fee_stream_economics']['distributed-fee'];ck('profile balance fee quantity and factor reconcile audit',math.isclose(econ['quantity'][0]*econ['pricing_factor'][0]/4,econ['reported_fee_income'][0]))
 cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'));p=product();cfg['assumptions']['lending_products']=[p]
 ck('public configuration validates',not validate_errors_v2(cfg))
 r=run_v2(cfg);audit=r['repayment_profiles'][0]['profile'];ck('public engine emits cohort audit',audit['monthly'][0]['ending']==1000)
 ck('public reported repayments match cohort ledger',math.isclose(r['products'][0]['repayments'][0],1))
 ck('public provision equals charge-offs plus allowance change',math.isclose(r['financials']['is']['prov'][0],.02,abs_tol=1e-9))
 from .audit_workbook import calculation_audit_workbook
 wb=calculation_audit_workbook(cfg,r);ck('audit workbook exposes monthly and cohort repayment reconciliation',{'Repayment Monthly','Repayment Cohorts'}<=set(wb.sheetnames))
 print(n,'checks passed')
if __name__=='__main__':main()
