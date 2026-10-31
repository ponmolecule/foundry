"""Stable quantity links across all product owners; quantities, never revenue.

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
        self.products=[];self.owners={};self.families={}
        for key in ('obs_exposures','deposit_products','lending_products'):
            for i,p in enumerate(a.get(key) or []):
                pi=len(self.products);self.products.append(p)
                self.owners[(key,i)]=pi;self.families[pi]=key
        self.nodes={};self.ids={};self.local={};self.deps={};self.kinds={}
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
        for node,dep in self.deps.items():
            if dep is not None and (self.nodes[node].get('driver') or {}).get('source')=='fee_stream_quantity' and not self.exportable(dep):
                raise ValueError('A linked stream cannot export a retention-pool balance before its bank-state allocation; use the published deposit/pool balance formula source instead')
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

    def exportable(self,node):
        """Pool balance quantities are provisional until the bank-state loop."""
        seen=set()
        while node not in seen:
            seen.add(node);owner=self.products[node[0]]
            source=(self.nodes[node].get('driver') or {}).get('source')
            if self.families[node[0]]=='deposit_products' and owner.get('balance_mode')=='pool' and source in {'own_balance','distributed_balance'}:return False
            if self.deps[node] is None:return True
            node=self.deps[node]
        return True  # DFS reports cycles separately, with a precise message.

    def evaluate(self,contexts,n,ppy,*,completed=None,require_complete=True):
        """Evaluate ready nodes once. Contexts arrive as parent balances are projected.

        Upstream fee quantities can feed deposit/lending balances before all loan
        contexts exist; unresolved nodes wait, never publish fabricated zeroes.
        """
        from .income_modules import fee_stream_q
        completed=set() if completed is None else completed
        totals={}
        definitions={sid:self.nodes[node] for sid,node in self.ids.items()}
        for q in range(1,n+1):
            for node in self.order:
                pi,si=node;key=(node,q);dep=self.deps[node]
                if key in completed or (pi,q) not in contexts or (dep is not None and (dep,q) not in completed):continue
                ctx=contexts[(pi,q)];st=self.nodes[node];sid=str(st.get('quantity_series_id') or '').strip()
                ctx.setdefault('stream_qty',{})
                ctx['stream_defs']={str(s.get('name') or ''):s for s in self.products[pi].get('fee_streams') or []}
                ctx['linked_stream_defs']=definitions;ctx['linked_stream_qty']=ctx['capture_stream_qty']
                if sid:
                    arr=ctx['capture_stream_qty'].setdefault(sid,[0.]*n)
                    while len(arr)<n:arr.append(0.)
                drv=st.get('driver') or {};coef=(drv.get('params') or {}).get('coefficient') or {}
                if coef.get('kind')=='pct' and not coef.get('semantics'):
                    st=copy.deepcopy(st);kind=self.kinds.get(dep,'count' if drv.get('source')=='customer_acquisition_count' else 'native')
                    st['driver']['params']['coefficient']['semantics']='share' if kind=='count' else 'flow'
                inc,cost=fee_stream_q(st,q,ctx,ppy)
                total=totals.setdefault((pi,q),[0.,0.]);total[0]+=inc;total[1]+=cost
                completed.add(key)
        if require_complete and len(completed)!=len(self.nodes)*n:
            raise ValueError('Linked stream evaluation is incomplete: a parent balance or source quantity is not available')
        return totals
