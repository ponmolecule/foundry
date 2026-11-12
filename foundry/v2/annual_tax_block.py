"""Reusable authoring block: actual-YTD state/federal provision, prior-year NOL.

Compiles to the existing expression ledger. No forecast tax amounts or client
labels are inferred. Annual tax-year boundaries come from the model calendar.
"""
import ast
import copy
import re
from .tax_interim import tax_year
from .timebase import model_period_end_date


def validate_calendar(a, cfg):
    end = (a.get('tax_policy') or {}).get('fiscal_year_end_month', 12)
    ppy = a.get('periods_per_year', 4)
    if type(end) is not int or not 1 <= end <= 12 or ppy not in (4, 12):
        raise ValueError('Select a valid tax year end and monthly or quarterly cadence')
    if ppy == 4 and end % 3:
        raise ValueError('Quarterly tax years must end on a calendar quarter boundary')
    first = model_period_end_date(cfg, 1, ppy)
    if (first.month - 12//ppy - end) % 12:
        raise ValueError('Annual state/federal tax requires forecast to begin at tax-year start; earlier tax-year results cannot be assumed zero')


def start_flag(cfg, a, period, ppy):
    end = (a.get('tax_policy') or {}).get('fiscal_year_end_month', 12)
    return float(period == 1 or tax_year(cfg, period, ppy, end)[0] != tax_year(cfg, period-1, ppy, end)[0])


def plan_annual(cfg, draft):
    from .external_tax import validate, CONFIGURED_UNITS, RESERVED, entered_input, configured_value
    from .tax_blocks import _canonical
    c = copy.deepcopy(cfg)
    a = c.get('assumptions') or {}
    if a.get('tax_mode') != 'external':
        raise ValueError('Select externally determined tax before configuring this block')
    validate(a,c)
    m = a['external_tax']
    blocks = m.get('blocks', [])
    bid = draft.get('id')
    old = next((x for x in blocks if x.get('id') == bid), None) if bid else None
    if bid and not old:
        raise ValueError('The block being edited is no longer available')
    if any(x.get('kind') == 'annual_state_federal' and x.get('id') != bid for x in blocks):
        raise ValueError('Edit the existing annual state/federal block instead of creating a duplicate')
    name = draft.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>100:
        raise ValueError('Give this calculation a name of at most 100 characters')
    end = draft.get('fiscal_year_end_month')
    if type(end) is not int:
        raise ValueError('Choose the tax year end')
    deduct = draft.get('deduct_state')
    if type(deduct) is not bool:
        raise ValueError('Choose whether state tax reduces federal taxable income')
    a.setdefault('tax_policy', {})['fiscal_year_end_month'] = end
    validate_calendar(a,c)
    used = {x['id'] for x in m.get('inputs', []) + m.get('rules', [])} | set(RESERVED)
    if not bid:
        i=1
        while any(x.get('id')==f'annual_tax_{i}' for x in blocks) or any(x.startswith(f'annual_tax_{i}_') for x in used): i+=1
        bid=f'annual_tax_{i}'
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,40}',bid):
        raise ValueError('Invalid block identifier')
    units = {'bank_pretax':'money', **CONFIGURED_UNITS,
             **{x['id']:x.get('unit','money') for x in m.get('inputs', [])+m.get('rules', [])}}
    labels = {'bank_pretax':'Bank pretax income (live)', 'configured_tax_rate':'Configured federal tax rate',
              'configured_nol_limit':'Configured NOL utilization limit', 'configured_opening_nol':'Configured opening NOL',
              **{x['id']:x.get('name') or x['id'] for x in m.get('inputs', [])+m.get('rules', [])}}
    b = draft.get('bindings') or {}
    selected={}
    def source(key, unit, opening=False):
        sid=b.get(key)
        if not isinstance(sid,str) or units.get(sid)!=unit:
            raise ValueError('Choose an available '+key.replace('_',' '))
        if sid in set((old or {}).get('owned_rule_ids', [])):
            raise ValueError('An annual block cannot consume its own generated outputs')
        if opening:
            x=next((x for x in m.get('inputs',[]) if x['id']==sid),None)
            if sid!='configured_opening_nol' and not (x and x.get('source','entered')=='entered' and x.get('measure')=='level'):
                raise ValueError('Opening NOL must be an entered historical balance')
        selected[key]=sid
        return sid
    income=source('taxable_income','money')
    state=source('state_rate','scalar')
    federal=source('federal_rate','scalar')
    opening=source('opening_losses','money',True)
    limit=source('utilization_limit','scalar')
    constraints=[dict(source=state,min=0,max=1),dict(source=federal,min=0,max=1),
                 dict(source=limit,min=0,max=1),dict(source=opening,min=0,opening_only=True)]
    old_owned=set((old or {}).get('owned_rule_ids', []))
    m['rules']=[x for x in m.get('rules', []) if x['id'] not in old_owned]
    generated=[];reused=[];owned=[];by_role={}
    # Reuse an already authored calendar flag only when its entire resolved path
    # equals the model calendar. Reused expressions migrate to the live calendar.
    n=int(a.get('n_periods',12));ppy=int(a.get('periods_per_year',4))
    from .growth import growth_context_from_cfg
    ctx=growth_context_from_cfg(c,ppy)
    flags={x['id'] for x in m.get('inputs',[]) if x.get('unit')=='scalar' and x.get('source','entered')=='entered'
           and entered_input(x,n,ppy,ctx)==[start_flag(c,a,i,ppy) for i in range(1,n+1)]}
    def canonical(expr, self_id, desired_id):
        tree=ast.parse(expr,mode='eval')
        class Rename(ast.NodeTransformer):
            def visit_Name(self,node):
                return ast.copy_location(ast.Name(id=desired_id if node.id==self_id else 'tax_year_start' if node.id in flags else node.id,ctx=node.ctx),node)
        return _canonical(ast.unparse(Rename().visit(tree)))
    def emit(role,title,expr):
        sid=f'{bid}_{role}'
        match=next((x for x in m['rules'] if x.get('unit','money')=='money' and canonical(x['expression'],x['id'],sid)==_canonical(expr)),None)
        if match:
            previous=match['expression']
            # Keep the stable existing ID, including self-recurrence references.
            tree=ast.parse(expr,mode='eval')
            class Self(ast.NodeTransformer):
                def visit_Name(self,node):
                    return ast.copy_location(ast.Name(id=match['id'] if node.id==sid else node.id,ctx=node.ctx),node)
            match['expression']=ast.unparse(Self().visit(tree).body)
            reused.append(dict(id=match['id'],name=match.get('name') or match['id'],role=role,
                               expression=match['expression'],previous_expression=previous))
            sid=match['id']
        else:
            if sid in used and sid not in old_owned:
                raise ValueError('Generated annual tax rule conflicts with an existing identifier')
            row=dict(id=sid,name=name.strip()+' · '+title,unit='money',expression=expr)
            m['rules'].append(row);generated.append(row);owned.append(sid);used.add(sid)
        by_role[role]=sid
        return sid
    ytd=emit('income_ytd','Pretax income YTD',f'{income} + (1-tax_year_start)*prior({bid}_income_ytd,0)')
    sy=emit('state_ytd','State provision YTD',f'max(0,{ytd}*{state})')
    sp=emit('state_period','State provision this period',f'{sy}-(1-tax_year_start)*prior({sy},0)')
    base=emit('federal_base','Federal income before NOL YTD',f'{ytd}-{sy}' if deduct else ytd)
    no=emit('opening_nol','NOL at tax-year opening',f'tax_year_start*prior({bid}_closing,{opening})+(1-tax_year_start)*prior({bid}_opening_nol,{opening})')
    used_nol=emit('used_nol','Prior-year NOL used YTD',f'min({no},max(0,{base})*{limit})')
    close=emit('closing','NOL remaining and current-year losses',f'{no}+max(0,-{base})-{used_nol}')
    # Closing recurrence must resolve to the actual adopted rule ID.
    for r in m['rules']:
        if r['id']==no:r['expression']=r['expression'].replace(f'{bid}_closing',close)
    fy=emit('federal_ytd','Federal provision YTD',f'(max(0,{base})-{used_nol})*{federal}')
    fp=emit('federal_period','Federal provision this period',f'{fy}-(1-tax_year_start)*prior({fy},0)')
    total=emit('tax','Combined current provision',f'{sp}+{fp}')
    outputs=dict(tax=total,state=sp,federal=fp,closing=close,used=used_nol,opening=no,
                 taxable=base,state_ytd=sy,federal_ytd=fy,income_ytd=ytd)
    record=dict(id=bid,kind='annual_state_federal',name=name.strip(),bindings=selected,
                fiscal_year_end_month=end,deduct_state=deduct,outputs=outputs,
                owned_rule_ids=owned,rule_ids=list(dict.fromkeys(by_role.values())),constraints=constraints)
    m['blocks']=[record if x.get('id')==bid else x for x in blocks] if old else blocks+[record]
    before=(cfg['assumptions']['external_tax'].get('outputs') or {}).get('current')
    if draft.get('set_current') is True:m.setdefault('outputs',{})['current']=total
    validate(a,c)
    for check in constraints:
        sid=check['source'];x=next((x for x in m.get('inputs',[]) if x['id']==sid),None)
        vals=[configured_value(a,sid)] if sid in CONFIGURED_UNITS else entered_input(x,n,ppy,ctx) if x and x.get('source','entered')=='entered' else None
        if vals is not None and any(v<check['min'] or v>check.get('max',float('inf')) for v in (vals[:1] if check.get('opening_only') else vals)):
            raise ValueError('Annual tax source is outside its allowed range: '+labels.get(sid,sid))
    return dict(cfg=c,block=record,summary=dict(name=name.strip(),
        explanation='Actual year-to-date provision. State tax uses positive YTD income with no state NOL. '+
        ('Cumulative state provision reduces federal taxable income. ' if deduct else 'No state-tax deduction from federal income. ')+
        'Federal NOL utilization uses the tax-year opening balance; current-year losses net within the year. Calendar resets are automatic. Deferred tax recognition and cash settlement remain unchanged.',
        generated=generated,reused=reused,preserved_inputs=len(m.get('inputs',[])),removed_rules=[],
        outputs=[dict(role=k,id=v,name=next(x.get('name',v) for x in m['rules'] if x['id']==v)) for k,v in outputs.items()],
        current_before=before,current_after=m.get('outputs',{}).get('current'),
        fiscal_year_end_month=end))
