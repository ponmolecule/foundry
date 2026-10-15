"""Authoring-only tax blocks compile to the existing validated expression grammar.

No engagement labels, rates, entity lists or amounts are inferred. Planning returns
an isolated candidate; applying it is a separate UI action. Ordinary runs are
unchanged unless the analyst explicitly materializes and selects a block output.
"""
import ast
import copy
import re

KINDS={'loss_carryforward','credit_limit','allocation'}


def _canonical(expression):
    """Compare syntax, not labels; normalize associative sum/product ordering."""
    from .external_tax import parse
    def norm(n):
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Mult)):
            cls=type(n.op);items=[]
            def collect(x):
                if isinstance(x,ast.BinOp) and isinstance(x.op,cls):collect(x.left);collect(x.right)
                else:items.append(norm(x))
            collect(n);return (cls.__name__,tuple(sorted(items,key=repr)))
        if isinstance(n,ast.Call):
            args=[norm(a) for a in n.args]
            if n.func.id in {'min','max'}:args.sort(key=repr)
            return ('call',n.func.id,tuple(args))
        if isinstance(n,ast.Constant):return ('constant',float(n.value))
        if isinstance(n,ast.Name):return ('name',n.id)
        if isinstance(n,ast.BinOp):return (type(n.op).__name__,norm(n.left),norm(n.right))
        if isinstance(n,ast.UnaryOp):return (type(n.op).__name__,norm(n.operand))
        raise ValueError('Unsupported expression')
    return norm(parse(expression))


def _all_refs(expression):
    from .external_tax import parse,FUNCS
    return {n.id for n in ast.walk(parse(expression)) if isinstance(n,ast.Name) and n.id not in FUNCS}


def plan(cfg,draft):
    from .external_tax import validate,CONFIGURED_UNITS,RESERVED
    if not isinstance(cfg,dict) or not isinstance(draft,dict):raise ValueError('Configuration and block choices are required')
    candidate=copy.deepcopy(cfg);a=candidate.get('assumptions') or {}
    if not isinstance(a,dict):raise ValueError('Engagement assumptions must be an object')
    if a.get('tax_mode')!='external':raise ValueError('Select externally determined tax before adding a block')
    validate(a,candidate)
    m=a['external_tax'];blocks=m.get('blocks',[])
    if not isinstance(blocks,list):raise ValueError('Tax blocks must be a list')
    kind=draft.get('kind');name=draft.get('name','')
    if not isinstance(name,str):raise ValueError('Block name must be text')
    name=name.strip()
    if kind not in KINDS:raise ValueError('Choose a supported calculation block')
    if not name or len(name)>100:raise ValueError('Give the block a name of at most 100 characters')
    bid=draft.get('id')
    old=next((b for b in blocks if b.get('id')==bid),None) if bid else None
    if bid and not old:raise ValueError('The block being edited no longer exists')
    used={x['id'] for x in m.get('inputs',[])+m.get('rules',[])}|set(RESERVED)
    if not bid:
        i=1
        while f'tax_block_{i}' in used or any(b.get('id')==f'tax_block_{i}' for b in blocks):i+=1
        bid=f'tax_block_{i}'
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,40}',bid):raise ValueError('Invalid block identifier')
    units={'bank_pretax':'money','periods_per_year':'scalar',**CONFIGURED_UNITS,**{x['id']:x.get('unit','money') for x in m.get('inputs',[])+m.get('rules',[])}}
    labels={'bank_pretax':'Bank pretax income (live)','configured_tax_rate':'Configured tax rate','configured_nol_limit':'Configured NOL utilization limit','configured_opening_nol':'Configured opening NOL','periods_per_year':'Periods per year',**{x['id']:x.get('name') or x['id'] for x in m.get('inputs',[])+m.get('rules',[])}}
    bindings=draft.get('bindings')
    if not isinstance(bindings,dict):raise ValueError('Choose the block sources')
    selected={};constraints=[]
    old_owned=set(old.get('owned_rule_ids',[])) if old else set()
    def source(key,unit,opening=False):
        sid=bindings.get(key)
        if not isinstance(sid,str) or sid not in units:raise ValueError('Choose an available source: '+key.replace('_',' '))
        if units[sid]!=unit:raise ValueError('Incompatible source units: '+key.replace('_',' '))
        if sid in old_owned:raise ValueError('A block cannot consume its own generated outputs')
        if opening:
            x=next((x for x in m.get('inputs',[]) if x['id']==sid),None)
            if sid!='configured_opening_nol' and not (x and x.get('source','entered')=='entered' and x.get('measure','flow')=='level'):
                raise ValueError('Opening losses must be an entered ending-balance source or the configured opening NOL')
        selected[key]=sid;return sid
    # Replacing only owned rules keeps adopted existing rules and all entered data intact.
    m['rules']=[x for x in m.get('rules',[]) if x['id'] not in old_owned]
    generated=[];reused=[];outputs={};by_role={};owned=[]
    def emit(role,title,expression,unit='money'):
        canonical=_canonical(expression)
        match=next((x for x in m['rules'] if x.get('unit','money')==unit and _canonical(x.get('expression','0'))==canonical),None)
        if match:
            sid=match['id'];reused.append({'id':sid,'name':match.get('name') or sid,'role':role});by_role[role]=sid;return sid
        sid=f'{bid}_{role}'
        if sid in used and sid not in old_owned:raise ValueError('Generated rule ID conflicts with an existing source')
        x={'id':sid,'name':name+' · '+title,'unit':unit,'expression':expression}
        m['rules'].append(x);generated.append(x);owned.append(sid);used.add(sid);units[sid]=unit;by_role[role]=sid;return sid
    def bound(sid,lo,hi=None,opening=False):constraints.append({'source':sid,'min':lo,**({'max':hi} if hi is not None else {}),**({'opening_only':True} if opening else {})})
    if kind=='loss_carryforward':
        income=source('taxable_income','money');opening=source('opening_losses','money',True);limit=source('utilization_limit','scalar');rate=source('tax_rate','scalar')
        bound(opening,0,opening=True);bound(limit,0,1);bound(rate,0,1)
        # Stable closing ID permits committed prior-state recurrence without placeholders.
        closing=f'{bid}_closing'
        available=emit('available','Opening losses this period',f'prior({closing}, {opening})')
        positive=emit('positive','Positive taxable income',f'max(0, {income})')
        cap=emit('capacity','Utilization ceiling',f'{positive} * {limit}')
        used_loss=emit('used','Losses utilized',f'min({available}, {cap})')
        new=emit('new','New losses',f'max(0, -{income})')
        end=emit('closing','Closing loss carryforward',f'{available} + {new} - {used_loss}')
        # Closing is recurrence state; it must retain its own ID, never an unrelated equivalent rule.
        if end!=closing:raise ValueError('Closing loss recurrence cannot adopt another rule; choose a different block')
        taxable=emit('taxable','Taxable income after losses',f'{positive} - {used_loss}')
        tax=emit('tax','Tax before credits',f'{taxable} * {rate}')
        outputs={'available':available,'used':used_loss,'new':new,'closing':end,'taxable':taxable,'tax':tax}
        explanation='Losses are tracked each engine period: opening losses + new losses − utilization = closing losses. Positive taxable income is limited by the selected utilization share. This is a period-based pool, not an inferred statutory annual tax calculation.'
    elif kind=='credit_limit':
        tax=source('tax_before_credit','money');threshold=source('threshold','money');share=source('retained_share','scalar')
        bound(tax,0);bound(threshold,0);bound(share,0,1)
        treatment=draft.get('threshold_treatment')
        if treatment not in {'fully_credited','fully_retained'}:raise ValueError('Choose whether tax up to the threshold is fully credited or fully retained')
        excess=emit('excess','Tax above threshold',f'max(0, {tax} - {threshold})')
        if treatment=='fully_credited':
            net=emit('tax','Tax after credit',f'{excess} * {share}')
            credit=emit('credit','Credit applied',f'{tax} - {net}')
        else:
            credit=emit('credit','Credit applied',f'{excess} * (1 - {share})')
            net=emit('tax','Tax after credit',f'{tax} - {credit}')
        outputs={'credit':credit,'tax':net}
        explanation=('Tax up to the threshold is fully credited.' if treatment=='fully_credited' else 'Tax up to the threshold is retained in full.')+' Only the selected share of tax above the threshold remains. The monetary threshold must already use the engine-period amount.'
    else:
        amount=source('amount','money');participants=bindings.get('participants');target=bindings.get('target');method=draft.get('method','positive_income')
        if not isinstance(participants,list) or len(participants)<2 or len(participants)>20 or len(set(participants))!=len(participants):raise ValueError('Choose 2–20 distinct entity income sources')
        if target not in participants:raise ValueError('The receiving entity must be in the comparison set')
        if method not in {'positive_income','signed_income'}:raise ValueError('Choose a supported allocation method')
        bases=[];selected['participants']=list(participants);selected['target']=target
        for i,sid in enumerate(participants):
            if sid not in units or units[sid]!='money' or sid in old_owned:raise ValueError('Each entity must use an available monetary income source')
            bases.append(emit(f'entity_{i+1}','Entity allocation basis '+str(i+1),f'max(0, {sid})') if method=='positive_income' else sid)
        base=emit('base','Allocation base',' + '.join(bases));numerator=bases[participants.index(target)]
        share=emit('share','Entity allocation share',f'safe_div({numerator}, {base}, 0)','scalar')
        tax=emit('tax','Allocated tax',f'{amount} * {share}')
        outputs={'base':base,'share':share,'tax':tax}
        explanation=('Only positive entity income participates.' if method=='positive_income' else 'Signed entity income participates; shares may be negative or exceed 100%.')+' A zero allocation base yields zero allocated tax. The block posts only for the selected receiving entity.'
    record={'threshold_treatment':draft.get('threshold_treatment'),'id':bid,'kind':kind,'name':name,'bindings':selected,'method':draft.get('method','positive_income'),'outputs':outputs,'owned_rule_ids':owned,'rule_ids':list(dict.fromkeys(by_role.values())),'constraints':constraints}
    if old:blocks=[record if b.get('id')==bid else b for b in blocks]
    else:blocks=blocks+[record]
    m['blocks']=blocks
    if draft.get('set_current') is True:m.setdefault('outputs',{})['current']=outputs['tax']
    # Old generated IDs referenced elsewhere may not disappear silently on editing.
    validate(a,candidate)
    # Reject invalid known assumptions during preview; endogenous sources remain
    # checked on every solver evaluation before a period can be committed.
    from .external_tax import entered_input,configured_value
    from .growth import growth_context_from_cfg
    ppy=int(a.get('periods_per_year',4));n=int(a.get('n_periods',12));context=growth_context_from_cfg(candidate,ppy)
    input_map={x['id']:x for x in m.get('inputs',[])}
    for constraint in constraints:
        sid=constraint['source'];values=None
        if sid in CONFIGURED_UNITS:values=[configured_value(a,sid)]
        elif sid in input_map and input_map[sid].get('source','entered')=='entered':values=entered_input(input_map[sid],n,ppy,context)
        if values is not None:
            check=[values[0]] if constraint.get('opening_only') else values
            if any(v<constraint.get('min',float('-inf')) or v>constraint.get('max',float('inf')) for v in check):raise ValueError('Block source is outside its allowed range: '+labels.get(sid,sid))
    result={'cfg':candidate,'block':record,'summary':{'name':name,'explanation':explanation,'generated':generated,'reused':reused,'outputs':[{'role':k,'id':v,'name':next((x['name'] for x in m['rules'] if x['id']==v),labels.get(v,v))} for k,v in outputs.items()], 'preserved_inputs':len(m.get('inputs',[])),'removed_rules':[],'current_before':cfg['assumptions']['external_tax'].get('outputs',{}).get('current'),'current_after':m.get('outputs',{}).get('current')}}
    return result


def validate_blocks(m,units):
    from .external_tax import number
    blocks=m.get('blocks',[])
    if not isinstance(blocks,list) or len(blocks)>20:raise ValueError('Tax blocks must be a list of at most 20 blocks')
    seen=set()
    for b in blocks:
        if not isinstance(b,dict):raise ValueError('Tax block must be an object')
        bid=b.get('id')
        if not isinstance(bid,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,40}',bid) or b.get('kind') not in KINDS or bid in seen:raise ValueError('Invalid or duplicate tax calculation block')
        seen.add(bid)
        if not isinstance(b.get('name'),str):raise ValueError('Tax block needs a name')
        rules=b.get('rule_ids',[]);constraints=b.get('constraints',[])
        if not isinstance(rules,list) or len(rules)>100 or not isinstance(constraints,list) or len(constraints)>20:raise ValueError('Invalid block rule or constraint list')
        for sid in rules:
            if not isinstance(sid,str) or sid not in units:raise ValueError('Tax block rule is missing; rebuild the block')
        for c in constraints:
            if not isinstance(c,dict) or not isinstance(c.get('source'),str) or c['source'] not in units:raise ValueError('Tax block source is missing; rebuild the block')
            for k in ('min','max'):
                if k in c:number(c[k])
            if c.get('min',float('-inf'))>c.get('max',float('inf')):raise ValueError('Invalid block constraint range')


def check_values(m,env,period):
    for b in m.get('blocks',[]):
        for c in b.get('constraints',[]):
            if c.get('opening_only') and period!=1:continue
            value=env[c['source']]
            if value<c.get('min',float('-inf')) or value>c.get('max',float('inf')):
                raise ValueError('Tax block '+b['name']+': source '+c['source']+' is outside its allowed range')
