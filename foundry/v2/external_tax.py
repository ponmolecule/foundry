"""Opt-in analyst-authored tax provision and settlement rules, in native dollars.

Expressions are a bounded arithmetic grammar, never Python eval. Current bank pretax
is the only endogenous source. Prior(rule, opening) reads committed periods only.
"""
import ast
import math
import re
from .tax_interim import MONEY_SERIES, tax_year
from .other_income import prepare as prepare_flows
from .series import resolve_entered_series

OPS=(ast.Add,ast.Sub,ast.Mult,ast.Div)
FUNCS={'min','max','abs','prior','safe_div'}
RESERVED=FUNCS|{'bank_pretax','periods_per_year','configured_tax_rate'}

def active(a): return a.get('tax_mode','calculated')=='external'
def number(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
        raise ValueError('Tax rule requires finite numeric values')
    return float(v)

def parse(text):
    if not isinstance(text,str) or len(text)>2000: raise ValueError('Tax expression must be text (maximum 2000 characters)')
    try: tree=ast.parse(text,mode='eval').body
    except SyntaxError: raise ValueError('Invalid tax expression syntax') from None
    if len(list(ast.walk(tree)))>150: raise ValueError('Tax expression is too complex')
    def check(n,depth=0):
        if depth>25:raise ValueError('Tax expression nesting is too deep')
        if isinstance(n,ast.Constant):number(n.value)
        elif isinstance(n,ast.Name):pass
        elif isinstance(n,ast.BinOp) and isinstance(n.op,OPS):check(n.left,depth+1);check(n.right,depth+1)
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):check(n.operand,depth+1)
        elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUNCS and not n.keywords:
            if n.func.id=='prior':
                if len(n.args)!=2 or not isinstance(n.args[0],ast.Name):raise ValueError('Use prior(rule_id, opening_value)')
                if not isinstance(n.args[1],(ast.Constant,ast.UnaryOp,ast.Name)):raise ValueError('Prior opening must be a numeric constant or an input')
            elif n.func.id=='safe_div' and len(n.args)!=3:raise ValueError('safe_div requires numerator, denominator, and zero-denominator result')
            elif n.func.id=='abs' and len(n.args)!=1:raise ValueError('abs requires one operand')
            elif n.func.id in {'min','max'} and len(n.args)<2:raise ValueError('min/max require at least two operands')
            for arg in n.args:check(arg,depth+1)
        else:raise ValueError('Tax expressions allow numbers, source IDs, + - * /, min, max, abs and prior only')
    check(tree);return tree

def references(node,lag=False):
    if isinstance(node,ast.Name):return set() if lag else {node.id}
    if isinstance(node,ast.Call):
        if node.func.id=='prior':return references(node.args[1])
        return set().union(*(references(x) for x in node.args))
    return set().union(*(references(x) for x in ast.iter_child_nodes(node)))

def entered_input(x,n,ppy,context=None):
    if x.get('unit','money')=='money' and x.get('measure','flow')=='flow':
        return prepare_flows({'other_income_model':{'lines':[dict(x,classification='other')]}},{},n,ppy,context)[0]['amount']
    spec=x.get('amount_spec') or {}
    if spec.get('trajectory')=='explicit' and spec.get('cadence')=='month' and ppy<12:
        width=12//ppy
        if x.get('unit','money')=='scalar':raise ValueError('Monthly scalar tax schedules require monthly cadence or a coarser authored schedule')
        return resolve_entered_series(spec,n*width,12,context=context)[width-1::width]
    return resolve_entered_series(spec,n,ppy,context=context)

def validate(a,cfg):
    if a.get('tax_mode','calculated') not in {'calculated','external'}:raise ValueError('Tax mode must be calculated or external')
    if not active(a):return
    m=a.get('external_tax')
    if not isinstance(m,dict):raise ValueError('Externally determined tax requires a rule configuration')
    if cfg.get('parity_profile','pf_a')!='pf_a':raise ValueError('Externally determined tax currently requires Profile A; Profile B is unsupported')
    inputs=m.get('inputs',[]);rules=m.get('rules',[])
    if not isinstance(inputs,list) or not isinstance(rules,list) or len(inputs)+len(rules)>100:raise ValueError('Tax inputs and rules must be lists with at most 100 total items')
    ids=set(RESERVED);units={'bank_pretax':'money','periods_per_year':'scalar'}
    for x in inputs+rules:
        if not isinstance(x,dict):raise ValueError('Tax inputs and rules must be objects')
        sid=x.get('id','')
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',sid) or sid in ids:raise ValueError('Tax source/rule IDs must be unique identifiers; built-in names are reserved')
        ids.add(sid)
    for x in inputs:
        if x.get('unit','money') not in {'money','scalar'}:raise ValueError('Tax input units must be money or scalar')
        units[x['id']]=x.get('unit','money')
        if x.get('measure','flow') not in {'flow','level'}:raise ValueError('Tax monetary measure must be flow or level')
        if x.get('source','entered')=='entered':
            if (x.get('amount_spec') or {}).get('source','entered')!='entered':raise ValueError('Use linked source mode for tax links')
            entered_input(x,int(a.get('n_periods',12)),int(a.get('periods_per_year',4)))
        elif x.get('source')=='linked_quantity':
            if x.get('unit','money')!='money' or x.get('measure','flow')!='flow':raise ValueError('Linked tax quantity must be a monetary flow')
            from .other_income import validate as validate_income
            validate_income({'other_income_model':{'lines':[dict(x,classification='other')]},**{k:v for k,v in a.items() if k!='other_income_model'}})
        else:raise ValueError('Tax input source must be entered or linked_quantity')
    input_ids={x['id'] for x in inputs}
    trees={x['id']:parse(x.get('expression','')) for x in rules}
    uses_rate=any(isinstance(node,ast.Name) and node.id=='configured_tax_rate' for t in trees.values() for node in ast.walk(t))
    if uses_rate:
        rate=number(a.get('tax_rate'))
        if not 0<=rate<=1:raise ValueError('Configured tax rate must be between 0 and 1')
        units['configured_tax_rate']='scalar'
    unknown=set().union(*(references(t) for t in trees.values()))-ids if trees else set()
    if unknown:raise ValueError('Unknown tax source/rule: '+', '.join(sorted(unknown)))
    for t in trees.values():
        for node in ast.walk(t):
            if isinstance(node,ast.Call) and node.func.id=='prior':
                if node.args[0].id not in ids-RESERVED:raise ValueError('Prior requires a named tax input or rule')
                if isinstance(node.args[1],ast.Name) and node.args[1].id not in input_ids:raise ValueError('Prior opening must reference an entered or linked input')
    order=[];visiting=set()
    def visit(k):
        if k in visiting:raise ValueError('Circular current-period tax rules: '+k)
        if k in order:return
        visiting.add(k)
        for dep in references(trees[k]):
            if dep in trees:visit(dep)
        visiting.remove(k);order.append(k)
    for k in trees:visit(k)
    def unit(n):
        if isinstance(n,ast.Constant):return 'zero' if n.value==0 else 'scalar'
        if isinstance(n,ast.Name):return units[n.id]
        if isinstance(n,ast.UnaryOp):return unit(n.operand)
        if isinstance(n,ast.Call):
            if n.func.id=='prior':
                u=units.get(n.args[0].id,'money');o=unit(n.args[1])
                if o not in {u,'zero'}:raise ValueError('Prior opening must match the referenced source unit')
                return u
            if n.func.id=='safe_div':
                u,v=unit(n.args[0]),unit(n.args[1])
                if v=='money' and u not in {'money','zero'}:raise ValueError('safe_div cannot divide a scalar by money')
                result='scalar' if u==v else u
                if unit(n.args[2]) not in {result,'zero'}:raise ValueError('safe_div default has incompatible units')
                return result
            us={unit(x) for x in n.args}-{'zero'}
            if len(us)>1:raise ValueError('Tax expression mixes money and scalar operands')
            return next(iter(us),'zero')
        l,r=unit(n.left),unit(n.right)
        if isinstance(n.op,(ast.Add,ast.Sub)):
            if l!=r and 'zero' not in {l,r}:raise ValueError('Tax addition/subtraction requires matching units')
            return r if l=='zero' else l
        if isinstance(n.op,ast.Mult):
            if l==r=='money':raise ValueError('Tax rule cannot multiply money by money')
            return 'money' if 'money' in {l,r} else 'scalar'
        if r=='money' and l not in {'money','zero'}:raise ValueError('Tax rule cannot divide a scalar by money')
        return 'scalar' if l==r else l
    # Prior/self references use the explicitly authored rule unit, checked against expression.
    for x in rules:
        if x.get('unit','money') not in {'money','scalar'}:raise ValueError('Tax rule units must be money or scalar')
        units[x['id']]=x.get('unit','money')
    for k in order:
        u=unit(trees[k])
        if u not in {units[k],'zero'}:raise ValueError('Tax rule unit mismatch: '+k)
    outputs=m.get('outputs') or {}
    for k in ('current','deferred_asset','deferred_liability','payments'):
        val=outputs.get(k)
        if val is None:
            if k=='current':raise ValueError('Choose the current tax provision source')
            continue
        if val not in units or units[val]!='money':raise ValueError('Tax output requires a monetary source/rule: '+k)
    if m.get('payment_mode','same_period') not in {'same_period','scheduled'}:raise ValueError('Tax payments must be same_period or scheduled')
    if m.get('payment_mode')=='scheduled' and not outputs.get('payments'):raise ValueError('Scheduled tax settlement requires a payment source')
    for k in ('opening_payable','opening_deferred_asset','opening_deferred_liability'):
        v=number(m.get(k,0))
        if k!='opening_payable' and v<0:raise ValueError('Deferred tax opening balances cannot be negative')
    if m.get('deferred_mode','none') not in {'none','balances'}:raise ValueError('Deferred-tax mode must be none or balances')
    if m.get('deferred_mode')=='balances' and not (outputs.get('deferred_asset') or outputs.get('deferred_liability')):raise ValueError('Deferred balance mode requires an explicit asset or liability source')
    return trees,order,units

class ExternalTaxLedger:
    external=True
    def __init__(self,cfg,a,ppy,quantities=None):
        self.cfg=cfg;self.a=a;self.ppy=ppy;self.m=a['external_tax'];self.trees,self.order,self.units=validate(a,cfg)
        self.quantities=quantities if quantities is not None else {};self.values={};self.rows=[];self.history={};self.last_period=0
        self.nol=0.;self.dta=self.opening_dta=float(self.m.get('opening_deferred_asset',0)) if self.m.get('deferred_mode')=='balances' else 0.;self.dtl=float(self.m.get('opening_deferred_liability',0)) if self.m.get('deferred_mode')=='balances' else 0.;self.payable=float(self.m.get('opening_payable',0))
        from .growth import growth_context_from_cfg
        n=int(a.get('n_periods',12));ctx=growth_context_from_cfg(cfg,ppy)
        for x in self.m.get('inputs',[]):
            if x.get('source','entered')=='entered':
                self.values[x['id']]=entered_input(x,n,ppy,ctx)
    def evaluate(self,period,pretax):
        if period!=self.last_period+1:raise ValueError('External tax periods must be evaluated and committed in order')
        env={'bank_pretax':number(pretax),'periods_per_year':float(self.ppy)}
        if 'configured_tax_rate' in self.units:env['configured_tax_rate']=number(self.a.get('tax_rate'))
        for x in self.m.get('inputs',[]):
            if x['id'] in self.values:env[x['id']]=self.values[x['id']][period-1]
            else:
                sid=x['source_series_id'];vals=self.quantities.get(sid)
                if vals is None or len(vals)<period:raise ValueError('External tax linked quantity unavailable: '+sid)
                env[x['id']]=number(vals[period-1])*number(x.get('multiplier',1))
        def calc(n):
            if isinstance(n,ast.Constant):return float(n.value)
            if isinstance(n,ast.Name):return env[n.id]
            if isinstance(n,ast.UnaryOp):return -calc(n.operand) if isinstance(n.op,ast.USub) else calc(n.operand)
            if isinstance(n,ast.Call):
                if n.func.id=='prior':return self.history.get(n.args[0].id,calc(n.args[1]))
                args=[calc(x) for x in n.args]
                if n.func.id=='safe_div':return args[0]/args[1] if args[1]!=0 else args[2]
                return {'min':min,'max':max,'abs':abs}[n.func.id](*args) if n.func.id!='abs' else abs(args[0])
            l,r=calc(n.left),calc(n.right)
            if isinstance(n.op,ast.Add):return l+r
            if isinstance(n.op,ast.Sub):return l-r
            if isinstance(n.op,ast.Mult):return l*r
            if r==0:raise ValueError('External tax division by zero; use max(denominator, positive_floor) or a defined rule')
            return l/r
        for k in self.order:env[k]=number(calc(self.trees[k]))
        out=self.m.get('outputs',{});current=env[out['current']]
        dta=env[out['deferred_asset']] if self.m.get('deferred_mode')=='balances' and out.get('deferred_asset') else 0.;dtl=env[out['deferred_liability']] if self.m.get('deferred_mode')=='balances' and out.get('deferred_liability') else 0.
        if dta<0 or dtl<0:raise ValueError('External deferred tax balances cannot be negative')
        deferred=(dtl-self.dtl)-(dta-self.dta)
        payments=current if self.m.get('payment_mode','same_period')=='same_period' else env[out['payments']]
        payable=self.payable+current-payments
        year,closing=tax_year(self.cfg,period,self.ppy);old=self.rows[-1] if self.rows and self.rows[-1]['year']==year else {}
        row={k:0. for k in MONEY_SERIES}
        row.update(period=period,year=year,yearEnd=closing,basis='Externally determined tax',tax=current+deferred,nol=0.,taxCurrent=current,taxDeferred=deferred,dtaGross=dta,dtaVA=0.,dtaNet=dta,taxIncomeYtd=old.get('taxIncomeYtd',0)+pretax,taxCurrentYtd=old.get('taxCurrentYtd',0)+current,taxProvisionYtd=old.get('taxProvisionYtd',0)+current+deferred,payments=payments,settlementNet=payable,taxPayable=max(0.,payable),taxReceivable=max(0.,-payable),deferredLiability=dtl,operands=env)
        return row
    def commit(self,row):
        if row['period']!=self.last_period+1:raise ValueError('External tax cannot commit twice')
        self.rows.append(row);self.last_period=row['period'];self.history=dict(row['operands']);self.dta=row['dtaNet'];self.dtl=row['deferredLiability'];self.payable=row['settlementNet']
    def audit(self):
        return {'method':'external','units':'native dollars; scalar operands dimensionless','source_units':self.units,'sources':[{k:x.get(k) for k in ('id','name','source','source_series_id','measure')} for x in self.m.get('inputs',[])],'rules':self.m.get('rules',[]),'payment_mode':self.m.get('payment_mode','same_period'),'deferred_mode':self.m.get('deferred_mode','none'),'rows':self.rows}

def ledger(cfg,a,ppy,quantities=None):
    if active(a):return ExternalTaxLedger(cfg,a,ppy,quantities)
    from .tax_interim import InterimTaxLedger
    return InterimTaxLedger(cfg,a,ppy)
