"""The IQ editor reads resolved payroll; observations must reconcile, including zero-count Total rows."""
import copy
import json
from pathlib import Path
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .parity import _conv_workforce

def fixture(profile='a', ppy=12):
    cfg=json.loads(Path(f'foundry/fixtures/parity/configs/pf_{profile}_base.json').read_text())
    a=cfg['assumptions'];a['periods_per_year']=ppy;a['n_periods']=36 if ppy==12 else 12
    a['operating_expense_mode']='detailed'
    roles=[
      {'series_id':'total','role':'Bank compensation','count':0,'hire_period':1,
       'annual_comp':287500,'compensation_basis':'total','compensation_period':'month',
       'compensation_spec':{'source':'entered','trajectory':'explicit','amount_basis':'total',
                            'period':'month','cadence':'month','values':[287500]*35+[300000],'extend':'hold'}},
      {'series_id':'directors','role':'Directors fees','count':1,'hire_period':1,
       'annual_comp':37500,'compensation_basis':'total','compensation_period':'month'},
      {'series_id':'future','role':'Future population','count':2,'hire_period':3,'end_period':4,
       'annual_comp':120000,'compensation_period':'year','payroll_load_rate':.1},
    ]
    if ppy==4:roles[0]['compensation_spec'].update(cadence='quarter',values=[287500]*12)
    a['nie_detail']={'categories':[],'other_gross_up_rate':0,'workforce':{'mode':'roles','roles':roles,
        'default_payroll_load_rate':0,'default_salary_growth_spec':{'rate':0,'period':'year','method':'step','anchor':'model_year'}}}
    return cfg

def main():
    for profile,ppy,run in [('a',12,run_pf_a),('a',4,run_pf_a),('b',4,run_pf_b)]:
        cfg=fixture(profile,ppy);w=run(copy.deepcopy(cfg))['workforce'];rows=w['population_comp'];n=cfg['assumptions']['n_periods']
        assert len(rows)==3 and all(len(row)==n for row in rows)
        for i in range(n):assert abs(sum(row[i] for row in rows)-w['role_comp'][i])<1e-7
        assert abs(rows[0][0]-287500*12/ppy)<1e-7
        assert abs(rows[1][0]-37500*12/ppy)<1e-7
        assert rows[2][0]==0 and rows[2][1]==0 and rows[2][4]==0
        assert abs(rows[2][2]-120000/ppy*2*1.1)<1e-7
        public=_conv_workforce(w)
        assert abs(public['population_comp'][0][0]-rows[0][0]/1000)<1e-6
        assert public['counts']==w['counts']
    print('PASS population costs reconcile to role payroll in A monthly, A quarterly and B quarterly; Total/zero Count, explicit amounts, start/end, payroll load, public units.')
if __name__=='__main__':main()
