"""Recognized category expenses available to non-posting liability stock formulas.

Includes recurring recognition and additive category components, but never silently
includes payroll, product costs or depreciation in the category aggregate.
"""
from collections.abc import Mapping
import math

TOTAL = 'operating_expense_categories'


def categories(a):
    return ((a.get('nie_detail') or {}).get('categories') or [])


def catalog(a):
    out = [dict(series_id=TOTAL, label='Operating expense categories · total')]
    for c in categories(a):
        if c.get('series_id'):
            out.append(dict(series_id=str(c['series_id']), label='Operating expense · '+str(c.get('name') or 'Unnamed category')))
    return out


def selection(a, sid, exclusions):
    if not isinstance(exclusions, list) or any(not isinstance(x,str) for x in exclusions):
        raise ValueError('Expense exclusions must be a list of category Series IDs')
    cs = categories(a)
    ids = [str(c['series_id']) for c in cs if c.get('series_id')]
    if len(ids) != len(set(ids)):
        raise ValueError('Expense category Series IDs must be unique')
    if any(x not in ids for x in exclusions):
        raise ValueError('Excluded expense category no longer exists')
    if sid != TOTAL and (sid not in ids or exclusions):
        raise ValueError('Select an existing expense category; exclusions apply only to the total')
    chosen = [i for i,c in enumerate(cs) if (sid == TOTAL or c.get('series_id') == sid) and c.get('series_id') not in exclusions]
    if not chosen:
        raise ValueError('Expense-linked liability requires at least one eligible category')
    for i in chosen:
        # A stock link adds a payable separately. Do not post a second accrued balance
        # for the same category through independent deferred cash settlement.
        mode = (cs[i].get('settlement') or {}).get('mode') or 'recognition'
        if mode not in {'recognition', 'monthly'} or float((cs[i].get('settlement') or {}).get('opening_balance') or 0):
            raise ValueError('Expense-linked liability overlaps category cash settlement; use Recognition settlement for its selected expenses')
    return chosen


def period_amounts(detail, index, linked_values):
    if not detail:
        return {}
    values = {i: float(v[index]) for i,v in enumerate(detail.get('_category_series') or [])}
    for component, amount in zip(detail.get('linked_components') or [], linked_values or []):
        i = component.get('category_index')
        if i is not None:
            values[i] = values.get(i,0.) + float(amount)
    if any(not math.isfinite(v) for v in values.values()):
        raise ValueError('Recognized expense source must be finite')
    return values
