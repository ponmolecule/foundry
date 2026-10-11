"""Configured expense gross-up eligibility. No expense is reclassified or posted twice."""
import math

DEFAULTS={'compensation':True,'categories':True,'fdic':True,'occ':True,'depreciation':True,'product_opex':True,'fee_costs':False}

def active(a):
    nd=a.get('nie_detail') or {}
    if 'gross_up_eligibility' in nd:return True
    def walk(x):
        if isinstance(x,dict):return 'gross_up_eligible' in x or 'opex_gross_up_eligible' in x or any(walk(v) for v in x.values())
        return isinstance(x,list) and any(walk(v) for v in x)
    return walk(a)

def validate(a):
    nd=a.get('nie_detail') or {};policy=nd.get('gross_up_eligibility',{})
    if not isinstance(policy,dict) or set(policy)-set(DEFAULTS):raise ValueError('Gross-up eligibility has unknown expense groups')
    if any(type(v) is not bool for v in policy.values()):raise ValueError('Gross-up group eligibility must be boolean')
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in {'gross_up_eligible','opex_gross_up_eligible'} and type(v) is not bool:raise ValueError('Gross-up line eligibility must be boolean')
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(a)
    if active(a) and not nd:raise ValueError('Gross-up eligibility requires detailed Operating Expense settings')
    for k in ('lending_products','deposit_products','obs_exposures'):
        for p in a.get(k) or []:
            for s in p.get('fee_streams') or []:
                if 'gross_up_eligible' in (s.get('cost') or {}) and not s.get('quantity_series_id'):raise ValueError('Individual fee cost eligibility requires a stable stream quantity ID')

def calculate(a, q, ppy, prepared, *, compensation, role_rows=(), additive_values=(), fdic, occ, depreciation, fixed_assets=None, products=(), linked_values=(), fee_economics=None, product_total):
    """Return eligibility base and evidence in engine dollars, preserving the old base by default."""
    nd=a.get('nie_detail') or {};wf=nd.get('workforce') or {};policy=nd.get('gross_up_eligibility') or {};rows=[]
    def add(label,group,amount,raw=None,inherited=None,field='gross_up_eligible'):
        default=DEFAULTS[group];selected=policy.get(group,default)
        if inherited is not None:selected=inherited
        if raw is not None and field in raw:selected=raw[field]
        amount=float(amount or 0)
        if not math.isfinite(amount):raise ValueError('Gross-up expense amount must be finite')
        rows.append({'name':label,'group':group,'amount':amount,'eligible':selected,'eligible_amount':amount if selected else 0.,'legacy_eligible':default})
    role_amount=0.
    for row in role_rows:
        raw=row.get('raw') or {};amount=(row.get('period_expenses') or {}).get(q,0.);role_amount+=amount
        add(raw.get('role') or 'Compensation role','compensation',amount,raw)
    adds=list(wf.get('additive_components') or []);add_amount=sum(additive_values)
    for i,v in enumerate(additive_values):
        raw=adds[i] if i<len(adds) else {};add(raw.get('name') or 'Additive compensation','compensation',v,raw)
    add('Other / legacy compensation','compensation',compensation-role_amount-add_amount,wf)
    cats=nd.get('categories') or []
    for i,cat in enumerate(cats):
        selected=cat.get('gross_up_eligible',policy.get('categories',True))
        arr=(prepared.get('_category_series') or [])[i]
        add(cat.get('name') or 'Expense category','categories',arr[q-1],cat)
        for j,component in enumerate(prepared.get('linked_components') or []):
            if component.get('category_index')==i:
                raw=component.get('_gross_raw') or {};amount=linked_values[j] if j<len(linked_values) else 0.
                add(raw.get('name') or (cat.get('name') or 'Expense')+' — component','categories',amount,raw,inherited=selected)
    add('FDIC assessment','fdic',fdic);add('OCC assessment','occ',occ)
    dep_total=0.;fa=fixed_assets or {};rawassets=(a.get('fixed_assets') or {}).get('assets') or []
    for i,asset in enumerate(fa.get('asset_rows') or []):
        life=asset.get('remaining_life_periods') or asset.get('useful_life_periods') or 0;start=int(asset.get('in_service_period') or 0)
        enabled=(q<=life) if asset.get('type')=='existing' or start==0 else start<=q<start+life
        amount=float(asset.get('depreciation_per_period') or 0) if enabled else 0.;dep_total+=amount
        raw=rawassets[i] if i<len(rawassets) else {};add(asset.get('name') or 'Asset depreciation','depreciation',amount,raw)
    add('Other / formula depreciation','depreciation',depreciation-dep_total,a.get('fixed_assets') or {})
    prod_sum=0.;fee_sum=0.;econ=fee_economics or {}
    for p in products:
        amount=(p.get('_ox') or [])[q];prod_sum+=amount
        add((p.get('name') or 'Product')+' — operating expense','product_opex',amount,p,field='opex_gross_up_eligible')
        product_fee=float((p.get('_fcost') or [0]*(q+1))[q] or 0);item_fee=0.
        for s in p.get('fee_streams') or []:
            c=s.get('cost') or {};arr=(econ.get(s.get('quantity_series_id')) or {}).get('fee_product_cost') or []
            if q<=len(arr):
                v=float(arr[q-1] or 0);item_fee+=v
                add((p.get('name') or 'Product')+' › '+(s.get('name') or 'Stream')+' — cost','fee_costs',v,c)
        add((p.get('name') or 'Product')+' — other stream costs','fee_costs',product_fee-item_fee)
        fee_sum+=product_fee
    add('Other product operating expense','product_opex',product_total-prod_sum)
    legacy=compensation+prepared['categories'][q-1]+sum(linked_values)+fdic+occ+depreciation+product_total
    adjustment=sum(r['amount']*((1 if r['eligible'] else 0)-(1 if r['legacy_eligible'] else 0)) for r in rows)
    base=legacy+adjustment;rate=float(prepared['gross_up_rate']);charge=base*rate/(1-rate) if 0<rate<1 else 0.
    if abs(sum(r['amount'] for r in rows)-(legacy+fee_sum))>1e-6*max(1,abs(legacy+fee_sum)):raise ValueError('Gross-up expense inventory does not reconcile')
    return {'period':q,'rate':rate,'legacy_base':legacy,'eligible_base':base,'gross_up':charge,'rows':rows}
