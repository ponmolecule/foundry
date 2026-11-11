"""Opt-in loan production, principal runoff and deferred fees/costs (Profile A).

Rates are annual fractions divided by native periods/year. This is a portfolio
beginning-balance method, not contractual level-payment or effective-yield amortization.
Principal and signed net deferred costs remain separately auditable.
"""
from math import isfinite
from .series import resolve_entered_series


def flat(value=0):
    return dict(source='entered', trajectory='flat', value=value)


def path(spec, n, ppy, context, label, maximum=None):
    if not isinstance(spec, dict) or spec.get('source', 'entered') != 'entered':
        raise ValueError(label + ' requires an entered Series')
    vals = [float(x) for x in resolve_entered_series(spec, n, ppy, context=context)]
    if any(not isfinite(x) or x < 0 or maximum is not None and x > maximum for x in vals):
        raise ValueError(label + ' contains an invalid nonnegative value')
    return vals


_RATE_PERIODS = {'month': 12, 'quarter': 4, 'year': 1}
_MEASURES = {'period_begin': 'Beginning balance', 'period_end': 'Ending balance',
             'period_average': 'Average balance'}


def linked_deposit_originations(c, a, deposits, n, ppy, context=None):
    """r485: originations = observed deposit balance x percentage x rate periods/yr / model periods/yr.

    The source is one upstream deposit product selected by its stable ``source_catalog_id``.
    Deposit balances are resolved before loans, so the link has no funding feedback. Retention-pool
    members are allocated from bank state inside the period loop and are rejected, as are lending
    balances, bank totals and missing or duplicated IDs. Nothing is substituted with zero.
    """
    did = str(c.get('deposit_id') or '').strip()
    if not did:
        raise ValueError('Linked deposit origination source requires a deposit product')
    if did == 'bank.deposits' or did.startswith('deposit_pool.'):
        raise ValueError('Linked deposit origination source must be one deposit product, not a total or retention pool')
    if any(str(x.get('id') or '') == did for x in a.get('deposit_retention_pools') or []):
        raise ValueError('Linked deposit origination source cannot be a deposit retention pool')
    if any(str(x.get('source_catalog_id') or '') == did for x in a.get('lending_products') or []):
        raise ValueError('Linked deposit origination source cannot be a lending balance')
    hits = [d for d in (deposits or []) if str(d.get('source_catalog_id') or '') == did]
    if not hits:
        raise ValueError(f'Linked deposit origination source {did!r} does not match any deposit product')
    if len(hits) > 1:
        raise ValueError(f'Linked deposit origination source {did!r} matches more than one deposit product')
    d = hits[0]
    if d.get('balance_mode') == 'pool' or d.get('retention_pool_id'):
        raise ValueError('Linked deposit origination source cannot be a retention-pool deposit; its balance depends on bank state')
    measure = c.get('balance_measure')
    if measure not in _MEASURES:
        raise ValueError('Linked deposit origination source requires a beginning, ending or average balance')
    period = c.get('percentage_period')
    if period not in _RATE_PERIODS:
        raise ValueError('Linked deposit origination percentage requires a Month, Quarter or Year period')
    bal, avg = list(d.get('_bal') or []), list(d.get('_avg') or [])
    if len(bal) != n + 1 or len(avg) != n + 1:
        raise ValueError('Linked deposit balance is not resolved for every model period')
    if measure == 'period_begin':
        source = bal[:n]
    elif measure == 'period_end':
        source = bal[1:]
    else:
        source = avg[1:]
    source = [float(x) if x is not None else float('nan') for x in source]
    if any(not isfinite(x) or x < 0 for x in source):
        raise ValueError('Linked deposit balance must be finite and nonnegative in every period')
    pct = path(c.get('percentage_spec'), n, ppy, context, 'Linked deposit origination percentage')
    factor = _RATE_PERIODS[period] / float(ppy)
    effective = [x * factor for x in pct]
    return dict(deposit_id=did, deposit_name=d.get('name'), balance_measure=measure,
                percentage_period=period, rate_periods_per_year=_RATE_PERIODS[period],
                model_periods_per_year=int(ppy), source_balance=source, percentage=pct,
                effective_percentage=effective,
                originations=[b * e for b, e in zip(source, effective)],
                switched_off=bool(d.get('_scenario_off')))


def prepare(p, a, activity, quantities, n, ppy, context=None, deposits=None):
    c = p.get('loan_rollforward')
    if c is None:
        return None
    if not isinstance(c, dict) or p.get('balance_mode', 'rollforward') != 'rollforward':
        raise ValueError('Loan production contract requires Loan roll-forward balance authoring')
    if p.get('mortgage_banking') or p.get('repayment_profile') or p.get('allocation_group_id') or p.get('measurement') == 'fair_value':
        raise ValueError('Loan production contract requires held amortized-cost loans without a repayment profile or shared cap')
    if any((p.get('overrides') or {}).get(k) for k in ('originations_q','originations_per_period','runoff_q','runoff_per_period')):
        raise ValueError('Remove legacy origination/runoff overrides before using the loan production contract')
    if p.get('allowance_mode','reserve_rate') != 'reserve_rate':
        raise ValueError('Loan production contract uses scheduled reserve-percent allowance')
    source = c.get('source')
    counts = None
    linked = None
    if source == 'account_activity':
        from .account_activity import catalog
        ids = {x['series_id'] for x in catalog(a) if x.get('field') == 'new_customers'}
        sid = c.get('series_id')
        if sid not in ids or sid not in activity:
            raise ValueError('Loan production requires an available gross new-customer flow')
        counts = list(activity[sid]['values'])
    elif source == 'entered_count':
        counts = path(c.get('count_spec'), n, ppy, context, 'New loans')
    elif source == 'entered_money':
        funded = path(c.get('amount_spec'), n, ppy, context, 'Originations')
    elif source == 'deposit_balance':
        linked = linked_deposit_originations(c, a, deposits, n, ppy, context)
        funded = list(linked['originations'])
    else:
        raise ValueError('Select entered loan count, gross customer flow, entered monetary originations or linked deposit balance')
    if counts is not None:
        if len(counts) != n or any(not isfinite(x) or x < 0 for x in counts):
            raise ValueError('Loan count flow must be complete and nonnegative')
        sizes = path(c.get('loan_size_spec'), n, ppy, context, 'Loan size')
        funded = [x*y for x,y in zip(counts, sizes)]
    volume_mult = float(p.get('_contract_volume_mult',1))
    if not isfinite(volume_mult) or not 0 <= volume_mult <= 1:raise ValueError('Loan volume haircut must be between zero and one')
    funded = [x*volume_mult for x in funded]
    if linked is not None:
        linked.update(volume_multiplier=volume_mult, originations=list(funded))
    if counts is not None:counts = [x*volume_mult for x in counts]
    payment = path(c.get('payment_rate_spec'), n, ppy, context, 'Principal payment annual rate', 1)
    prepay = path(c.get('prepayment_rate_spec'), n, ppy, context, 'Prepayment annual rate', 1)
    if any((x+y)/ppy > 1 for x,y in zip(payment, prepay)):
        raise ValueError('Combined principal paydown exceeds the beginning balance')
    policy = c.get('provision_release_policy', 'allow')
    if policy not in ('allow','floor_zero'):
        raise ValueError('Unknown provision release policy')
    reserve = path(c.get('reserve_rate_spec'), n, ppy, context, 'Allowance target', 1)
    reserve = [x*float(p.get('_contract_reserve_mult',1)) for x in reserve]
    if any(not isfinite(x) or not 0 <= x <= 1 for x in reserve):raise ValueError('Stressed allowance target must be between zero and one')
    opening_allowance = float(c.get('opening_allowance',0))
    if not isfinite(opening_allowance) or opening_allowance < 0:
        raise ValueError('Opening allowance must be finite and nonnegative')
    d = c.get('deferred')
    if d is not None and not isinstance(d,dict):raise ValueError('Deferred fees/costs must be an object')
    result = dict(counts=counts, funded=funded, payment=payment, prepay=prepay,
                  reserve=reserve, policy=policy, allowance=opening_allowance,
                  opening_allowance=opening_allowance, deferred_balance=0., opening_deferred=0., rows=[],
                  linked=linked)
    if d is not None:
        basis = d.get('basis','per_loan')
        if basis not in ('per_loan','percent_funded'):raise ValueError('Unknown deferred fees/costs basis')
        if basis == 'per_loan' and counts is None:raise ValueError('Per-loan deferred fees/costs require a loan-count source')
        cost = path(d.get('cost_spec',flat()), n, ppy, context, 'Deferred origination cost',1 if basis=='percent_funded' else None)
        fee = path(d.get('fee_spec',flat()), n, ppy, context, 'Deferred origination fee',1 if basis=='percent_funded' else None)
        mult = path(d.get('multiplier_spec',flat(1)), n, ppy, context, 'Deferred fee/cost multiplier')
        amort = path(d.get('amortization_rate_spec'), n, ppy, context, 'Deferred amortization annual rate',1)
        catch = path(d.get('prepayment_rate_spec'), n, ppy, context, 'Deferred prepayment annual rate',1)
        if any((x+y)/ppy>1 for x,y in zip(amort,catch)):raise ValueError('Deferred amortization exceeds beginning deferred balance')
        opening = float(d.get('opening_net_cost',0))
        if not isfinite(opening):raise ValueError('Opening deferred net cost must be finite')
        operand = counts if basis=='per_loan' else funded
        result.update(deferred_balance=opening,opening_deferred=opening,
                      cost=[x*y*z for x,y,z in zip(operand,cost,mult)],
                      fee=[x*y*z for x,y,z in zip(operand,fee,mult)],amort=amort,catch=catch)
    return result


def step(c, i, beginning, charge_off_rate, annual_yield, ppy):
    if not isfinite(charge_off_rate) or charge_off_rate < 0:raise ValueError('Charge-off rate must be finite and nonnegative')
    payment = beginning*c['payment'][i]/ppy
    prepay = beginning*c['prepay'][i]/ppy
    co = beginning*charge_off_rate/ppy
    if payment+prepay+co > beginning+1e-8:raise ValueError('Loan paydowns and losses exceed beginning principal')
    ending = beginning+c['funded'][i]-payment-prepay-co
    dbeg = c['deferred_balance']
    cost = c.get('cost',[0]*len(c['funded']))[i]
    fee = c.get('fee',[0]*len(c['funded']))[i]
    amort = dbeg*c['amort'][i]/ppy if 'amort' in c else 0.
    catch = dbeg*c['catch'][i]/ppy if 'catch' in c else 0.
    dend = dbeg+cost-fee-amort-catch
    gross_interest = (beginning+ending)/2*annual_yield/ppy
    target = ending*c['reserve'][i]
    provision = target-c['allowance']+co
    if c['policy']=='floor_zero':provision=max(0.,provision)
    allowance = c['allowance']-co+provision
    if allowance < -1e-8:raise ValueError('Loan allowance cannot be negative')
    row = dict(beginning=beginning,originations=c['funded'][i],principalPayments=payment,
               prepayments=prepay,chargeOffs=co,ending=ending,grossInterest=gross_interest,
               deferredBeginning=dbeg,deferredCosts=cost,deferredFees=fee,
               deferredAmortization=amort,deferredPrepaymentCatchup=catch,
               deferredNetBalance=dend,loanCarryingAmount=ending+dend,
               interest=gross_interest-amort-catch,allowanceTarget=target,
               provision=provision,allowance=max(0.,allowance))
    if c['counts'] is not None:row['newLoanCount']=c['counts'][i]
    c.update(deferred_balance=dend,allowance=max(0.,allowance))
    c['rows'].append(row)
    return row
