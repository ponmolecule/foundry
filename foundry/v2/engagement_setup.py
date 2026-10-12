"""Explicit setup edits with input-dependent protection; never reset an engagement."""
import copy,hashlib,json,math,re,datetime

CHARTERS={'national':'OCC','national_trust':'OCC','state_member':'Federal Reserve + state supervisor','state_nonmember':'FDIC + state supervisor'}
LABELS={'lending_products':'Lending inputs','deposit_products':'Deposit inputs','obs_exposures':'Fee / off-book inputs','nie_detail':'Operating expenses','cac_feeds':'Customer acquisition','rate_curves':'Manually edited reference curves'}
FIELDS={'name','state','target_opening','charter_type','cblr_election','periods_per_year','years','initial_capital'}

def _clean(value):
    if isinstance(value,dict):
        return {k:v for k,x in sorted(value.items()) if not k.startswith('_') and k not in {'name','label','memo','description','source_vintage','vintage','retrieved_at'} and (v:=_clean(x)) not in (None,{},[])}
    if isinstance(value,list):return [_clean(x) for x in value]
    return value

def fingerprints(cfg):
    a=copy.deepcopy(cfg.get('assumptions') or {})
    # Generated caches move whenever the calendar/horizon changes or the page renders.
    # Only authored curve overrides are setup dependencies.
    for key in ('rate_path_q','rate_path_longer_run','org_costs_pre_open','n_periods','periods_per_year'):a.pop(key,None)
    rc=a.get('rate_curves') or {}
    a['rate_curves']={k:v for k,v in rc.items() if isinstance(v,dict) and v.get('edited') is True}
    return {k:hashlib.sha256(json.dumps(_clean(v),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest() for k,v in a.items() if not k.startswith('_') and _clean(v) not in (None,{},[])}

def initialize(cfg):
    out=copy.deepcopy(cfg)
    out['authoring_setup']={'version':1,'creation_inputs':fingerprints(out)}
    return out

def values(cfg):
    a=cfg.get('assumptions') or {};cp=cfg.get('charter_profile') or {};ppy=int(a.get('periods_per_year') or 4);n=int(a.get('n_periods') or 12)
    return {'name':cfg.get('proposed_bank') or cfg.get('client_legal_name') or '', 'state':cp.get('state') or cfg.get('hq') or '', 'target_opening':cp.get('target_opening') or cfg.get('target_opening') or '', 'charter_type':cp.get('charter_type') or '', 'regulator':cp.get('regulator') or CHARTERS.get(cp.get('charter_type'),''), 'cblr_election':cp.get('cblr_election',True), 'periods_per_year':ppy,'years':n/ppy,'n_periods':n,'initial_capital':(cfg.get('target_state') or {}).get('initial_capital',0)}

def _horizon_dependency(cfg):
    def walk(node):
        if isinstance(node,dict):
            mn=node.get('managed_notional')
            if isinstance(mn,dict) and mn.get('trajectory','ramp_to_target')=='ramp_to_target':
                implicit=(not mn.get('ramp_periods')) if mn.get('ramp_periods') is not None else mn.get('ramp_quarters') is None
                if implicit and float(mn.get('day1') or 0)!=float(mn.get('target') or 0):return True
            return any(walk(v) for v in node.values())
        if isinstance(node,list):return any(walk(x) for x in node)
        return False
    return 'A managed balance ramps over the forecast horizon. Enter an explicit ramp duration in its product card before changing the horizon.' if walk(cfg.get('assumptions') or {}) else ''


def policy(cfg):
    current=fingerprints(cfg);baseline=(cfg.get('authoring_setup') or {}).get('creation_inputs') if (cfg.get('authoring_setup') or {}).get('version')==1 else None
    if isinstance(baseline,dict):changed=[k for k in sorted(set(current)|set(baseline)) if current.get(k)!=baseline.get(k)]
    else:
        # Old files have no creation evidence. Only genuinely empty model shells
        # can be treated as early; populated legacy engagements remain protected.
        a=cfg.get('assumptions') or {}
        roots=('lending_products','deposit_products','obs_exposures','nie_detail','cac_feeds','capital_raises','scheduled_borrowings','securities_afs','securities_htm','managed_securities_portfolios','fixed_assets','cost_pools','other_assets_model','other_liabilities_model','interest_balances','interest_balance_model','balance_components_model','account_adoption','deposit_retention_pools','loan_allocation_groups')
        changed=[k for k in roots if a.get(k)]
        if any(isinstance(v,dict) and v.get('edited') for v in (a.get('rate_curves') or {}).values()):changed.append('rate_curves')
    if any(isinstance(v,dict) and v.get('edited') for v in ((cfg.get('assumptions') or {}).get('rate_curves') or {}).values()) and 'rate_curves' not in changed:changed.append('rate_curves')
    labels=[LABELS.get(k,k.replace('_',' ').capitalize()) for k in changed]
    reason='Existing inputs protect these structural settings: '+', '.join(labels[:3])+(' and other inputs' if len(labels)>3 else '')+'.' if labels else ''
    if labels and not isinstance(baseline,dict):reason='This existing engagement has model inputs and no creation baseline. Its structural settings are protected.'
    manual=any(isinstance(v,dict) and v.get('edited') for v in ((cfg.get('assumptions') or {}).get('rate_curves') or {}).values())
    return {'values':values(cfg),'early':not changed,'dependencies':labels,'structural_reason':reason,'extend_reason':'Manual dated anchors are preserved; added periods use the existing curve interpolation and terminal rule.' if manual else '', 'has_baseline':isinstance(baseline,dict),'horizon_dependency':_horizon_dependency(cfg)}

def _cadence_defaults(a,old,new):
    ratio=old/new
    amounts={'originations','new_deposits','purchases','opex_fixed','overhead'};growth={'growth','orig_growth','overhead_growth'}
    def walk(obj):
        if isinstance(obj,dict):
            if obj.get('cadence')=='model_period' and obj.get('values'):raise ValueError('A model-period schedule requires deliberate reauthoring before changing cadence')
            if obj.get('overrides') and any(obj['overrides'].values()):raise ValueError('Period overrides require deliberate reauthoring before changing cadence')
            if obj.get('schedule') and obj.get('period') not in {'month','quarter','year'}:raise ValueError('An untyped period schedule prevents a cadence change')
            drv=obj.get('driver') or {}
            if obj.get('basis')=='transaction' and drv.get('source','constant')=='constant' and not (drv.get('params') or {}).get('flow_path'):
                params=drv.get('params') or {}
                if isinstance(params.get('base'),(int,float)):params['base']*=ratio
            for k,v in list(obj.items()):
                if k in {'start_period','end_period','hire_period','placed_in_service_period','at_period'} and isinstance(v,int) and not isinstance(v,bool) and v>0:
                    translated=(v-1)*new/old+1
                    if translated!=int(translated):raise ValueError('Period timing cannot be represented exactly at the proposed cadence')
                    obj[k]=int(translated)
                if k in {'ramp_periods','ramp_in_periods'} and isinstance(v,int) and not isinstance(v,bool) and v>1:
                    translated=v*new/old
                    if translated!=int(translated) or translated<1:raise ValueError('Ramp timing cannot be represented exactly at the proposed cadence')
                    obj[k]=int(translated)
                if k.endswith('_per_period') and isinstance(v,(int,float)) and not isinstance(v,bool):
                    stem=k[:-11]
                    if stem in amounts:obj[k]=v*ratio
                    elif stem in growth:
                        if 1+v<0:raise ValueError('Cannot convert '+k+' safely')
                        obj[k]=(1+v)**ratio-1
                    elif stem in {'runoff','fv_decay','msr_decay'}:
                        if not 0<=v<=1:raise ValueError('Cannot convert runoff safely')
                        obj[k]=1-(1-v)**ratio
                    elif v:raise ValueError('Unrecognized per-period input '+k+' prevents a cadence change')
                walk(v)
        elif isinstance(obj,list):
            for x in obj:walk(x)
    walk(a)

def apply(cfg,patch):
    if not isinstance(patch,dict) or set(patch)-FIELDS:raise ValueError('Unsupported engagement setup fields')
    out=copy.deepcopy(cfg);p=policy(cfg);old=p['values'];new={**old,**patch}
    ppy=new['periods_per_year'];years=new['years'];capital=new['initial_capital']
    if isinstance(ppy,bool) or ppy not in (4,12) and ppy!=old['periods_per_year']:raise ValueError('Select monthly or quarterly cadence')
    if isinstance(years,bool) or not isinstance(years,(int,float)) or not math.isfinite(years) or not 1<=years<=7 or not math.isclose(years*ppy,round(years*ppy),rel_tol=0,abs_tol=1e-9):raise ValueError('Select a horizon of 1–7 years with whole model periods')
    if isinstance(capital,bool) or not isinstance(capital,(int,float)) or not math.isfinite(capital) or capital<0:raise ValueError('Initial capital must be finite and nonnegative')
    if not isinstance(new['cblr_election'],bool):raise ValueError('CBLR election must be Yes or No')
    if not str(new['name']).strip():raise ValueError('Institution name is required')
    if new['charter_type'] not in CHARTERS and new['charter_type']!=old['charter_type']:raise ValueError('Select a supported charter type')
    opening=str(new['target_opening']).strip()
    if opening!=old['target_opening'] and opening:
        if re.fullmatch(r'\d{4}-Q[1-4]',opening,re.I):pass
        else:
            try:datetime.date.fromisoformat(opening)
            except ValueError:raise ValueError('Opening date must be YYYY-MM-DD or YYYY-Q1…Q4')
    structural=[k for k in ('periods_per_year','target_opening','charter_type') if new[k]!=old[k]]
    if (structural or years<old['years']) and not p['early']:raise ValueError(p['structural_reason'])
    if years!=old['years'] and p['horizon_dependency']:raise ValueError(p['horizon_dependency'])
    if years>old['years'] and any(isinstance(v,dict) and v.get('edited') and not v.get('dated_anchors') for v in ((cfg.get('assumptions') or {}).get('rate_curves') or {}).values()):raise ValueError('A manual reference curve lacks dated anchors. Open its curve editor before extending the forecast; no curve values have been changed.')
    changed={k for k in FIELDS if new[k]!=old[k]}
    if not changed:return out
    a=out.setdefault('assumptions',{})
    if ppy!=old['periods_per_year']:
        _cadence_defaults(a,old['periods_per_year'],ppy);a['periods_per_year']=ppy
    if changed & {'years','periods_per_year'}:a['n_periods']=round(years*ppy)
    cp_fields=changed & {'charter_type','state','target_opening','cblr_election'}
    if cp_fields:
        cp=out.setdefault('charter_profile',{})
        for key in cp_fields:cp[key]=opening if key=='target_opening' else new[key]
        if 'charter_type' in changed:cp['regulator']=CHARTERS[new['charter_type']]
        cp['source']='engagement setup'
    if 'name' in changed:
        out['proposed_bank']=str(new['name']).strip()
        if out.get('client_legal_name')==old['name']+' (in organization)':out['client_legal_name']=out['proposed_bank']+' (in organization)'
        if out.get('scenario_name')==old['name']+' — engagement baseline':out['scenario_name']=out['proposed_bank']+' — engagement baseline'
    if 'state' in changed and out.get('hq') in ('',None,'TBD',old['state']):out['hq']=str(new['state']) or 'TBD'
    if 'initial_capital' in changed:out.setdefault('target_state',{})['initial_capital']=capital
    if ppy!=old['periods_per_year'] or opening!=old['target_opening'] or years!=old['years']:
        rc=a.get('rate_curves')
        if rc:
            # Dated anchors are source observations, not disposable horizon caches.
            # Rebuild only the sampled quarterly grid, using the existing engine rule.
            from .engine_q_a import _build_rate_curve_set
            projected=_build_rate_curve_set(a,out,ppy)
            width=max(1,ppy//4);nq=math.ceil(a['n_periods']/width)
            for key in ('sofr','effr','prime'):
                curve=rc.get(key) or {};oldpath=list((cfg['assumptions']['rate_curves'].get(key) or {}).get('path_q') or [])
                samples=[projected[key](min(a['n_periods'],q*width)) for q in range(1,nq+1)]
                keep=curve.get('edited') and ppy==old['periods_per_year'] and opening==old['target_opening']
                curve['path_q']=(oldpath+samples[len(oldpath):])[:nq] if keep else samples;rc[key]=curve
            a['rate_path_q']=rc['sofr']['path_q'].copy()
    if 'target_opening' in changed and 'target_opening' in out:out['target_opening']=opening
    # Full validator checks that extending doesn't demand absent source observations.
    # Existing intake questions may remain, but no new ones may be introduced.
    from .validate_q import validate_errors_v2
    def messages(c):return {json.dumps(x,sort_keys=True) for x in validate_errors_v2(copy.deepcopy(c))}
    extra=messages(out)-messages(cfg)
    if extra:raise ValueError('Setup change requires additional inputs: '+'; '.join(sorted(extra)[:3]))
    # Safe setup edits update the creation baseline, without erasing later authorship.
    if p['early']:out['authoring_setup']={'version':1,'creation_inputs':fingerprints(out)}
    return out
