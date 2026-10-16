"""Calendar curves, schedule precedence, no silent fallback, stress and evidence."""
import copy,json,math
from pathlib import Path
from .rates_workspace import preview,validate,lookup,iso
from .engine_q_a import _build_rate_curve_set,_apply_overlays,run_pf_a
from .run_q import run_v2
from .audit_workbook import calculation_audit_workbook

def config(ppy=12):
 c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions'];a['periods_per_year']=ppy;a['n_periods']=36 if ppy==12 else 12;c.setdefault('charter_profile',{})['target_opening']='2028-01-01'
 rc={'fomc':{'anchors':{'2028-12-31':.034,'2029-12-31':.031},'lr':.03},'current_policy':{'mid':.034,'top':.03525,'bottom':.03275,'observation_date':'2027-12-31'},'offsets':{'effr':0.,'sofr':.0005,'prime':.03},'half_band':.00125}
 a['rate_curves']=rc;return c

def workspace(c):
 a=c['assumptions'];w={'version':1,'published':copy.deepcopy(a['rate_curves']),'indices':{k:{'source':'existing'} for k in ('effr','sofr','prime')},'anchor_overrides':{},'basis':{},'policy_interpolation':'linear','policy_tail':'glide'};a['rates_workspace']=w;return w

def schedule(w,k='effr',extension='hold'):
 w['indices'][k]={'source':'schedule','schedule':{'points':[{'date':'2028-01-01','rate':.034},{'date':'2029-01-01','rate':.031}],'units':'percent','label':'Test source','interpolation':'step','extension':extension,'through':'2030-12-31'}}

def near(a,b):assert abs(a-b)<1e-12,(a,b)
def bad(c):
 try:validate(c['assumptions'],c)
 except (ValueError,TypeError):return
 raise AssertionError('invalid configuration accepted')

def main():
 c=config();old=run_pf_a(copy.deepcopy(c));w=workspace(c);assert run_pf_a(copy.deepcopy(c))==old,'opening workspace cannot alter legacy economics'
 before=copy.deepcopy(c);p=preview(c);assert c==before,'preview mutated config';assert len(p['monthly'])==36
 schedule(w);p=preview(c);near(p['monthly'][11]['effr']['rate'],.034);near(p['monthly'][12]['effr']['rate'],.031)
 # Annualized rates are not divided just because the schedule is monthly.
 near(p['native'][12]['effr'],.031)
 q=config(4);qw=workspace(q);schedule(qw);qp=preview(q)
 for r in qp['native']:near(r['effr'],p['monthly'][r['period']*3-1]['effr']['rate'])
 for k in ('effr','sofr','prime'):
  d=config();dw=workspace(d);schedule(dw,k);curves=_build_rate_curve_set(d['assumptions'],d,12);near(curves[k](1),.034)
  dw['basis'][k]=.2;dw['anchor_overrides']['2028-12-31']=.09;near(_build_rate_curve_set(d['assumptions'],d,12)[k](1),.034)
 # Scenario shift reaches independent pasted rates exactly once.
 a=copy.deepcopy(c['assumptions']);_apply_overlays([],[],a,{'rate_shock_bp':100},12)
 near(_build_rate_curve_set(a,c,12)['effr'](13),.041)
 d=config();dw=workspace(d);dw['indices']['effr']['source']='derived';v=_build_rate_curve_set(d['assumptions'],d,12)['effr'](10)
 da=copy.deepcopy(d['assumptions']);_apply_overlays([],[],da,{'rate_shock_bp':100},12);near(_build_rate_curve_set(da,d,12)['effr'](10),v+.01)
 # Scheduled curves work even without Fed source metadata.
 e=config();ew=workspace(e);ew['published']={};e['assumptions']['rate_curves']={}
 for k in ew['indices']:schedule(ew,k)
 validate(e['assumptions'],e)
 # Range wins over selected schedule, and only on its inclusive dates.
 w['indices']['effr']['overrides']=[{'start':'2029-01-01','end':'2029-02-28','rate':.04}]
 p=preview(c);near(p['monthly'][12]['effr']['rate'],.04);near(p['monthly'][14]['effr']['rate'],.031)
 for edit in [lambda x:x['indices']['effr']['schedule'].update(extension='error',through='2029-01-01'),lambda x:x['indices']['effr']['schedule'].update(interpolation='x'),lambda x:x['indices']['effr']['schedule']['points'].append({'date':'2029-01-01','rate':.03}),lambda x:x['indices']['effr']['schedule']['points'][0].update(date='2028-02-31'),lambda x:x['indices']['effr']['schedule'].update(units='auto'),lambda x:x['indices']['effr']['schedule']['points'][0].update(rate=float('nan')),lambda x:x['indices']['effr']['schedule']['points'][0].update(date='2028-02-01')]:
  d=copy.deepcopy(c);edit(d['assumptions']['rates_workspace']);bad(d)
 # Error extension is strict outside the explicit coverage, including valuation horizons.
 d=copy.deepcopy(c);d['assumptions']['rates_workspace']['indices']['effr']['schedule']['extension']='error';f=_build_rate_curve_set(d['assumptions'],d,12)['effr']
 try:f(37)
 except ValueError:pass
 else:raise AssertionError('out of coverage silently filled')
 pts=[(iso('2028-01-01'),.04),(iso('2028-03-01'),.03)];near(lookup(pts,iso('2028-01-31'),'linear'),.035);near(lookup(pts,iso('2028-01-31'),'step'),.04)
 # Product pricing consumes the shared index, retaining spread and balance measure.
 d=config();dw=workspace(d);schedule(dw)
 d['assumptions']['deposit_products'][0].update(rate_type='float',index='effr',index_spread=.0025)
 rr=run_pf_a(copy.deepcopy(d));dp=next(x for x in rr['products'] if x['family']=='deposit')
 near(dp['rateQ'][0],3.65);near(dp['rateQ'][12],3.35)
 assert abs(dp['intExp'][0]-(dp['bal'][0]+dp['bal'][1])/2*.0365/12)<1e-6
 # End to end: deposit expense follows selected index; export retains source data and rates.
 d=config();dw=workspace(d);schedule(dw);res=run_v2(d);wb=calculation_audit_workbook(d,res)
 assert {'Rate Assumptions','Effective Rates','Engine Rates'}<=set(wb.sheetnames)
 assert wb['Effective Rates'].cell(2,4).value==.034
 assert wb['Engine Rates'].cell(14,3).value==.031
 from io import BytesIO
 wb.save(BytesIO())
 print('Rates workspace: legacy identity, dates, cadence, precedence, stress, validation and audit pass.')
if __name__=='__main__':main()
