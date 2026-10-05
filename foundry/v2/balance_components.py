"""Named balance components: typed stock formulas and explicit accounting destinations.

Legacy interest_balance_model remains a separate, unchanged compatibility contract.
No source-model product names, customer terminology or fixed component count live here.
"""
from copy import deepcopy
from math import isfinite
from .series import resolve_entered_series
from .interest_balances import interest_balance_amount

TREATMENTS = {'cash_allocation', 'residual_cash', 'earning_asset', 'off_book'}


def validate_model(a):
    m=a.get('balance_components_model') or {}
    if not m or m.get('enabled') is False:return
    if (a.get('interest_balance_model') or {}).get('enabled', True) and a.get('interest_balance_model'):
        raise ValueError('Choose the legacy balances model or named balance components, not both')
    inputs=m.get('inputs') or []
    ids=[str(x.get('id') or '') for x in inputs]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):raise ValueError('Shared balance inputs require unique stable IDs')
    comps=m.get('components') or [];ids=[str(x.get('id') or '') for x in comps]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):raise ValueError('Balance components require unique stable IDs')
    if sum(x.get('treatment')=='residual_cash' for x in comps)>1:raise ValueError('Only one component can own residual cash')
    for c in comps:
        if c.get('treatment') not in TREATMENTS:raise ValueError('Unknown balance-component accounting treatment')
        for k in ('opening_balance','risk_weight'):
            v=float(c.get(k) or 0)
            if not isfinite(v) or v<0:raise ValueError('Balance component '+k+' must be finite and non-negative')
        if float(c.get('risk_weight') or 0)>2.5:raise ValueError('Balance-component risk weight exceeds 250%')
        if c.get('interest_balance_measure','current_end') not in {'current_end','prior_end','average'}:raise ValueError('Invalid balance-component interest measurement')
        if c.get('income_line','interest') not in {'interest','fee'}:raise ValueError('Invalid balance-component income destination')
        if c.get('cost_line','interest_expense') not in {'interest_expense','operating_expense'}:raise ValueError('Invalid balance-component cost destination')
        for k in ('interest_start_period',):
            if k in c and (isinstance(c[k],bool) or not isinstance(c[k],int) or c[k]<1):raise ValueError('Interest start must be a positive model period')
        start=c.get('start_period',1)
        if isinstance(start,bool) or not isinstance(start,int) or start<1:raise ValueError('Balance-component start period must be a positive integer')
        if c.get('treatment')=='residual_cash' and (c.get('income_line','interest')!='interest' or c.get('cost_spec')):raise ValueError('Residual cash earns interest only; assign costs to an independently sourced component')


class BalanceComponents:
    def __init__(self,a,counts,quantities,n,ppy,context=None):
        validate_model(a);self.model=deepcopy(a['balance_components_model']);self.n=n;self.ppy=float(ppy)
        self.counts=counts;self.quantities=quantities;self.context=context;self.cache={}
        self.inputs={x['id']:x for x in self.model.get('inputs') or []}
        self.components=self.model.get('components') or []
        self.rows={c['id']:{'id':c['id'],'name':c.get('name') or 'Balance component','treatment':c['treatment'],
                           'income_line':c.get('income_line','interest'),'cost_line':c.get('cost_line','interest_expense'),
                           'risk_weight':float(c.get('risk_weight') or 0),'opening':float(c.get('opening_balance') or 0),
                           'ending':[],'interest_balance':[],'annual_rate':[],'annual_cost_rate':[],'income':[],'cost':[]} for c in self.components}
        from .source_catalog import catalog
        self.meta={x['series_id']:x for x in catalog(a) if x.get('driver')=='fee_stream_quantity'}
        # Eager traversal catches broken/cyclic inputs before solving or publishing numbers.
        for x in self.inputs.values():
            spec=x.get('spec') or {}
            self.check_spec(spec,set())
            declared=x.get('unit','scalar')
            if declared not in {'money','count','scalar','rate','share','money_per_unit'}:
                raise ValueError('Unknown shared assumption unit')
            if spec.get('source','entered')!='entered' and self.unit(spec)!=declared:
                raise ValueError('Shared assumption unit does not match its source')
        for c in self.components:
            for t in c.get('terms') or []:
                self.check_spec(t.get('source_spec') or {},set())
                for f in t.get('factors') or []:self.check_spec(f,set())
            for key in ('yield_spec','cost_spec'):
                spec=c.get(key) or {'value':0}
                self.check_spec(spec,set())
                if self.unit(spec) not in {'rate','scalar','share'}:
                    raise ValueError('Annual income/cost rate must be dimensionless')
            for t in c.get('terms') or []:
                source=t.get('source_spec') or {}
                u=self.unit(source)
                if source.get('source','entered')=='entered' and 'unit' not in source:u='money'
                dimensional=[self.unit(f) for f in t.get('factors') or [] if self.unit(f) not in {'scalar','rate','share'}]
                if (u=='count' and dimensional!=['money_per_unit']) or (u=='money' and dimensional) or u not in {'count','money'}:
                    raise ValueError('Balance formula must resolve to money: count × balance per unit, or money × dimensionless factors')


    def check_spec(self,s,seen):
        src=s.get('source','entered')
        if src=='input_ref':
            sid=s.get('input_id')
            if sid not in self.inputs:raise ValueError('Missing shared balance input: '+str(sid))
            if sid in seen:raise ValueError('Circular shared balance input: '+str(sid))
            self.check_spec(self.inputs[sid].get('spec') or {},seen|{sid})
        elif src=='fee_stream_quantity':
            sid=s.get('series_id')
            if sid not in self.quantities or len(self.quantities[sid])!=self.n:raise ValueError('Unavailable balance-component fee quantity: '+str(sid))
            unit=(self.meta.get(sid) or {}).get('unit')
            if unit not in {'count','money_stock'}:raise ValueError('A stock formula needs a count or monetary balance source, not a monetary flow')
            if s.get('unit') and s['unit']!=('count' if unit=='count' else 'money'):raise ValueError('Balance source unit does not match linked quantity')
        elif src=='customer_count':
            sid=s.get('series_id');measure=s.get('measure','period_end')
            if sid not in self.counts or measure not in self.counts[sid]:raise ValueError('Unavailable customer-count balance source: '+str(sid))
        elif src=='bank_series':
            sid=s.get('series_id')
            allowed={'equity','total_assets','deposits'}
            if sid not in allowed or s.get('timing','prior_period') not in {'prior_period','current_period'}:raise ValueError('Unsupported balance-component bank source')
            if s.get('timing')=='current_period' and sid!='deposits':raise ValueError('Current equity/assets are circular; use prior-period stock')
            if s.get('prior_initialization','opening') not in {'opening','zero'}:raise ValueError('Invalid prior-period initialization')
        elif src=='entered':
            key=repr(s)
            if key not in self.cache:
                vals=[float(x) for x in resolve_entered_series(s,self.n,int(self.ppy),context=self.context,default_value=0)]
                if len(vals)!=self.n or any(not isfinite(x) or x<0 for x in vals):raise ValueError('Balance-component assumption must be finite and non-negative')
                self.cache[key]=vals
        else:raise ValueError('Unsupported balance-component source: '+str(src))

    def unit(self,s):
        src=s.get('source','entered')
        if src=='input_ref':return self.inputs[s['input_id']].get('unit','scalar')
        if src=='customer_count':return 'count'
        if src=='fee_stream_quantity':return 'count' if self.meta[s['series_id']]['unit']=='count' else 'money'
        if src=='bank_series':return 'money'
        return s.get('unit','scalar')

    def value(self,s,i,bank):
        src=s.get('source','entered')
        if src=='input_ref':return self.value(self.inputs[s['input_id']]['spec'],i,bank)
        if src=='fee_stream_quantity':return float(self.quantities[s['series_id']][i])
        if src=='customer_count':return float(self.counts[s['series_id']][s.get('measure','period_end')][i])
        if src=='bank_series':
            if i==0 and s.get('timing','prior_period')=='prior_period' and s.get('prior_initialization')=='zero':return 0.
            return float(bank[(s.get('timing','prior_period'),s['series_id'])])
        return self.cache[repr(s)][i]

    def opening_totals(self):
        return {kind:sum(r['opening'] for r in self.rows.values() if r['treatment']==kind) for kind in TREATMENTS}

    def set_opening_cash(self,cash):
        alloc=self.opening_totals()['cash_allocation']
        if alloc>cash+1e-6:raise ValueError('Opening allocated cash exceeds available cash')
        for r in self.rows.values():
            if r['treatment']=='residual_cash':r['opening']=max(0.,cash-alloc)

    def stocks(self,i,bank):
        vals={}
        for c in self.components:
            if c['treatment']=='residual_cash':continue
            value=0.
            if i+1>=c.get('start_period',1):
                for t in c.get('terms') or []:
                    v=self.value(t.get('source_spec') or {},i,bank)
                    for factor in t.get('factors') or []:v*=self.value(factor,i,bank)
                    value+=v
            if not isfinite(value) or value<0:raise ValueError('Invalid balance for component '+c['id'])
            vals[c['id']]=value
        return vals

    def period(self,i,bank,stocks,cash,residual_rate,prior_cash):
        allocated=sum(stocks.get(c['id'],0) for c in self.components if c['treatment']=='cash_allocation')
        if allocated>cash+1e-6:raise ValueError('Allocated cash exceeds available cash')
        out=[];has_residual=False
        for c in self.components:
            r=self.rows[c['id']];stock=stocks.get(c['id'],0.)
            if c['treatment']=='residual_cash':stock=max(0.,cash-allocated);has_residual=True
            prior=r['ending'][-1] if r['ending'] else r['opening']
            measure=interest_balance_amount(stock,prior,c.get('interest_balance_measure','current_end'))
            rate=self.value(c.get('yield_spec') or {'value':0},i,bank)
            cost_rate=self.value(c.get('cost_spec') or {'value':0},i,bank)
            income=measure*rate/self.ppy if i+1>=c.get('interest_start_period',c.get('start_period',1)) else 0.
            cost=measure*cost_rate/self.ppy if i+1>=c.get('start_period',1) else 0.
            if not isfinite(income+cost):raise ValueError('Non-finite component income/cost')
            out.append(dict(id=c['id'],ending=stock,interest_balance=measure,annual_rate=rate,annual_cost_rate=cost_rate,income=income,cost=cost,
                            income_line=c.get('income_line','interest'),cost_line=c.get('cost_line','interest_expense')))
        unassigned=0.
        if not has_residual:
            prior_alloc=sum((self.rows[c['id']]['ending'][-1] if self.rows[c['id']]['ending'] else self.rows[c['id']]['opening']) for c in self.components if c['treatment']=='cash_allocation')
            unassigned=((cash-allocated)+max(0.,prior_cash-prior_alloc))/2*residual_rate/self.ppy
        return out,unassigned

    def commit(self,rows):
        for x in rows:
            row=self.rows[x['id']]
            for k in ('ending','interest_balance','annual_rate','annual_cost_rate','income','cost'):row[k].append(x[k])

    def audit(self):return {'components':list(self.rows.values())}


def prepare(a,counts,quantities,n,ppy,context=None):
    m=a.get('balance_components_model') or {}
    return BalanceComponents(a,counts,quantities,n,ppy,context) if m and m.get('enabled') is not False else None


def legacy_to_components(legacy):
    """Lossless operands adapter; adoption is explicit, never a render/import mutation."""
    m=deepcopy(legacy or {});flat=lambda v:{'source':'entered','trajectory':'flat','value':v}
    inputs=[]
    def add(sid,name,unit,spec):
        inputs.append({'id':sid,'name':name,'unit':unit,'spec':deepcopy(spec or flat(0))})
        return {'source':'input_ref','input_id':sid}
    src=m.get('mab_source') or {}
    activity=deepcopy(m.get('mab_spec') or flat(0))
    if src.get('source') in {'link','fee_stream_quantity'}:
        activity={**src,'source':'customer_count' if src['source']=='link' else 'fee_stream_quantity','unit':'count'}
    count=add('activity','Customer activity','count',activity)
    policy=add('policy-rate','Reference yield','rate',m.get('scenario_rate_spec'))
    cost=add('customer-cost','Customer cost rate','rate',m.get('customer_cost_rate_spec'))
    comps=[]
    def component(sid,name,kind,terms,yield_spec,**extra):
        c={'id':sid,'name':name,'treatment':kind,'opening_balance':0,'risk_weight':0 if kind=='off_book' else .2,
           'start_period':1,'interest_balance_measure':'current_end','yield_spec':deepcopy(yield_spec),'terms':terms,**extra};comps.append(c);return c
    for sid,name,share,balance in [('customer-balance','Customer-linked balance','deposit_attach_rate_spec','avg_noninterest_balance_per_mab_spec'),('customer-paid-balance','Customer-linked balance with cost','boost_attach_rate_spec','avg_interest_balance_per_mab_spec')]:
        f1=add(sid+'-share','Participation share','scalar',m.get(share));f2=add(sid+'-amount','Balance per customer','money_per_unit',m.get(balance))
        c=component(sid,name,'off_book',[{'source_spec':count,'factors':[f1,f2]}],policy)
        if sid=='customer-paid-balance':c['cost_spec']=cost
    component('cash-allocation','Cash allocation','cash_allocation',[{'source_spec':{'source':'bank_series','series_id':'equity','timing':'prior_period','prior_initialization':'zero'},'factors':[m.get('operating_cash_ratio_spec') or flat(0)]}],m.get('operating_cash_yield_spec') or flat(0),interest_balance_measure=m.get('operating_cash_interest_basis','current_end'))
    component('earning-asset','Other earning asset','earning_asset',[{'source_spec':{'source':'bank_series','series_id':'equity','timing':'prior_period','prior_initialization':'zero'},'factors':[m.get('frb_stock_ratio_spec') or flat(0)]}],m.get('frb_stock_yield_spec') or flat(0),risk_weight=1.)
    component('remaining-cash','Remaining cash','residual_cash',[],policy,interest_balance_measure=m.get('affiliated_cash_interest_basis','current_end'),interest_start_period=max(1,int(m.get('affiliated_cash_interest_start_period') or 1)))
    return {'enabled':m.get('enabled',True),'inputs':inputs,'components':comps}
