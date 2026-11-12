"""Salary-linked award cohorts with explicit historical awards and finite vesting."""
import math


def normalize(c, ppy):
    if ppy not in (4, 12):
        raise ValueError('Salary vesting requires monthly or quarterly cadence')
    ids = c.get('role_series_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('Select distinct eligible base-salary roles for LTI')
    def number(v, label):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(label + ' must be finite and nonnegative')
        return float(v)
    rate = number(c.get('award_rate'), 'Award rate')
    cliff = number(c.get('cliff_years'), 'Cliff years')
    duration = number(c.get('vesting_years'), 'Vesting years')
    if cliff != int(cliff) or cliff < 1 or duration != int(duration) or duration < 1:
        raise ValueError('Cliff and vesting duration must be positive whole years')
    if 'historical_awards' not in c or not isinstance(c['historical_awards'], list):
        raise ValueError('Enter historical awards, or explicitly confirm none')
    history, seen = [], set()
    for h in c['historical_awards']:
        year = h.get('model_year')
        if isinstance(year, bool) or not isinstance(year, int) or year > 0 or year in seen:
            raise ValueError('Historical award years must be distinct integers at or before Year 0')
        seen.add(year)
        history.append(dict(model_year=year, amount=number(h.get('amount'), 'Historical award')))
    return dict(driver='salary_vesting', allocation='salary_vesting',
                component_id=str(c.get('component_id') or ''), name=str(c.get('name') or 'Long-term incentives'),
                role_series_ids=list(ids), award_rate=rate, cliff_years=int(cliff),
                vesting_years=int(duration), historical_awards=history, payroll_load_rate=0)


def build(c, role_pay, n, ppy):
    selected = c['role_series_ids']
    if any(s not in role_pay or len(role_pay[s]) != n for s in selected):
        raise ValueError('LTI references unavailable or ambiguous base-salary roles')
    cohorts = [dict(h, historical=True) for h in c['historical_awards']]
    years, amounts = [], []
    for start in range(0, n, ppy):
        year = start // ppy + 1
        salary = sum(sum(role_pay[s][start:start+ppy]) for s in selected)
        award = salary * c['award_rate']
        if not math.isfinite(award) or salary < 0:
            raise ValueError('LTI base salary and award must be finite and nonnegative')
        cohorts.append(dict(model_year=year, amount=award, historical=False))
        recognized = [dict(award_year=h['model_year'], award=h['amount'], installment=h['amount']/c['vesting_years'])
                      for h in cohorts if c['cliff_years'] <= year-h['model_year'] < c['cliff_years']+c['vesting_years']]
        expense = sum(h['installment'] for h in recognized)
        years.append(dict(model_year=year, selected_base_pay=salary, award=award, expense=expense,
                          per_period=expense/ppy, cohorts=recognized, terms=[], composite=salary,
                          salary_floor=0, band_award=award, payroll_load=0))
        amounts.extend([expense/ppy]*ppy)
    return dict(component_id=c['component_id'], name=c['name'], allocation='salary_vesting',
                units='dollars', cliff_years=c['cliff_years'], vesting_years=c['vesting_years'],
                award_rate=c['award_rate'], historical_awards=c['historical_awards'], years=years, amounts=amounts)
