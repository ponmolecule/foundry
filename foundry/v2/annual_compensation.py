"""Full model-year compensation awards, reusing existing literal marginal bands.

A projection pass supplies full-year upstream flows and actual selected-role pay.
The posting pass allocates the award. Re-observing inputs rejects feedback rather
than silently using a stale revenue/payroll forecast or a fixed-point guess.
"""
import math
from .workforce import resolve_workforce_additive_components
from .opex_extensions import apply_piecewise_schedule


def enabled(cfg):
    wf = (((cfg.get('assumptions') or {}).get('nie_detail') or {}).get('workforce') or {})
    return any(c.get('allocation') == 'model_year_equal' for c in wf.get('additive_components') or [])


def build_plan(cfg, projection):
    a = cfg['assumptions']; ppy = int(a.get('periods_per_year') or 4)
    n = int(a.get('n_periods') or 12)
    if n % ppy:
        raise ValueError('Full-year compensation allocation requires a horizon of complete model years')
    wf = ((a.get('nie_detail') or {}).get('workforce') or {})
    inputs = projection.get('_comp_projection_inputs') or {}
    histories = inputs.get('income_statement_flow_history') or {}
    role_pay = inputs.get('role_base_pay') or {}
    plan = {}
    for c in resolve_workforce_additive_components(wf, ppy):
        if c.get('allocation') != 'model_year_equal':
            continue
        cid = c['component_id']
        if not cid or cid in plan:
            raise ValueError('Full-year compensation pools require unique stable component IDs')
        floor = c.get('salary_floor') or {}; selected = floor.get('role_series_ids') or []
        if any(s not in role_pay for s in selected):
            raise ValueError('Compensation floor references an unavailable or ambiguous workforce role')
        years, amounts = [], []
        for start in range(0, n, ppy):
            terms, observed = [], 0.0
            for term in c['terms']:
                path = histories.get(term['metric'])
                if path is None or len(path) != n:
                    raise ValueError('Full-year compensation source has an incomplete forecast')
                value = sum(float(x) for x in path[start:start+ppy])
                contribution = value * term['weight']; observed += contribution
                terms.append(dict(metric=term['metric'], amount=value, weight=term['weight'], contribution=contribution))
            selected_pay = {s: sum(role_pay[s][start:start+ppy]) for s in selected}
            salary = sum(selected_pay.values())
            minimum = salary * float(floor.get('rate') or 0)
            banded = apply_piecewise_schedule(observed, c['bands'])
            award = max(minimum, banded) if floor else banded
            load = award * c.get('payroll_load_rate', 0.0)
            posted = (award + load) / ppy
            if not all(math.isfinite(v) for v in (salary, minimum, banded, award, load, posted)):
                raise ValueError('Full-year compensation calculation must be finite')
            years.append(dict(model_year=start//ppy+1, terms=terms, composite=observed,
                              selected_base_pay=salary, role_base_pay=selected_pay, salary_floor=minimum, band_award=banded,
                              award=award, payroll_load=load, expense=award+load, per_period=posted))
            amounts.extend([posted]*ppy)
        plan[cid] = dict(component_id=cid, name=c['name'], allocation='model_year_equal',
                         units='dollars', salary_floor=floor, years=years, amounts=amounts)
    return plan


def run_with_annual_pools(cfg, engine):
    probe = engine(cfg, _comp_probe=True)
    plan = build_plan(cfg, probe)
    result = engine(cfg, _comp_plan=plan)
    checked = build_plan(cfg, result)
    for cid, row in plan.items():
        for initial, actual in zip(row['years'], checked[cid]['years']):
            for key in ('composite', 'selected_base_pay', 'salary_floor', 'band_award', 'award'):
                if not math.isclose(initial[key], actual[key], rel_tol=1e-10, abs_tol=1e-6):
                    raise ValueError('Full-year compensation has a feedback dependency: its revenue or selected payroll changes when the pool is posted. Use event-based observation or independent sources.')
    result.pop('_comp_projection_inputs', None)
    result['workforce']['annual_pool_calculations'] = list(plan.values())
    return result
