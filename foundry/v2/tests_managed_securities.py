"""Focused managed-securities gate: economics, authoring, audit, and UI integration."""
from __future__ import annotations
import copy, json, sys, subprocess
from pathlib import Path
import io

from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_config_v2
from .securities import EQUITY_END_SERIES_ID, DEPOSITS_END_SERIES_ID, managed_period_snapshot, prepare_managed_securities
from .fiw import build_fiw, diff_import
from .audit_workbook import calculation_audit_workbook


def _cfg():
    c=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
    a=c['assumptions']
    a['securities_afs']=[]; a['securities_htm']=[]
    a['aoci_sensitivity_annual']=0.0
    a['managed_securities_portfolios']=[{
        'name':'Managed liquidity portfolio',
        'series_id':'managed-sec-portfolio-test',
        'target_source':{'kind':'bank_balance_sheet','series_id':EQUITY_END_SERIES_ID},
        'target_ratio_spec':{'source':'entered','trajectory':'flat','value':0.30},
        'sleeves':[
            {'name':'Government','series_id':'managed-sec-gov','classification':'AFS','opening':0.0,
             'allocation_spec':{'source':'entered','trajectory':'flat','value':0.80},
             'maturity_rate_spec':{'source':'entered','trajectory':'flat','value':0.10,'period':'month'},
             'yield_source':'entered','yield_spec':{'source':'entered','trajectory':'flat','value':0.04}},
            {'name':'Agency','series_id':'managed-sec-agency','classification':'AFS','opening':0.0,
             'allocation_spec':{'source':'entered','trajectory':'flat','value':0.15},
             'maturity_rate_spec':{'source':'entered','trajectory':'flat','value':0.05,'period':'quarter'},
             'yield_source':'entered','yield_spec':{'source':'entered','trajectory':'flat','value':0.045}},
            {'name':'Community','series_id':'managed-sec-community','classification':'HTM','opening':0.0,
             'allocation_spec':{'source':'entered','trajectory':'flat','value':0.05},
             'maturity_rate_spec':{'source':'entered','trajectory':'flat','value':0.00,'period':'year'},
             'yield_source':'entered','yield_spec':{'source':'entered','trajectory':'flat','value':0.045}},
        ]
    }]
    return c


def main():
    p=f=0
    def ck(name, cond, detail=''):
        nonlocal p,f
        if cond: p+=1; print('  PASS ',name+(f' — {detail}' if detail else ''))
        else: f+=1; print('  FAIL ',name+(f' — {detail}' if detail else ''))

    c=_cfg(); validate_config_v2(c); r=run_pf_a(copy.deepcopy(c)); mp=r['managed_securities'][0]
    ck('managed portfolio targets current period-end Total Equity',
       all(abs(t-0.30*r['bs']['equity'][i+1])<1e-3 for i,t in enumerate(mp['target'][:12])))
    lag=_cfg(); lagts=lag['assumptions']['managed_securities_portfolios'][0]['target_source']; lagts['timing']='prior_period'; lagts['prior_initialization']='zero'
    lagr=run_pf_a(copy.deepcopy(lag)); lagmp=lagr['managed_securities'][0]
    ck('prior-period target timing leaves first modeled-period securities at zero',
       abs(lagmp['target'][0])<1e-9 and all(abs(s['ending'][0])<1e-9 for s in lagmp['sleeves']))
    ck('prior-period target timing uses M1 equity to establish M2 securities',
       all(abs(lagmp['target'][i] - 0.30*lagr['bs']['equity'][i]) < 1e-3 for i in range(1,12)))
    lagopen=_cfg(); ots=lagopen['assumptions']['managed_securities_portfolios'][0]['target_source']; ots['timing']='prior_period'; ots['prior_initialization']='opening_source'
    lagopenr=run_pf_a(copy.deepcopy(lagopen)); lagopenmp=lagopenr['managed_securities'][0]
    ck('prior-period opening-source initialization is explicit and uses opening equity when selected',
       abs(lagopenmp['target'][0] - 0.30*lagopenr['bs']['equity'][0]) < 1e-3)
    depcfg=_cfg(); depcfg['assumptions']['managed_securities_portfolios'][0]['target_source']['series_id']=DEPOSITS_END_SERIES_ID
    depr=run_pf_a(copy.deepcopy(depcfg)); depmp=depr['managed_securities'][0]
    ck('managed portfolio target source is a selectable stable Balance Sheet Series, not an Equity-only branch',
       all(abs(t-0.30*depr['bs']['deposits'][i+1])<1e-3 for i,t in enumerate(depmp['target'][:12])))
    g,a,cr=mp['sleeves']
    ck('generic sleeve allocations resolve 80/15/5 target split',
       abs(g['ending'][0]/mp['target'][0]-.80)<1e-10 and abs(a['ending'][0]/mp['target'][0]-.15)<1e-10 and abs(cr['ending'][0]/mp['target'][0]-.05)<1e-10)
    ck('opening + maturities + balancing net purchases reaches target exactly',
       all(abs((s['starting'][i]-s['maturing'][i]+s['net_purchases'][i])-s['ending'][i])<1e-6
           for s in mp['sleeves'] for i in range(12)))
    ck('period-end annual yield is periodized once for managed interest',
       abs(cr['interest_income'][0] - cr['ending'][0]*cr['yield'][0]/12.0)<1e-6)
    ck('CRA-like sleeve therefore does not overstate monthly interest by 12x',
       abs(cr['interest_income'][0]*12.0 - cr['ending'][0]*0.045)<1e-6)
    ck('managed AFS/HTM endings feed designated securities balance-sheet lines',
       abs(r['bs']['afsBook'][1]-(g['ending'][0]+a['ending'][0]))<1e-6 and abs(r['bs']['htmBook'][1]-cr['ending'][0])<1e-6)
    ck('managed interest feeds securities interest income', r['is']['bookInt'][0] > 0 and abs(r['is']['bookInt'][0]-sum(s['interest_income'][0] for s in mp['sleeves']))<1e-6)
    ck('managed portfolios suppress the legacy residual-securities funding plug',
       all(abs(x)<1e-6 for x in r['bs']['sec']))
    ck('surplus funding remains in cash when managed portfolios own the securities allocation',
       any(float(x or 0.0)>0 for x in r['bs']['cash']))

    # Signed balancing flow: a falling target is a sale, never silently floored to zero.
    a0=c['assumptions']; a0['managed_securities_portfolios'][0]['target_ratio_spec']={
        'source':'entered','trajectory':'explicit','cadence':'month','values':[0.30,0.01]+[0.01]*34,'extend':'hold'}
    r2=run_pf_a(copy.deepcopy(c)); mp2=r2['managed_securities'][0]
    ck('negative balancing flow remains a net sale/reduction', any(x < 0 for s in mp2['sleeves'] for x in s['net_purchases'][1:3]))

    # Explicit yield path is consumed as authored, not mapped through curve library.
    c3=_cfg(); sl=c3['assumptions']['managed_securities_portfolios'][0]['sleeves'][0]
    sl['yield_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[.01,.02,.03]+[.03]*33,'extend':'hold'}
    r3=run_pf_a(copy.deepcopy(c3)); ys=r3['managed_securities'][0]['sleeves'][0]['yield']
    ck('entered explicit yield path is consumed directly', ys[:3]==[.01,.02,.03])

    # Curve Library is optional, not mandatory.
    c4=_cfg(); sl=c4['assumptions']['managed_securities_portfolios'][0]['sleeves'][0]
    sl['yield_source']='curve_library'; sl['curve_name']='sofr'; sl.pop('yield_spec',None)
    r4=run_pf_a(copy.deepcopy(c4));
    ck('curve-library yield is an optional alternative source', len(r4['managed_securities'][0]['sleeves'][0]['yield'])==36)

    # Maturity/runoff owns an explicit natural period independent of trajectory cadence.
    cy=_cfg(); sly=cy['assumptions']['managed_securities_portfolios'][0]['sleeves'][0]
    sly['maturity_rate_spec']={'source':'entered','trajectory':'flat','value':0.12,'period':'year'}
    ry=run_pf_a(copy.deepcopy(cy)); eff=ry['managed_securities'][0]['sleeves'][0]['maturity_rate'][0]
    ck('annual runoff is survival-equivalent when periodized to monthly cadence',
       abs((1.0-eff)**12 - 0.88) < 1e-10)
    cq=_cfg(); slq=cq['assumptions']['managed_securities_portfolios'][0]['sleeves'][0]
    slq['maturity_rate_spec']={'source':'entered','trajectory':'flat','value':1-(1-.12)**(1/4),'period':'quarter'}
    rq=run_pf_a(copy.deepcopy(cq)); effq=rq['managed_securities'][0]['sleeves'][0]['maturity_rate'][0]
    ck('equivalent annual and quarterly runoff assumptions produce same monthly economics', abs(eff-effq)<1e-12)

    # Same grammar under a quarterly Profile-A engine: yield periodizes once by /4 and runoff
    # preserves its authored natural-period economics.
    qcfg=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text())
    qcfg['assumptions']['managed_securities_portfolios']=copy.deepcopy(_cfg()['assumptions']['managed_securities_portfolios'])
    qcfg['assumptions']['n_periods']=12; qcfg['assumptions']['periods_per_year']=4
    qr=run_pf_a(copy.deepcopy(qcfg)); qsl=qr['managed_securities'][0]['sleeves'][2]
    ck('quarterly managed interest periodizes annual yield exactly once',
       abs(qsl['interest_income'][0]-qsl['ending'][0]*qsl['yield'][0]/4.0)<1e-6)

    # Fail closed on bad allocation and target source.
    bad=_cfg(); bad['assumptions']['managed_securities_portfolios'][0]['sleeves'][0]['allocation_spec']['value']=.79
    try: validate_config_v2(bad); bad_alloc=False
    except ValueError as e: bad_alloc='sum to 100%' in str(e)
    ck('allocation totals fail closed when they do not sum to 100%', bad_alloc)
    bad=_cfg(); bad['assumptions']['managed_securities_portfolios'][0]['target_source']['series_id']='made.up.series'
    try: validate_config_v2(bad); bad_src=False
    except ValueError as e: bad_src='supported balance-sheet Series' in str(e)
    ck('unsupported endogenous target source fails closed', bad_src)
    bad=_cfg(); bad['assumptions']['managed_securities_portfolios'][0]['target_source']['timing']='mystery_period'
    try: validate_config_v2(bad); bad_timing=False
    except ValueError as e: bad_timing='target_source.timing' in str(e)
    ck('unsupported target timing fails closed', bad_timing)
    bad=_cfg(); badts=bad['assumptions']['managed_securities_portfolios'][0]['target_source']; badts['timing']='prior_period'; badts['prior_initialization']='guess'
    try: validate_config_v2(bad); bad_init=False
    except ValueError as e: bad_init='prior_initialization' in str(e)
    ck('unsupported prior-period initialization fails closed', bad_init)

    # AOCI circularity is solved rather than dodged with prior-period equity.
    c5=_cfg(); c5['assumptions']['aoci_sensitivity_annual']=-0.02
    r5=run_pf_a(copy.deepcopy(c5)); mp5=r5['managed_securities'][0]
    ck('current-equity/AOCI circularity converges to the current-period target',
       all(abs(t-.30*r5['bs']['equity'][i+1])<1e-3 for i,t in enumerate(mp5['target'][:12])))

    # Public seam preserves rate dimensions and converts only money to $000s.
    pub=run_v2(_cfg()); ps=pub['managed_securities'][0]['sleeves'][0]
    ck('public managed-securities output preserves decimal rate paths', ps['yield'][0]==.04 and ps['allocation'][0]==.80)
    ck('public managed-securities monetary paths are $000s', ps['ending'][0] < 1_000_000 and pub['managed_securities_units']['monetary']=='$000s')
    ck('public managed-securities target-source value is converted with the other monetary paths',
       pub['managed_securities'][0]['target_source_value'][0] < 1_000_000)

    # Legacy no-managed config remains behaviorally identical when new key is absent vs empty.
    legacy=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text())
    l1=run_pf_a(copy.deepcopy(legacy)); le=copy.deepcopy(legacy); le['assumptions']['managed_securities_portfolios']=[]; l2=run_pf_a(le)
    ck('empty managed-securities authoring is backward-compatible', l1==l2)
    ck('legacy simple-only funding waterfall still permits residual securities', any(abs(x)>1e-6 for x in l1['bs']['sec']))

    # FIW: managed assumptions are visible/editable but clean round-trip is a semantic no-op.
    fiw_cfg=_cfg(); data,_=build_fiw(copy.deepcopy(fiw_cfg), include_capability_map=True)
    merged,rep=diff_import(data,copy.deepcopy(fiw_cfg))
    ck('managed-securities FIW zero-edit round trip is a no-op',
       (rep.get('edits') or [])==[] and json.dumps(merged,sort_keys=True)==json.dumps(fiw_cfg,sort_keys=True))

    # Calculation Audit exposes the complete causal chain, including authored/effective runoff.
    aud=calculation_audit_workbook(copy.deepcopy(fiw_cfg), run_v2(copy.deepcopy(fiw_cfg)))
    ck('Calculation Audit includes Managed Securities causal sheet', bool(aud) and 'Managed Securities' in aud.sheetnames and aud['Managed Securities'].max_row>5)

    # Narrow-tile UI: one managed section only; each security owns a headed block before parameters.
    html=Path('web/console_v2.html').read_text()
    ck('managed securities renders exactly one managed section in Securities & AOCI',
       html.count('Managed portfolios</div><div class="cmut">Target-driven books')==1)
    ck('managed security name/header owns a self-contained sleeve block',
       'sec-managed-sleeve-head' in html and 'sec-managed-sleeve-name' in html and 'sec-managed-sleeve{border-top' in html)
    ck('managed maturity authoring exposes explicit Rate period', 'Rate period' in html and 'secSeriesPeriod' in html)
    ck('managed target source dropdown exposes multiple stable Balance Sheet Series',
       '_managedSecTargetSources' in html and 'bank.balance_sheet.equity.end' in html and 'bank.balance_sheet.deposits.end' in html
       and 'secManagedTargetSource' in html)
    ck('managed target timing and first-period initialization are explicit in the UI',
       'Target timing' in html and 'Current period' in html and 'Prior period' in html
       and 'First modeled period' in html and 'Opening source' in html
       and 'secManagedTargetTiming' in html and 'secManagedTargetPriorInit' in html)
    ck('new managed portfolios default to prior-period timing with an explicit zero first period',
       'timing:"prior_period",prior_initialization:"zero"' in html)
    ck('choosing Explicit opens the managed-securities paste editor immediately',
       'window._secSeriesExplicitOpen[String(path)]=true' in html
       and 'secSeriesExplicitOpen' in html and 'secSeriesExplicitClose' in html)
    ck('closed Explicit managed-securities schedules always expose a visible View / edit control',
       'class="pillbtn sec-managed-explicit-edit"' in html
       and '>View / edit schedule</button>' in html
       and 'sec-managed-explicit-closed' in html)
    ck('open Explicit managed-securities schedules expose an explicit Close control',
       'onclick="secSeriesExplicitClose(' in html and '>Close</button>' in html)

    # Execute the real renderer around the failure mode: Explicit survives a re-render while
    # its transient editor state is closed. The user must never be stranded with only the
    # dropdown saying Explicit and no affordance to reopen the schedule.
    ea=html.index('function _secSeriesEditor(')
    eb=html.index('window.secManagedAddPortfolio=', ea)
    editor_js=html[ea:eb]
    state_a=html.index('window._secSeriesExplicitOpen=')
    state_b=html.index('function _managedSecPortfolios(', state_a)
    state_js=html[state_a:state_b]
    node = "\n".join([
        "const window=globalThis;",
        "let renders=0;",
        "function renderContent(){renders++;}",
        "function refresh(){}",
        "function esc(x){return String(x);}",
        "function _nativeFlowPeriod(){return 'month';}",
        "function _seriesCadenceOptions(){return ['month','quarter','year'];}",
        "function _seriesResolutionUseful(){return false;}",
        "function _seriesPasteSummary(vals,fmt){return vals.length ? vals.length+' values · '+fmt(vals[0]) : 'No values loaded';}",
        "function _explicitPreviewHtml(){return '';}",
        "function growthSpecInline(){return '';}",
        "function _secSeriesDefault(v){return {source:'entered',trajectory:'flat',value:v||0};}",
    ]) + "\n" + state_js + editor_js + "\n" + "\n".join([
        "const path='assumptions.managed_securities_portfolios.0.sleeves.0.yield_spec';",
        "const spec={source:'entered',trajectory:'explicit',cadence:'month',values:[.04,.05],extend:'hold',resolution:'step'};",
        "secSeriesExplicitSet(path,false);",
        "const closed=_secSeriesEditor(path,spec,'Annual yield',false);",
        "secSeriesExplicitOpen(path);",
        "const opened=_secSeriesEditor(path,spec,'Annual yield',false);",
        "secSeriesExplicitClose(path);",
        "const closedAgain=_secSeriesEditor(path,spec,'Annual yield',false);",
        "console.log(JSON.stringify({closed,opened,closedAgain,renders}));",
    ])
    nr=subprocess.run(['node','-e',node],text=True,capture_output=True)
    nj={}
    if nr.returncode==0 and nr.stdout.strip():
        try: nj=json.loads(nr.stdout.strip().splitlines()[-1])
        except Exception: pass
    closed=nj.get('closed',''); opened=nj.get('opened',''); closed_again=nj.get('closedAgain','')
    ck('Explicit renderer is recoverable after close and re-render',
       nr.returncode==0
       and 'View / edit schedule' in closed and '<textarea' not in closed
       and '<textarea' in opened and '>Close</button>' in opened
       and 'View / edit schedule' in closed_again and '<textarea' not in closed_again
       and nj.get('renders')==2, nr.stderr.strip())
    ck('Securities & AOCI card has a whole-card compact collapse/expand control',
       '_cfgSectionIsOpen("secaoci",_secCardHasContent)' in html
       and "cfgSectionSetOpen('secaoci'" in html
       and '_secCardSummary' in html)
    ck('Securities & AOCI module activation includes managed portfolios',
       'function _secAociActive(a)' in html
       and 'c.managed>0' in html
       and 'a.managed_securities_portfolios = []' in html
       and 'secAociToggle();' in html)
    ck('managed UI does not hard-code Treasury/GSE/CRA instrument names or 80/15/5 weights',
       all(x not in html[html.find('// ---------------------------------------------------------------- managed securities'):html.find('function _newNieDetail')]
           for x in ('Treasur','GSE','CRA','0.80','0.15','0.05')))

    print(f'\n{p} passed, {f} failed')
    return 0 if f==0 else 1

if __name__=='__main__': sys.exit(main())
