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
    allowed={'cadence','funding_timing','repayment_fractions','loss_basis','loss_balance_measure','loss_rate_spec','opening_cohorts','opening_distributed_cohorts','loss_timing_fractions','legacy_settings','name','memo','repayment_basis'}
    if set(profile)-allowed:raise ValueError('Unsupported repayment profile settings: '+', '.join(sorted(set(profile)-allowed)))
    basis=profile.get('repayment_basis','surviving_principal')
    if basis not in {'surviving_principal','portfolio_scheduled'}:raise ValueError('Unknown repayment basis')
    if basis=='portfolio_scheduled':
        if profile.get('loss_basis')!='annual_balance':raise ValueError('Portfolio scheduled repayments require annual balance losses')
        if p.get('allowance_mode','reserve_rate')!='reserve_rate':raise ValueError('Portfolio scheduled repayments require a reserve-percent allowance')
        if p.get('allocation_group_id') or float(p.get('target_retention_share',1))!=1 or float(p.get('reserve_share',0))!=0 or profile.get('opening_distributed_cohorts'):
            raise ValueError('Portfolio scheduled repayments require fully retained funding without shared-cap transfers or held-aside funding')
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
            if str(row['id']).startswith(('funded-','distributed-')) or p.get('allocation_group_id') and str(row['id']).startswith('transfer-'):raise ValueError('Opening cohort IDs cannot use generated funding prefixes')
            ids.append(row['id']);age=row.get('next_age_month')
            if isinstance(age,bool) or not isinstance(age,int) or not 0<=age<len(curve):raise ValueError('Opening cohort next age must be within the repayment curve')
            orig=number(row.get('original_principal'),'Opening original principal');bal=number(row.get('outstanding'),'Opening outstanding');paid=number(row.get('repaid_to_date'),'Opening repayments');loss=number(row.get('charged_off_to_date'),'Opening charge-offs')
            transferred=number(row.get('transferred_to_date',0),'Opening transfers')
            if abs(orig-bal-paid-loss-transferred)>1e-7*max(1,orig):raise ValueError('Opening cohort principal must equal repayments + charge-offs + transfers + outstanding')
            if number(row.get('loss_principal_at_opening',orig),'Opening retained loss principal')>orig:raise ValueError('Opening loss principal cannot exceed original principal')
            if key=='opening_cohorts' and profile['loss_basis']=='cohort_volume' and transferred and 'loss_principal_at_opening' not in row:raise ValueError('A previously transferred lifetime-loss cohort requires its remaining retained loss principal')
            if key=='opening_cohorts' and profile['loss_basis']=='cohort_volume':
                if number(row.get('loss_rate_at_funding'),'Opening cohort loss rate')>1:raise ValueError('Opening cohort loss rate must be within 0–100%')
            if key=='opening_distributed_cohorts' and loss:raise ValueError('Distributed cohort credit losses are not modeled by this bank')
        if len(ids)!=len(set(ids)):raise ValueError('Opening cohort IDs must be unique')
    opening=sum(number(x['outstanding'],'Opening outstanding') for x in profile['opening_cohorts'])
    if abs(opening-float(p.get('opening_balance') or 0))>1e-7*max(1,opening):raise ValueError('Opening loan balance must equal explicit opening cohort outstanding')
    if p.get('balance_mode')!='funded_flow_level':raise ValueError('Repayment profiles require a funded-flow lending balance')
    if p.get('allowance_mode','reserve_rate') not in {'reserve_rate','profile_expected_loss','loss_rate_term'}:raise ValueError('Unsupported profiled allowance method')
    if float(p.get('charge_off_ann') or 0)!=0 or any(float(v or 0)!=0 for v in ((p.get('overrides') or {}).get('charge_off_ann') or {}).values()):raise ValueError('Profile loss path replaces legacy charge_off_ann; set the legacy rate and overrides to zero')
    if float(p.get('runoff_per_period') or p.get('runoff_q') or 0)!=0:raise ValueError('Repayment curve replaces legacy runoff; set runoff to zero')
    if p.get('measurement')=='fair_value':raise ValueError('Repayment profiles currently support amortized-cost loans only')
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

def _project_portfolio(p,a,n,ppy,linked,context=None):
    """Independent scheduled gross paydowns and balance losses on one portfolio.

    Unlike surviving-principal cohorts, the original funding curve determines
    contractual paydowns without reducing them for losses. This is an explicit
    portfolio convention, not a claim that an extinguished cohort repays twice.
    Reject impossible portfolio balances rather than clipping either cash flow.
    """
    from .series import resolve_entered_series
    rp=p['repayment_profile'];months=n*(12//ppy);width=12//ppy
    rates=resolve_entered_series(rp['loss_rate_spec'],months,12,context=context)
    factors=resolve_entered_series(p['credit_loss_factor_spec'],months,12,context=context) if p.get('credit_loss_factor_spec') else [1.]*months
    inputs=canonical_flow(p,a,n,ppy,context)
    curve=rp['repayment_fractions'];scheduled=[0.]*months;funded=[]
    for m,v in enumerate(inputs):
        v=number(v,'Monthly funded activity')*number(p.get('_profile_volume_mult',1),'Stress funding multiplier')
        q=m//width+1
        if linked['input_stage']=='funded_volume':
            if q<linked['start_period'] and v:raise ValueError('Final funded volume is nonzero before the configured start')
        else:v*=linked['take_up_share']*(0 if q<linked['start_period'] else min(1,(q-linked['start_period']+1)/linked['ramp_periods']))
        funded.append(v)
        for age,f in enumerate(curve):
            if m+age<months:scheduled[m+age]+=v*f
    for c in rp['opening_cohorts']:
        for age in range(c['next_age_month'],len(curve)):
            m=age-c['next_age_month']
            if m<months:scheduled[m]+=float(c['original_principal'])*curve[age]
    begin=float(p.get('opening_balance') or 0);reserve=float(p.get('reserve_rate_pct_bal') or 0)
    opening_allowance=begin*reserve;monthly=[]
    overrides={int(k):number(v,'Stress annual loss') for k,v in (p.get('_profile_loss_overrides') or {}).items()}
    for m,v in enumerate(funded):
        quote=number(rates[m],'Annual loss rate')
        if quote>1:raise ValueError('Annual loss rate must be within 0–100%')
        rate=overrides.get(m//width+1,quote*number(p.get('_profile_loss_mult',1),'Stress loss multiplier'))
        factor=number(factors[m],'Credit loss factor')
        exposure=begin+(v if rp['loss_balance_measure']=='balance_plus_funding' else 0)
        loss=exposure*rate*factor/12;pay=scheduled[m];end=begin+v-loss-pay
        if end < -1e-7:
            raise ValueError(f'Portfolio scheduled repayments and charge-offs exceed available principal in month {m+1}; revise repayment or loss assumptions')
        end=max(0.,end)  # floating-point roundoff only, not economic clipping
        allocation=yield end
        if allocation!=1:raise ValueError('Portfolio scheduled repayments do not support shared-cap transfers')
        monthly.append({'month':m+1,'beginning':begin,'funded':v,'charge_offs':loss,'repayments':pay,'ending':end,'average':(begin+end)/2,'allowance':end*reserve,'distributed':0.,'transfers_out':0.,'target_before_allocation':end,'allocation_factor':1.,'loss_exposure':exposure,'loss_rate':rate,'loss_factor':factor,'loss_denominator':12,'repayment_basis':'portfolio_scheduled'})
        begin=end
    def sums(k):return [sum(x[k] for x in monthly[i:i+width]) for i in range(0,months,width)]
    def ends(k):return [monthly[i+width-1][k] for i in range(0,months,width)]
    key={'period_begin':'beginning','period_end':'ending','period_average':'average'}[linked['interest_balance_measure']]
    out={'monthly':monthly,'cohorts':[],'distributed_cohorts':[],'opening_allowance':opening_allowance,'ending_balance':ends('ending'),'allowance':ends('allowance'),'repayments':sums('repayments'),'transfers_out':sums('transfers_out'),'target_before_allocation':ends('ending'),'charge_offs':sums('charge_offs'),'retained_funded':sums('funded'),'interest_basis':[v/width for v in sums(key)],'average':[v/width for v in sums('average')],'distributed_balance':[0.]*n,'funded_volume':sums('funded'),'source_activity':[sum(inputs[i:i+width]) for i in range(0,months,width)],'monthly_funded_volume':funded,'outstanding':ends('ending'),'repayment_basis':'portfolio_scheduled'}
    _validate_profile_fees(p,a,n,ppy,out,context)
    return out


def _validate_profile_fees(p,a,n,ppy,output,context):
    if not p.get('fee_streams'):return
    from .income_modules import product_fee_streams_q
    activity,counts=monthly_sources(a,n,ppy,context)
    operands={'own_balance':[x['average'] for x in output['monthly']],'own_balance_end':[x['ending'] for x in output['monthly']],'distributed_balance':[x['distributed'] for x in output['monthly']],'product_funded_flow':output['monthly_funded_volume']}
    def check(value):
        if isinstance(value,dict):
            if value.get('period')=='model_period' or value.get('cadence')=='model_period':raise ValueError('Profile fee paths require natural Month / Quarter / Year units')
            for child in value.values():check(child)
        elif isinstance(value,list):
            for child in value:check(child)
    for st in p['fee_streams']:
        check(st)
        if ((st.get('rate') or {}).get('params') or {}).get('schedule'):raise ValueError('Profile fees require a natural-period rate path, not a legacy model-period schedule')
    for q in range(1,n+1):
        product_fee_streams_q(p,q,{'growth_context':context,'account_activity':activity,'customer_acquisition_count':{},'cac_monthly_counts':counts,'_profile_monthly_operands':operands},ppy)


def _project(p,a,n,ppy,linked,context=None):
    profile=validate(p,a)
    if profile is None:return None
    if profile.get('repayment_basis')=='portfolio_scheduled':
        return (yield from _project_portfolio(p,a,n,ppy,linked,context))
    months=n*(12//ppy);width=12//ppy;curve=profile['repayment_fractions'];cum=[];total=0.
    for x in curve:cum.append(total);total+=x
    from .series import resolve_entered_series
    rates=resolve_entered_series(profile['loss_rate_spec'],months,12,context=context)
    rates=[number(v,'Profile loss rate') for v in rates]
    if any(v>1 for v in rates):raise ValueError('Profile loss rates must be within 0–100%')
    factors=resolve_entered_series(p['credit_loss_factor_spec'],months,12,context=context) if p.get('credit_loss_factor_spec') else [1.]*months
    factors=[number(v,'Credit loss factor') for v in factors]
    rates=[v*number(p.get('_profile_loss_mult',1),'Stress loss multiplier') for v in rates]
    overlays={int(k):number(v,'Stress annual balance loss') for k,v in (p.get('_profile_loss_overrides') or {}).items()}
    inputs=[v*number(p.get('_profile_volume_mult',1),'Stress funding multiplier') for v in canonical_flow(p,a,n,ppy,context)]
    fd=p['funded_flow_driver'];funded=[]
    for m,v in enumerate(inputs):
        q=m//width+1
        if linked['input_stage']=='funded_volume':
            if q<linked['start_period'] and abs(v)>1e-9:raise ValueError('Final funded volume is nonzero before the configured start')
            funded.append(v)
        else:funded.append(v*linked['take_up_share']*(0 if q<linked['start_period'] else min(1,(q-linked['start_period']+1)/linked['ramp_periods'])))
    cohorts=[];distributed=[]
    def opening(rows):
        return [dict(id=x['id'],original=float(x['original_principal']),balance=float(x['outstanding']),age=x['next_age_month'],loss_rate=float(x.get('loss_rate_at_funding',0))*float(p.get('_profile_loss_mult',1)),loss_principal=float(x.get('loss_principal_at_opening',x['original_principal']))) for x in rows]
    cohorts=opening(profile['opening_cohorts']);distributed=opening(profile['opening_distributed_cohorts'])
    def step(c,rate,factor, *, new=False, loss=True, month=None):
        age=c['age'];beg=c['balance'];orig=c['original']
        if age>=len(curve):
            if beg>1e-7:raise ValueError('Exposure remains after the entered repayment horizon')
            return 0.,0.,0.
        co=0.
        if loss:
            overlay=overlays.get(month//width+1) if month is not None else None
            if overlay is not None:
                co=(0. if new and profile['loss_balance_measure']=='period_begin' else beg)*overlay*factor/12.
            elif profile['loss_basis']=='cohort_volume':
                timing=profile['loss_timing_fractions'];co=c.get('loss_principal',orig)*float(c['loss_rate'])*factor*(timing[age] if age<len(timing) else 0.)
            else:co=(0. if new and profile['loss_balance_measure']=='period_begin' else beg)*rate*factor/12.
        if co>beg+1e-8:raise ValueError('Profile charge-offs exceed available cohort exposure')
        remaining=beg-co;pay=remaining*(curve[age]/(1-cum[age]) if cum[age]<1-1e-12 else 0.)
        end=remaining-pay
        if end<-1e-7:raise ValueError('Profile repayments exceed available exposure')
        return co,pay,max(0.,end)
    def expected(c,m):
        cp=copy.deepcopy(c);loss=0.
        for offset in range(len(curve)-cp['age']):
            mi=min(months-1,m+offset);co,pay,end=step(cp,rates[mi],factors[mi],month=m+offset);loss+=co;cp['balance']=end;cp['age']+=1
        return loss
    def allowance(c,m):
        mode=p.get('allowance_mode','reserve_rate')
        if mode=='reserve_rate':return c['balance']*float(p.get('reserve_rate_pct_bal') or 0)
        if mode=='profile_expected_loss' or profile['loss_basis']=='cohort_volume':return expected(c,m)
        # Curve survival rebases the legacy term method; no fixed exposure-days input.
        cp=copy.deepcopy(c);exposure=0.
        for offset in range(len(curve)-cp['age']):
            exposure+=cp['balance'];_,_,end=step(cp,0,0,loss=False)
            cp['balance']=end;cp['age']+=1
        mi=min(months-1,m);quote=overlays.get(m//width+1,rates[mi])
        return min(c['balance'],exposure*quote*factors[mi]/12.)
    opening_allowance=sum(allowance(c,0) for c in cohorts)
    monthly=[];ledger=[];distributed_ledger=[]
    retain=linked['target_retention_share'];available=1-linked['reserve_share']
    for m,v in enumerate(funded):
        begin=sum(c['balance'] for c in cohorts);dist_begin=sum(c['balance'] for c in distributed);new=v*available*retain;newdist=v*available*(1-retain)
        if new:cohorts.append({'id':'funded-'+str(m+1),'original':new,'balance':new,'age':0,'funding_month':m+1,'loss_rate':rates[m],'loss_principal':new})
        if newdist:distributed.append({'id':'distributed-'+str(m+1),'original':newdist,'balance':newdist,'age':0,'funding_month':m+1})
        repayments=chargeoffs=0.;month_rows=[]
        for c in cohorts:
            isnew=c.get('funding_month')==m+1;beg=c['balance'];age=c['age'];co,pay,end=step(c,rates[m],factors[m],new=isnew,month=m)
            c['balance']=end;c['age']+=1;repayments+=pay;chargeoffs+=co
            month_rows.append({'month':m+1,'cohort':c['id'],'age_month':age,'original_principal':c['original'],'beginning':0. if isnew else beg,'funded':new if isnew else 0.,'charge_offs':co,'repayments':pay,'ending':end,'allowance':0.,'transfers_out':0.,'loss_rate':overlays.get(m//width+1,rates[m] if profile['loss_basis']=='annual_balance' else c['loss_rate']),'loss_treatment':'stress_balance_replacement' if m//width+1 in overlays else profile['loss_basis'],'loss_factor':factors[m],'loss_exposure':(0. if isnew and profile['loss_balance_measure']=='period_begin' else beg) if profile['loss_basis']=='annual_balance' or m//width+1 in overlays else c.get('loss_principal',c['original'])*(profile['loss_timing_fractions'][age] if age<len(profile['loss_timing_fractions']) else 0.),'loss_denominator':12 if profile['loss_basis']=='annual_balance' or m//width+1 in overlays else 1})
        dist_pay=0.
        for c in distributed:
            beg=c['balance'];age=c['age'];isnew=c.get('funding_month')==m+1
            co,pay,end=step(c,0,0,loss=False);c['balance']=end;c['age']+=1;dist_pay+=pay
            distributed_ledger.append({'month':m+1,'cohort':c['id'],'age_month':age,'beginning':0. if isnew else beg,'funded':beg if isnew else 0.,'transfers_in':0.,'repayments':pay,'ending':end})
        target=sum(c['balance'] for c in cohorts)
        factor=yield target
        if not math.isfinite(factor) or not 0<=factor<=1:raise ValueError('Invalid cohort allocation factor')
        transfer=0.
        for c,row in zip(cohorts,month_rows):
            sold=c['balance']*(1-factor);transfer+=sold
            if sold:
                tid='transfer-'+c['id']+'-'+str(m+1)
                distributed.append({'id':tid,'original':sold,'balance':sold,'age':c['age']})
                distributed_ledger.append({'month':m+1,'cohort':tid,'age_month':c['age']-1,'beginning':0.,'funded':0.,'transfers_in':sold,'repayments':0.,'ending':sold})
                c['balance']-=sold;c['loss_principal']=c.get('loss_principal',c['original'])*factor
            row['transfers_out']=sold;row['ending']=c['balance'];row['allowance']=allowance(c,m+1)
            ledger.append(row)
        end=sum(c['balance'] for c in cohorts);dist=sum(c['balance'] for c in distributed)
        acl=sum(allowance(c,m+1) for c in cohorts)
        if abs(begin+new-chargeoffs-repayments-transfer-end)>1e-7*max(1,begin+new):raise ValueError('Cohort roll-forward does not reconcile')
        if abs(dist_begin+newdist+transfer-dist_pay-dist)>1e-7*max(1,dist_begin+newdist+transfer):raise ValueError('Distributed cohort roll-forward does not reconcile')
        monthly.append({'distributed_beginning':dist_begin,'distributed_funded':newdist,'distributed_repayments':dist_pay,'distributed_transfers_in':transfer,'month':m+1,'beginning':begin,'funded':new,'repayments':repayments,'transfers_out':transfer,'target_before_allocation':target,'allocation_factor':factor,'charge_offs':chargeoffs,'ending':end,'average':(begin+end)/2,'allowance':acl,'distributed':dist})
        cohorts=[c for c in cohorts if c['balance']>1e-10];distributed=[c for c in distributed if c['balance']>1e-10]
    def sums(k):return [sum(x[k] for x in monthly[i:i+width]) for i in range(0,months,width)]
    def ends(k):return [monthly[i+width-1][k] for i in range(0,months,width)]
    measure=linked['interest_balance_measure'];key={'period_begin':'beginning','period_end':'ending','period_average':'average'}[measure]
    output = {'monthly':monthly,'cohorts':ledger,'distributed_cohorts':distributed_ledger,'opening_allowance':opening_allowance,'ending_balance':ends('ending'),'allowance':ends('allowance'),'repayments':sums('repayments'),'transfers_out':sums('transfers_out'),'target_before_allocation':ends('target_before_allocation'),'charge_offs':sums('charge_offs'),'retained_funded':sums('funded'),'interest_basis':[x/width for x in sums(key)],'average':[x/width for x in sums('average')],'distributed_balance':ends('distributed'),'funded_volume':[sum(funded[i:i+width]) for i in range(0,months,width)],'source_activity':[sum(inputs[i:i+width]) for i in range(0,months,width)],'monthly_funded_volume':funded,'outstanding':[sum(x[k] for k in ('ending','distributed')) for x in [monthly[i+width-1] for i in range(0,months,width)]]}

    if p.get('fee_streams'):
        from .income_modules import product_fee_streams_q
        activity,counts=monthly_sources(a,n,ppy,context)
        operands={'own_balance':[x['average'] for x in monthly],'own_balance_end':[x['ending'] for x in monthly],'distributed_balance':[x['distributed'] for x in monthly],'product_funded_flow':funded}
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


def _drive(projector, factors=None):
    """Single-product projection with explicit monthly allocation factors."""
    month=0
    try:
        next(projector)
        while True:
            projector.send(1. if factors is None else factors[month]);month+=1
    except StopIteration as done:return done.value


def resolve(p,a,n,ppy,linked,context=None):
    if p.get('repayment_profile') is None:return None
    if p.get('allocation_group_id'):
        raise ValueError('Shared cohort allocation must resolve all pool members together')
    return _drive(_project(p,a,n,ppy,linked,context))


def resolve_group(members,a,n,ppy,capacity,legacy_targets,context=None):
    """Simultaneous monthly post-loss/paydown cap. Transfers are at par, never buybacks.

    A falling cap may transfer seasoned exposure. Each transfer removes the
    surviving principal and its future bank loss share, without changing cash
    repayments, historical charge-offs, or the original cohort principal.
    """
    months=n*(12//ppy);width=12//ppy
    if len(capacity)!=months:raise ValueError('Shared cohort cap needs a canonical monthly capacity')
    gens={p['allocation_target_id']:_project(p,a,n,ppy,p['_linked_balance'],context) for p in members if p.get('repayment_profile') is not None}
    targets={key:next(gen) for key,gen in gens.items()};results={}
    keys=[p['allocation_target_id'] for p in members]
    audit={'targets':{k:[] for k in keys},'cap':[],'total_target':[],'factor':[],'retained':{k:[] for k in keys},'distributed':{k:[] for k in keys},'monthly':[],'profile_cap_treatment':'transfer_at_par_no_buyback'}
    for m in range(months):
        all_targets={k:targets[k] if k in gens else legacy_targets[k][m] for k in keys}
        cap=number(capacity[m],'Monthly capacity');total=sum(number(v,'Monthly target') for v in all_targets.values());factor=min(1.,cap/total) if total else 1.
        row={'month':m+1,'cap':cap,'total_target':total,'factor':factor,'targets':all_targets.copy(),'retained':{k:v*factor for k,v in all_targets.items()}}
        audit['monthly'].append(row)
        if (m+1)%width==0:
            audit['cap'].append(cap);audit['total_target'].append(total);audit['factor'].append(factor)
            for k,v in all_targets.items():
                audit['targets'][k].append(v);audit['retained'][k].append(v*factor);audit['distributed'][k].append(v*(1-factor))
        for key,gen in gens.items():
            try:targets[key]=gen.send(factor)
            except StopIteration as done:results[key]=done.value
    if len(results)!=len(gens):raise ValueError('Incomplete shared cohort projection')
    return results,audit


def monthly_allocation_inputs(cfg,group,members,n,ppy,context=None):
    """Resolve monthly capacities and legacy level targets without profile recursion.

    Entered natural-cadence levels are evaluated at month ends. A legacy explicit
    model-period level is held constant within that period. The deposit-book
    capacity uses the native-period closing deposit target, held within the
    period. It does not claim to observe intra-period deposit balances.
    """
    from .series import resolve_entered_series
    months=n*(12//ppy);width=12//ppy;a=cfg['assumptions'];legacy={}
    def monthly_spec(spec):
        spec=copy.deepcopy(spec)
        if spec.get('cadence')=='model_period':
            vals=resolve_entered_series(spec,n,ppy,context=context)
            return {'source':'entered','trajectory':'explicit','cadence':'month','values':[v for v in vals for _ in range(width)]}
        return spec
    for p in members:
        if p.get('repayment_profile') is not None:continue
        if p.get('balance_mode')=='explicit_level':
            legacy[p['allocation_target_id']]=resolve_entered_series(monthly_spec(p['ending_balance_spec']),months,12,context=context)
        else:
            # Preserve the existing native-period start/take-up/ramp convention.
            ln=p['_linked_balance'];inputs=canonical_flow(p,a,n,ppy,context)
            vals=[]
            for m,v in enumerate(inputs):
                q=m//width+1
                vals.append(v if ln['input_stage']=='funded_volume' else v*ln['take_up_share']*(0 if q<ln['start_period'] else min(1,(q-ln['start_period']+1)/ln['ramp_periods'])))
            legacy[p['allocation_target_id']]=[v*12*ln['term_days']/ln['day_count']*(1-ln['reserve_share'])*ln['target_retention_share'] for v in vals]
    if group['cap_source']=='entered':
        return resolve_entered_series(monthly_spec(group['cap_spec']),months,12,context=context),legacy
    # The cap source is the native-model-period closing deposit target. As with
    # an entered quarterly level, that target applies throughout its period.
    # No intra-quarter deposit observations are invented. Monthly modeling or
    # an entered monthly capacity is needed for a genuinely monthly deposit cap.
    return [float(group['cap_ratio'])*v for v in group['_monthly_deposit_book']],legacy
