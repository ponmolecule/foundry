"""Opt-in monthly purchase cohorts with explicit loss and repayment conventions.

Curve entries are scheduled repayment fractions of original principal, age 0 =
the funding month. Actual repayments apply the implied conditional paydown to
surviving principal, so charge-offs never also repay.
"""
import math,copy

def number(v,label):
    try:x=float(v)
    except (TypeError,ValueError):raise ValueError(label+' must be numeric')
    if not math.isfinite(x) or x<0:raise ValueError(label+' must be finite and nonnegative')
    return x

def validate(p, a=None):
    profile=p.get('repayment_profile')
    if profile is None:return None
    if not isinstance(profile,dict) or profile.get('cadence')!='month':raise ValueError('Repayment profile requires explicit monthly cadence')
    allowed={'cadence','funding_timing','repayment_fractions','loss_basis','loss_balance_measure','loss_rate_spec','opening_cohorts','opening_distributed_cohorts','loss_timing_fractions','legacy_settings','name','memo'}
    if set(profile)-allowed:raise ValueError('Unsupported repayment profile settings: '+', '.join(sorted(set(profile)-allowed)))
    if number(p.get('reserve_rate_pct_bal',0),'Reserve share')>1:raise ValueError('Reserve share must be within 0–100%')
    curve=profile.get('repayment_fractions')
    if not isinstance(curve,list) or not curve:raise ValueError('Enter a monthly repayment curve, age 0 = funding month')
    curve=[number(x,'Repayment fraction') for x in curve]
    if any(x>1 for x in curve) or abs(sum(curve)-1)>1e-9:raise ValueError('Repayment fractions must sum to 100%')
    if len(curve)>360:raise ValueError('Repayment profile is limited to 360 monthly ages')
    if profile.get('funding_timing')!='monthly_bucket':raise ValueError('Select monthly_bucket explicitly; within-month repayment is supplied by the age-0 fraction')
    if profile.get('loss_basis') not in {'annual_balance','cohort_volume'}:raise ValueError('Select annual balance loss or lifetime funded-volume loss explicitly')
    if profile.get('loss_balance_measure') not in {'period_begin','balance_plus_funding'}:raise ValueError('Select the monthly loss balance measure explicitly')
    if profile.get('loss_basis')=='cohort_volume':
        timing=profile.get('loss_timing_fractions')
        if not isinstance(timing,list) or not timing:raise ValueError('Cohort-volume loss requires an explicit monthly loss timing curve')
        timing=[number(x,'Loss timing fraction') for x in timing]
        if abs(sum(timing)-1)>1e-9:raise ValueError('Loss timing fractions must sum to 100%')
        paid=0.
        for age,f in enumerate(timing):
            if f and paid>=1-1e-12:raise ValueError('Loss timing cannot occur after scheduled exposure is fully repaid')
            if age<len(curve):paid+=curve[age]
    if not isinstance(profile.get('loss_rate_spec'),dict) or profile['loss_rate_spec'].get('source','entered')!='entered':raise ValueError('Repayment profiles require an explicit entered loss-rate path')
    for key in ('opening_cohorts','opening_distributed_cohorts'):
        if not isinstance(profile.get(key),list):raise ValueError('Repayment profiles require explicit '+key+' (use an empty list for zero opening exposure)')
        ids=[]
        for row in profile[key]:
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip():raise ValueError('Opening cohorts require stable IDs')
            if str(row['id']).startswith(('funded-','distributed-')):raise ValueError('Opening cohort IDs cannot use generated funding prefixes')
            ids.append(row['id']);age=row.get('next_age_month')
            if isinstance(age,bool) or not isinstance(age,int) or not 0<=age<len(curve):raise ValueError('Opening cohort next age must be within the repayment curve')
            orig=number(row.get('original_principal'),'Opening original principal');bal=number(row.get('outstanding'),'Opening outstanding');paid=number(row.get('repaid_to_date'),'Opening repayments');loss=number(row.get('charged_off_to_date'),'Opening charge-offs')
            if abs(orig-bal-paid-loss)>1e-7*max(1,orig):raise ValueError('Opening cohort principal must equal repayments + charge-offs + outstanding')
            if key=='opening_cohorts' and profile['loss_basis']=='cohort_volume':
                if number(row.get('loss_rate_at_funding'),'Opening cohort loss rate')>1:raise ValueError('Opening cohort loss rate must be within 0–100%')
            if key=='opening_distributed_cohorts' and loss:raise ValueError('Distributed cohort credit losses are not modeled by this bank')
        if len(ids)!=len(set(ids)):raise ValueError('Opening cohort IDs must be unique')
    opening=sum(number(x['outstanding'],'Opening outstanding') for x in profile['opening_cohorts'])
    if abs(opening-float(p.get('opening_balance') or 0))>1e-7*max(1,opening):raise ValueError('Opening loan balance must equal explicit opening cohort outstanding')
    if p.get('balance_mode')!='funded_flow_level':raise ValueError('Repayment profiles require a funded-flow lending balance')
    if p.get('allocation_group_id'):raise ValueError('Repayment profiles cannot yet be combined with shared balance caps; use the existing average-days method or remove the cap')
    if p.get('allowance_mode','reserve_rate') not in {'reserve_rate','profile_expected_loss'}:raise ValueError('Profiled balances require reserve share or remaining profile expected loss; loss_rate_term is unsupported')
    if float(p.get('charge_off_ann') or 0)!=0 or any(float(v or 0)!=0 for v in ((p.get('overrides') or {}).get('charge_off_ann') or {}).values()):raise ValueError('Profile loss path replaces legacy charge_off_ann; set the legacy rate and overrides to zero')
    if float(p.get('runoff_per_period') or p.get('runoff_q') or 0)!=0:raise ValueError('Repayment curve replaces legacy runoff; set runoff to zero')
    if p.get('measurement')=='fair_value':raise ValueError('Repayment profiles currently support amortized-cost loans only')
    if a is not None:
        for group in a.get('loan_allocation_groups') or []:
            if p.get('allocation_target_id') in (group.get('members') or []):raise ValueError('Repayment profiles cannot join a shared balance cap')
    return profile

def monthly_sources(a,n,ppy,context=None):
    from .account_activity import resolve
    from .cac_feeder import cac_auc_rollforward
    activity,_=resolve(a,n,ppy,context);counts={};months=n*(12//ppy)
    for feed in (a.get('cac_feeds') or {}).values():
        sid=feed.get('customer_count_series_id')
        if not sid:continue
        r=cac_auc_rollforward(feed,n,ppy,assumptions=a,growth_context=context)
        counts[sid]={'period_end':r['customer_end_by_month'][:months],'period_average':r['customer_average_by_month'][:months],'annual_count':r['customer_annual_count_by_month'][:months]}
    return activity,counts

def canonical_flow(p,a,n,ppy,context=None):
    """Resolve one source on the monthly graph, never divide a quarterly total silently."""
    fd=p['funded_flow_driver'];months=n*(12//ppy)
    from .income_modules import _fee_entered_flow_value,fee_stream_q
    if fd['source']=='entered':return [_fee_entered_flow_value(fd['flow_path'],m+1,12,{'growth_context':context}) for m in range(months)]
    from .account_activity import monthly_fee
    products=[pr for k in ('obs_exposures','deposit_products','lending_products') for pr in a.get(k) or []]
    defs={s.get('quantity_series_id'):s for pr in products for s in pr.get('fee_streams') or [] if s.get('quantity_series_id')}
    owners={s.get('quantity_series_id'):pr.get('fee_streams') or [] for pr in products for s in pr.get('fee_streams') or [] if s.get('quantity_series_id')}
    st=defs.get(fd.get('series_id'))
    if st is None:raise ValueError('Repayment profile monthly funding source is missing')
    activity,counts=monthly_sources(a,n,ppy,context)
    out=[]
    for m in range(months):
        qty={};ctx={'growth_context':context,'linked_stream_defs':defs,'stream_defs':{s.get('name'):s for s in owners[st['quantity_series_id']]},'activity_stream_owners':owners,'account_activity':activity,'cac_monthly_counts':counts,'capture_stream_qty':qty}
        monthly_fee(st,m+1,ctx,12,fee_stream_q,force=True)
        arr=qty.get(st['quantity_series_id']) or []
        if len(arr)<=m:raise ValueError('Repayment profile source has no canonical monthly monetary quantity')
        out.append(number(arr[m],'Monthly funded activity'))
    return out

def resolve(p,a,n,ppy,linked,context=None):
    profile=validate(p,a)
    if profile is None:return None
    months=n*(12//ppy);width=12//ppy;curve=profile['repayment_fractions'];cum=[];total=0.
    for x in curve:cum.append(total);total+=x
    from .series import resolve_entered_series
    rates=resolve_entered_series(profile['loss_rate_spec'],months,12,context=context)
    rates=[number(v,'Profile loss rate') for v in rates]
    if any(v>1 for v in rates):raise ValueError('Profile loss rates must be within 0–100%')
    factors=resolve_entered_series(p['credit_loss_factor_spec'],months,12,context=context) if p.get('credit_loss_factor_spec') else [1.]*months
    factors=[number(v,'Credit loss factor') for v in factors]
    rates=[float((p.get('_profile_loss_overrides') or {}).get(str(m//width+1),v))*float(p.get('_profile_loss_mult',1)) for m,v in enumerate(rates)]
    inputs=[v*float(p.get('_profile_volume_mult',1)) for v in canonical_flow(p,a,n,ppy,context)]
    fd=p['funded_flow_driver'];funded=[]
    for m,v in enumerate(inputs):
        q=m//width+1
        if linked['input_stage']=='funded_volume':
            if q<linked['start_period'] and abs(v)>1e-9:raise ValueError('Final funded volume is nonzero before the configured start')
            funded.append(v)
        else:funded.append(v*linked['take_up_share']*(0 if q<linked['start_period'] else min(1,(q-linked['start_period']+1)/linked['ramp_periods'])))
    cohorts=[];distributed=[]
    def opening(rows):
        return [dict(id=x['id'],original=float(x['original_principal']),balance=float(x['outstanding']),age=x['next_age_month'],loss_rate=float(x.get('loss_rate_at_funding',0))*float(p.get('_profile_loss_mult',1))) for x in rows]
    cohorts=opening(profile['opening_cohorts']);distributed=opening(profile['opening_distributed_cohorts'])
    def step(c,rate,factor, *, new=False, loss=True):
        age=c['age'];beg=c['balance'];orig=c['original']
        if age>=len(curve):
            if beg>1e-7:raise ValueError('Exposure remains after the entered repayment horizon')
            return 0.,0.,0.
        co=0.
        if loss:
            if profile['loss_basis']=='cohort_volume':
                timing=profile['loss_timing_fractions'];co=orig*float(c['loss_rate'])*factor*(timing[age] if age<len(timing) else 0.)
            else:co=(0. if new and profile['loss_balance_measure']=='period_begin' else beg)*rate*factor/12.
        if co>beg+1e-8:raise ValueError('Profile charge-offs exceed available cohort exposure')
        remaining=beg-co;pay=remaining*(curve[age]/(1-cum[age]) if cum[age]<1-1e-12 else 0.)
        end=remaining-pay
        if end<-1e-7:raise ValueError('Profile repayments exceed available exposure')
        return co,pay,max(0.,end)
    def expected(c,m):
        cp=copy.deepcopy(c);loss=0.
        for offset in range(len(curve)-cp['age']):
            mi=min(months-1,m+offset);co,pay,end=step(cp,rates[mi],factors[mi]);loss+=co;cp['balance']=end;cp['age']+=1
        return loss
    opening_allowance=(sum(expected(c,0) for c in cohorts) if p.get('allowance_mode')=='profile_expected_loss' else sum(c['balance'] for c in cohorts)*float(p.get('reserve_rate_pct_bal') or 0))
    monthly=[];ledger=[]
    retain=linked['target_retention_share'];available=1-linked['reserve_share']
    for m,v in enumerate(funded):
        begin=sum(c['balance'] for c in cohorts);new=v*available*retain;newdist=v*available*(1-retain)
        if new:cohorts.append({'id':'funded-'+str(m+1),'original':new,'balance':new,'age':0,'funding_month':m+1,'loss_rate':rates[m]})
        if newdist:distributed.append({'id':'distributed-'+str(m+1),'original':newdist,'balance':newdist,'age':0})
        repayments=chargeoffs=0.
        for c in cohorts:
            isnew=c.get('funding_month')==m+1;beg=c['balance'];age=c['age'];co,pay,end=step(c,rates[m],factors[m],new=isnew)
            c['balance']=end;c['age']+=1;repayments+=pay;chargeoffs+=co
            acl=expected(c,m+1) if p.get('allowance_mode')=='profile_expected_loss' else end*float(p.get('reserve_rate_pct_bal') or 0)
            ledger.append({'month':m+1,'cohort':c['id'],'age_month':age,'original_principal':c['original'],'beginning':0. if isnew else beg,'funded':new if isnew else 0.,'charge_offs':co,'repayments':pay,'ending':end,'allowance':acl,'loss_rate':rates[m] if profile['loss_basis']=='annual_balance' else c['loss_rate'],'loss_factor':factors[m],'loss_exposure':(0. if isnew and profile['loss_balance_measure']=='period_begin' else beg) if profile['loss_basis']=='annual_balance' else c['original']*(profile['loss_timing_fractions'][age] if age<len(profile['loss_timing_fractions']) else 0.),'loss_denominator':12 if profile['loss_basis']=='annual_balance' else 1})
        for c in distributed:
            co,pay,end=step(c,0,0,loss=False);c['balance']=end;c['age']+=1
        end=sum(c['balance'] for c in cohorts);dist=sum(c['balance'] for c in distributed)
        acl=sum(expected(c,m+1) for c in cohorts) if p.get('allowance_mode')=='profile_expected_loss' else end*float(p.get('reserve_rate_pct_bal') or 0)
        if abs(begin+new-chargeoffs-repayments-end)>1e-7*max(1,begin+new):raise ValueError('Cohort roll-forward does not reconcile')
        monthly.append({'month':m+1,'beginning':begin,'funded':new,'repayments':repayments,'charge_offs':chargeoffs,'ending':end,'average':(begin+end)/2,'allowance':acl,'distributed':dist})
        cohorts=[c for c in cohorts if c['balance']>1e-10];distributed=[c for c in distributed if c['balance']>1e-10]
    def sums(k):return [sum(x[k] for x in monthly[i:i+width]) for i in range(0,months,width)]
    def ends(k):return [monthly[i+width-1][k] for i in range(0,months,width)]
    measure=linked['interest_balance_measure'];key={'period_begin':'beginning','period_end':'ending','period_average':'average'}[measure]
    output = {'monthly':monthly,'cohorts':ledger,'opening_allowance':opening_allowance,'ending_balance':ends('ending'),'allowance':ends('allowance'),'repayments':sums('repayments'),'charge_offs':sums('charge_offs'),'retained_funded':sums('funded'),'interest_basis':[x/width for x in sums(key)],'average':[x/width for x in sums('average')],'distributed_balance':ends('distributed'),'funded_volume':[sum(funded[i:i+width]) for i in range(0,months,width)],'source_activity':[sum(inputs[i:i+width]) for i in range(0,months,width)],'monthly_funded_volume':funded,'outstanding':[sum(x[k] for k in ('ending','distributed')) for x in [monthly[i+width-1] for i in range(0,months,width)]]}

    if p.get('fee_streams'):
        from .income_modules import product_fee_streams_q
        activity,counts=monthly_sources(a,n,ppy,context)
        operands={'own_balance':[x['average'] for x in monthly],'distributed_balance':[x['distributed'] for x in monthly],'product_funded_flow':funded}
        def check_periods(value):
            if isinstance(value,dict):
                if value.get('period')=='model_period' or value.get('cadence')=='model_period':raise ValueError('Profile fee paths require natural Month / Quarter / Year units')
                for child in value.values():check_periods(child)
            elif isinstance(value,list):
                for child in value:check_periods(child)
        for st in p['fee_streams']:
            check_periods(st)
            if ((st.get('rate') or {}).get('params') or {}).get('schedule'):raise ValueError('Profile fees require a natural-period rate path, not a legacy model-period schedule')
        for q in range(1,n+1):
            product_fee_streams_q(p,q,{'growth_context':context,'account_activity':activity,'cac_monthly_counts':counts,'_profile_monthly_operands':operands},ppy)
    return output
