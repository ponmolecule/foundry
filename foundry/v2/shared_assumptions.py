"""Reusable non-posting assumption equations over the existing shared-input registry."""
from math import isfinite
from .series import resolve_entered_series

UNITS = {'money', 'money_per_unit', 'count', 'scalar', 'share', 'rate'}
DIMENSIONLESS = {'scalar', 'share', 'rate'}

class SharedAssumptions:
    def __init__(self, assumptions, n, ppy, context=None):
        rows=(assumptions.get('balance_components_model') or {}).get('inputs') or []
        ids=[str(x.get('id') or '') for x in rows]
        if any(not x for x in ids) or len(ids)!=len(set(ids)):
            raise ValueError('Shared assumptions require unique stable IDs')
        self.inputs=dict(zip(ids, rows));self.n=int(n);self.ppy=int(ppy);self.context=context
        if self.ppy not in {4,12}:raise ValueError('Shared assumptions require monthly or quarterly cadence')
        self.months=self.n*12//self.ppy;self.detail=[]

    def evaluate(self, spec, expected, stack=()):
        s=spec or {};src=s.get('source','entered')
        if expected not in UNITS:raise ValueError('Unsupported shared-assumption units')
        if src=='input_ref':
            sid=str(s.get('input_id') or '')
            if sid not in self.inputs:raise ValueError('Missing shared assumption: '+sid)
            if sid in stack:raise ValueError('Circular shared assumption: '+' -> '.join(stack+(sid,)))
            row=self.inputs[sid]
            if row.get('amount_time_basis','none') not in {'none','month','quarter','year'}:
                raise ValueError('Unsupported shared amount time basis')
            if row.get('unit','scalar')!=expected:raise ValueError('Shared-assumption unit mismatch')
            values=self.evaluate(row.get('spec') or {},expected,stack+(sid,))
            self.detail.append({'input_id':sid,'name':row.get('name') or sid,'unit':expected,'values':list(values)})
        elif src=='weighted_sum':
            if s.get('unit',expected)!=expected:raise ValueError('Weighted amount unit mismatch')
            terms=s.get('components') or []
            if not terms:raise ValueError('Weighted amount needs at least one component')
            ids=[str(t.get('id') or '') for t in terms]
            if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Weighted components require unique stable IDs')
            values=[0.]*self.months;weights=[0.]*self.months
            for term in terms:
                amount=self.evaluate(term.get('amount_spec') or {},expected,stack)
                weight=self.evaluate(term.get('weight_spec') or {},'share',stack)
                for i,(a,w) in enumerate(zip(amount,weight)):
                    if w>1:raise ValueError('Component weight must be between 0% and 100%')
                    weights[i]+=w;values[i]+=a*w
                self.detail.append({'component_id':term['id'],'name':term.get('name') or term['id'],
                                    'unit':expected,'amount':amount,'weight':weight,
                                    'weighted_amount':[a*w for a,w in zip(amount,weight)]})
            if any(abs(w-1)>1e-8 for w in weights):
                raise ValueError('Weighted amount shares must total 100% in every month')
        elif src=='entered':
            unit=s.get('unit',expected)
            if unit!=expected:raise ValueError('Entered assumption unit mismatch')
            values=[float(v) for v in resolve_entered_series(s,self.months,12,context=self.context,default_value=0)]
        else:raise ValueError('Unsupported reusable assumption source: '+str(src))
        if any(not isfinite(v) or v<0 for v in values):raise ValueError('Shared assumptions must resolve finite and non-negative')
        for factor in s.get('factors') or []:
            unit=factor.get('unit','scalar')
            if unit not in DIMENSIONLESS:raise ValueError('Assumption factors must be dimensionless')
            f=self.evaluate(factor,unit,stack)
            values=[a*b for a,b in zip(values,f)]
            self.detail.append({'name':factor.get('name') or 'Factor','unit':unit,'values':f})
        if any(not isfinite(v) for v in values):raise ValueError('Shared-assumption product is not finite')
        return values

    def resolve(self,spec,unit):
        vals=self.evaluate(spec,unit)
        self.detail.append({'name':'Resolved amount per customer','unit':unit,'values':list(vals)})
        width=12//self.ppy
        def sample(v):return list(v[width-1::width])
        detail=[{k:sample(v) if isinstance(v,list) else v for k,v in row.items()} for row in self.detail]
        return sample(vals),detail
