"""Stable quantity links across fee-product owners; quantities, never revenue.

Opt-in: configurations without fee_stream_quantity drivers use the old evaluator.
All stream nodes are sorted, allowing A -> B -> A across owners when the actual
stream dependency graph is acyclic. Owner balances are prepared before quantities.
"""
import copy

def has_links(a):
    return any((s.get('driver') or {}).get('source')=='fee_stream_quantity'
               for key in ('obs_exposures','deposit_products','lending_products')
               for p in a.get(key) or [] for s in p.get('fee_streams') or [])

class FeeLinkPlan:
    def __init__(self,a):
        from .income_modules import fee_quantity_kind
        self.products=a.get('obs_exposures') or []
        self.nodes={};self.ids={};self.local={};self.deps={};self.kinds={}
        for key in ('deposit_products','lending_products'):
            if any((s.get('driver') or {}).get('source')=='fee_stream_quantity' for p in a.get(key) or [] for s in p.get('fee_streams') or []):
                raise ValueError('Linked fee-stream quantities are authored on Fee Products; deposit/lending links use their existing typed selectors')
        all_ids={}
        for key in ('obs_exposures','deposit_products','lending_products'):
            for p in a.get(key) or []:
                for st in p.get('fee_streams') or []:
                    sid=str(st.get('quantity_series_id') or '').strip()
                    if sid:
                        if sid in all_ids:raise ValueError('Fee quantity series IDs must be unique: '+sid)
                        all_ids[sid]=st
        for pi,p in enumerate(self.products):
            names={}
            for si,st in enumerate(p.get('fee_streams') or []):
                node=(pi,si);self.nodes[node]=st
                names.setdefault(str(st.get('name') or ''),[]).append(node)
                sid=str(st.get('quantity_series_id') or '').strip()
                if sid:self.ids[sid]=node
            self.local[pi]=names
        for node,st in self.nodes.items():
            d=st.get('driver') or {};source=d.get('source');ref=str(d.get('ref') or '').strip();dep=None
            if source=='fee_stream_quantity':
                dep=self.ids.get(ref)
                if dep is None:raise ValueError('Linked fee quantity source is missing: '+ref)
                sb=self.nodes[dep].get('basis');basis=st.get('basis')
                if sb not in {'balance','transaction','account'} or basis not in {'balance','transaction','account'}:
                    raise ValueError('Flat/event fee streams cannot supply or consume a linked quantity')
                if basis=='balance' and sb!='balance':raise ValueError('A balance requires a stock quantity, not a transaction flow or account count')
                if basis=='account' and sb!='account':raise ValueError('An account stream requires an account-count quantity')
            elif source=='stream_ref':
                hits=self.local[node[0]].get(ref,[])
                if len(hits)!=1:raise ValueError('Same-product fee reference is missing or ambiguous: '+ref)
                dep=hits[0]
            self.deps[node]=dep
        self.order=[];visiting=set();done=set()
        def visit(node):
            if node in done:return
            if node in visiting:raise ValueError('Fee quantity dependency cycle detected')
            visiting.add(node)
            if self.deps[node] is not None:visit(self.deps[node])
            visiting.remove(node);done.add(node);self.order.append(node)
        for node in self.nodes:visit(node)
        for node in self.order:
            st=self.nodes[node];d=st.get('driver') or {};params=d.get('params') or {};basis=st.get('basis');src=d.get('source','constant');coef=params.get('coefficient') or {}
            kind=fee_quantity_kind(st,self.kinds.get(self.deps[node],'native'))
            self.kinds[node]=kind
            if src=='fee_stream_quantity' and (st.get('rate') or {}).get('behavior')=='durbin_capped':
                if kind=='money':raise ValueError('Durbin pricing requires transaction counts, not monetary throughput')
                if not st.get('quantity_series_id'):raise ValueError('A linked Durbin stream requires its own quantity_series_id')

    def evaluate(self,contexts,n,ppy):
        from .income_modules import fee_stream_q
        totals={(pi,q):[0.,0.] for pi,_ in enumerate(self.products) for q in range(1,n+1)}
        definitions={sid:self.nodes[node] for sid,node in self.ids.items()}
        for q in range(1,n+1):
            for pi in range(len(self.products)):
                ctx=contexts[(pi,q)];ctx['stream_qty']={};ctx['stream_defs']={str(s.get('name') or ''):s for s in self.products[pi].get('fee_streams') or []}
                ctx['linked_stream_defs']=definitions;ctx['linked_stream_qty']=ctx['capture_stream_qty']
            for node in self.order:
                pi,si=node;ctx=contexts[(pi,q)];st=self.nodes[node];sid=str(st.get('quantity_series_id') or '').strip()
                if sid:
                    arr=ctx['capture_stream_qty'].setdefault(sid,[0.]*n)
                    while len(arr)<n:arr.append(0.)
                drv=st.get('driver') or {};coef=(drv.get('params') or {}).get('coefficient') or {}
                if coef.get('kind')=='pct' and not coef.get('semantics'):
                    st=copy.deepcopy(st);dep=self.deps[node];kind=self.kinds.get(dep,'count' if drv.get('source')=='customer_acquisition_count' else 'native')
                    st['driver']['params']['coefficient']['semantics']='share' if kind=='count' else 'flow'
                inc,cost=fee_stream_q(st,q,ctx,ppy)
                totals[(pi,q)][0]+=inc;totals[(pi,q)][1]+=cost
        return totals
