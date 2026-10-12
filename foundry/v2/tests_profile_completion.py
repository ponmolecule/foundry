"""r317: cap transfers, curve-duration allowance, and replacement stress losses."""
import copy,json,math
from .tests_repayment_profiles import product
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import calculation_audit_workbook

def config(ppy=12):
 c=json.load(open('foundry/fixtures/core_bank_test_base.json'));a=c['assumptions'];a.update(periods_per_year=ppy,n_periods=12 if ppy==12 else 4)
 a['capital_raises']=[]
 p=product();p.update(allocation_group_id='pool',allocation_target_id='a',yield_ann=.12)
 a['lending_products']=[p];a['loan_allocation_groups']=[{'id':'pool','cap_source':'entered','cap_spec':{'source':'entered','trajectory':'flat','value':1500}}]
 return c

def main():
 count=0
 def ck(label,ok):
  nonlocal count
  assert ok,label;count+=1;print('PASS',label)
 def profile(r,i=0):return r['repayment_profiles'][i]['profile']
 c=config();ck('profile cap configuration validates',not validate_errors_v2(c));r=run_pf_a(copy.deepcopy(c));p=profile(r)
 ck('cap applies after repayment at each month end',p['ending_balance'][:3]==[1000,1500,1500])
 ck('cap transfers explicit principal instead of invented repayment',all(math.isclose(v,t,abs_tol=1e-8) for v,t in zip(p['transfers_out'][:3],[0,500,250])) and p['repayments'][2]==750)
 ck('seasoned cohort histories keep original principal',next(x for x in p['cohorts'] if x['cohort']=='funded-1' and x['month']==2)['original_principal']==1000)
 ck('all retained monthly identities include transfers',all(math.isclose(x['beginning']+x['funded']-x['charge_offs']-x['repayments']-x['transfers_out'],x['ending'],abs_tol=1e-8) for x in p['monthly']))
 ck('all distributed monthly identities include incoming transfers',all(math.isclose(x['distributed_beginning']+x['distributed_funded']+x['distributed_transfers_in']-x['distributed_repayments'],x['distributed'],abs_tol=1e-8) for x in p['monthly']))
 ck('every distributed cohort identity reconciles',all(math.isclose(x['beginning']+x['funded']+x['transfers_in']-x['repayments'],x['ending'],abs_tol=1e-8) for x in p['distributed_cohorts']))
 ck('fully extinguished retained cohort repays or transfers original exactly',math.isclose(sum(x['repayments']+x['charge_offs']+x['transfers_out'] for x in p['cohorts'] if x['cohort']=='funded-1'),1000))
 q=config(4);qr=run_pf_a(copy.deepcopy(q));qp=profile(qr)
 ck('quarterly cap uses exact monthly cohorts',all(math.isclose(qp['ending_balance'][i],p['ending_balance'][i*3+2]) for i in range(4)))
 ck('quarterly transfers sum monthly transfers',math.isclose(qp['transfers_out'][0],sum(p['transfers_out'][:3])))
 ck('quarterly capped interest sums monthly exposure',math.isclose(qr['products'][0]['intInc'][0],sum(r['products'][0]['intInc'][:3])))
 # Falling and then rising capacities: no reacquisition of previously sold cohorts.
 c=config();a=c['assumptions'];a['lending_products'][0]['funded_flow_driver']['flow_path'].update(trajectory='explicit_schedule',schedule={str(i+1):1000 if i==0 else 0 for i in range(12)})
 a['loan_allocation_groups'][0]['cap_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[1000,500,2000]+[2000]*9}
 p=profile(run_pf_a(c));ck('capacity fall transfers seasoned exposure and rising cap never buys it back',p['ending_balance'][:3]==[1000,500,0] and p['distributed_balance'][:3]==[0,500,0])
 # Simultaneous competition, independent of member order.
 c=config();a=c['assumptions'];b=copy.deepcopy(a['lending_products'][0]);b.update(name='Second',allocation_target_id='b');b['funded_flow_driver']['flow_path']['value']=500;a['lending_products'].append(b)
 r=run_pf_a(copy.deepcopy(c));reversed_c=copy.deepcopy(c);reversed_c['assumptions']['lending_products'].reverse();rr=run_pf_a(reversed_c)
 ck('shared cap competes pro rata without member-order dependence',all(math.isclose(x['bal'][i],next(y for y in rr['products'] if y['name']==x['name'])['bal'][i]) for x in r['products'] if x['family']=='lending' for i in range(13)))
 ck('multiple profiles never exceed group capacity',all(sum(x['ending_balance'][i] for x in [profile(r,0),profile(r,1)])<=1500+1e-8 for i in range(12)))
 # A legacy explicit-level member shares the same capacity.
 c=config();b=product();b.pop('repayment_profile');b.update(name='Legacy level',balance_mode='explicit_level',ending_balance_spec={'source':'entered','trajectory':'flat','value':500},allocation_group_id='pool',allocation_target_id='b');c['assumptions']['lending_products'].append(b)
 r=run_pf_a(copy.deepcopy(c));ck('mixed level and profile books share closing capacity',all(sum(x['bal'][i] for x in r['products'] if x['family']=='lending')<=1500+1e-8 for i in range(1,13)))
 # Deposit-based caps at both cadences, natural monthly level source.
 c=config();a=c['assumptions'];dep=copy.deepcopy(a['deposit_products'][0]);dep.update(balance_mode='level',ending_balance_spec={'source':'entered','trajectory':'explicit','cadence':'quarter','values':[1000,1200,1400,1500]},avg_maturity_m=0)
 for k in ('growth_q','growth_per_period','runoff_q','runoff_per_period','new_deposits_q','new_deposits_per_period'):dep[k]=0
 dep['overrides']={};a['deposit_products']=[dep];a['loan_allocation_groups'][0]={'id':'pool','cap_source':'deposit_book_end','cap_ratio':1}
 r=run_pf_a(copy.deepcopy(c));q=copy.deepcopy(c);q['assumptions'].update(periods_per_year=4,n_periods=4);qr=run_pf_a(q)
 ck('quarterly deposit closing target is explicitly held within the period',qr['loan_allocation_groups']['pool']['monthly'][0]['cap']==1000 and qr['loan_allocation_groups']['pool']['monthly'][1]['cap']==1000)
 ck('deposit cap quarterly retained balance matches monthly projection',math.isclose(profile(qr)['ending_balance'][0],profile(r)['ending_balance'][2]))
 # Curve-duration allowance annual rate, and lifetime loss remaining age curve.
 from .loan_balance import normalize_linked_loan_balance
 from .repayment_profiles import resolve
 p=product();p['allowance_mode']='loss_rate_term';p['repayment_profile']['loss_rate_spec']['value']=.12
 pr=resolve(p,{},12,12,normalize_linked_loan_balance(p,{}));ck('annual term allowance uses two remaining balance-months',math.isclose(pr['allowance'][0],20))
 p['repayment_profile']['repayment_fractions']=[0,.5,.5];pr=resolve(p,{},12,12,normalize_linked_loan_balance(p,{}));ck('partial repayments reduce allowance remaining exposure',math.isclose(pr['allowance'][0],15))
 p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']['value']=.04;pr=resolve(p,{},12,12,normalize_linked_loan_balance(p,{}));ck('lifetime quote allowance uses remaining age losses, not annualized lifetime quote',math.isclose(pr['allowance'][0],40))
 # Absolute stress losses replace, not add to, the lifetime quote within the window.
 c=config();p=c['assumptions']['lending_products'][0];p['allowance_mode']='profile_expected_loss';p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']['value']=.04
 c['scenario_overlays']={'dfast_severe_rates':{'loanOther':.27},'dfast_spread':'level'}
 r=run_pf_a(copy.deepcopy(c));pr=profile(r);row=next(x for x in pr['cohorts'] if x['cohort']=='funded-1' and x['month']==2)
 ck('lifetime profile accepts an absolute DFAST balance overlay',math.isclose(row['charge_offs'],10))
 ck('stress replacement audit states balance loss denominator and exposure',row['loss_treatment']=='stress_balance_replacement' and row['loss_denominator']==12 and row['loss_exposure']==1000 and math.isclose(row['loss_rate'],.12))
 ck('stress provision and cap identities reconcile',all(math.isclose(x['beginning']+x['funded']-x['charge_offs']-x['repayments']-x['transfers_out'],x['ending'],abs_tol=1e-8) for x in pr['monthly']))
 c=config();pub=run_v2(c);ck('public principal transfers use $000s',pub['products'][0]['detailExact']['principalTransfersOut'][1]==.5)
 wb=calculation_audit_workbook(c,pub);ck('audit shows bank and distributed transfer ledgers',{'Repayment Monthly','Repayment Cohorts','Distributed Cohorts','Profile Cap Monthly'}<=set(wb.sheetnames))
 ck('public cap monthly factors remain raw shares',pub['loan_allocation_groups']['pool']['monthly'][1]['factor']==.75)
 # Monthly entered capacity remains monthly in a quarterly model.
 c=config(4);c['assumptions']['loan_allocation_groups'][0]['cap_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[1000,500,2000]+[2000]*9}
 ck('monthly capacity path validates under quarterly profiles',not validate_errors_v2(c))
 r=run_pf_a(c);ck('quarterly model honors each monthly capacity value',r['loan_allocation_groups']['pool']['monthly'][1]['cap']==500 and profile(r)['ending_balance'][0]<=2000)
 c=config(4);c['assumptions']['loan_allocation_groups'][0]['cap_spec']={'source':'entered','trajectory':'explicit','cadence':'model_period','values':[1000,2000,3000,4000]}
 r=run_pf_a(c);ck('model-period capacity has explicit hold-within-period semantics',r['loan_allocation_groups']['pool']['monthly'][2]['cap']==1000 and r['loan_allocation_groups']['pool']['monthly'][3]['cap']==2000)
 # Ownership transfers also transfer the future lifetime-loss principal share.
 c=config();a=c['assumptions'];a['loan_allocation_groups'][0]['cap_spec']['value']=500;p=a['lending_products'][0];p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']['value']=.04;p['allowance_mode']='profile_expected_loss'
 r=run_pf_a(c);pr=profile(r);row=next(x for x in pr['cohorts'] if x['month']==2 and x['cohort']=='funded-1')
 ck('transferred original-principal share has no future bank lifetime loss',row['loss_exposure']==500 and row['charge_offs']==20)
 ck('allowance releases the transferred share of expected loss',pr['allowance'][0]==20)
 # Imported seasoned holdings can carry historical transfers explicitly.
 p=product();p['opening_balance']=500;p['repayment_profile'].update(loss_basis='cohort_volume',loss_timing_fractions=[0,1]);p['repayment_profile']['loss_rate_spec']['value']=.04;p['repayment_profile']['opening_cohorts']=[{'id':'seasoned','original_principal':1000,'outstanding':500,'repaid_to_date':0,'charged_off_to_date':0,'transferred_to_date':500,'next_age_month':1,'loss_rate_at_funding':.04,'loss_principal_at_opening':500}]
 pr=resolve(p,{},12,12,normalize_linked_loan_balance(p,{}));ck('opening transfer history and retained loss principal reconcile',pr['charge_offs'][0]==20)
 del p['repayment_profile']['opening_cohorts'][0]['loss_principal_at_opening']
 try:normalize_linked_loan_balance(p,{})
 except ValueError:ck('historical transfers cannot silently infer a lifetime-loss share',True)
 else:raise AssertionError('missing retained loss principal')
 # Par transfer changes liquid funding availability, not income at the sale price.
 c=config();p=c['assumptions']['lending_products'][0];p.update(yield_ann=0,reserve_rate_pct_bal=0);a=c['assumptions'];a['securities_yield']=0;a['cash_yield']=0
 r=run_pf_a(copy.deepcopy(c));uncapped=copy.deepcopy(c);uncapped['assumptions']['lending_products'][0].pop('allocation_group_id');uncapped['assumptions']['loan_allocation_groups']=[];ur=run_pf_a(uncapped)
 ck('principal transferred at par creates no gain on sale',r['products'][0]['gos'][1]==ur['products'][0]['gos'][1]==0)
 ck('transfer releases principal into liquid funding assets',math.isclose((r['bs']['cash'][2]+r['bs']['sec'][2])-(ur['bs']['cash'][2]+ur['bs']['sec'][2]),500,abs_tol=1e-5))
 # Rate-replacement stress must revert to each cohort's own lifetime quote after its window.
 p=product();p['repayment_profile'].update(loss_basis='cohort_volume',repayment_fractions=[0,0,0,1],loss_timing_fractions=[0,.5,.5]);p['repayment_profile']['loss_rate_spec']['value']=.04;p['_profile_loss_overrides']={'1':.12}
 pr=resolve(p,{},12,12,normalize_linked_loan_balance(p,{}));ck('lifetime loss schedule resumes after the explicit stress replacement window',pr['charge_offs'][1]==20 and pr['charge_offs'][2]==40)
 # Zero and very large capacities exercise identity boundary cases.
 c=config();c['assumptions']['loan_allocation_groups'][0]['cap_spec']['value']=0;pr=profile(run_pf_a(c));ck('zero cap transfers exposure with no spurious repayment',pr['ending_balance']==[0]*12 and pr['transfers_out']==[1000]*12 and pr['repayments']==[0]*12)
 c=config();c['assumptions']['loan_allocation_groups'][0]['cap_spec']['value']=1e12;pr=profile(run_pf_a(c));ck('nonbinding cap reproduces ordinary cohort balances',pr['ending_balance'][:3]==[1000,2000,2000] and pr['transfers_out']==[0]*12)
 # Invalid inputs remain rejected; no numeric clipping is used to force a reconciliation.
 c=config();c['assumptions']['loan_allocation_groups'][0]['cap_spec']['value']=-1
 ck('negative profiled capacity is rejected',bool(validate_errors_v2(c)))
 from .fiw import build_fiw,diff_import
 c=config();c['assumptions']['nie_detail']['gross_up_eligibility']={'fee_costs':True,'fdic':False};c['assumptions']['lending_products'][0]['opex_gross_up_eligible']=False
 data,_=build_fiw(c);merged,_=diff_import(data,copy.deepcopy(c));ck('combined profile/cap/gross-up workbook round trip preserves full configuration',merged==c)
 print(count,'checks passed')
if __name__=='__main__':main()
