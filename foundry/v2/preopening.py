"""Pre-opening earned income and expenses, in raw dollars, before forecast period one."""
import math

def totals(config):
    po = config.get('pre_opening') or {}
    amounts = {}
    for kind in ('expenses', 'incomes'):
        rows = po.get(kind) or []
        if not isinstance(rows, list): raise ValueError('pre_opening.' + kind + ' must be a list')
        total = 0.0
        for row in rows:
            if not isinstance(row, dict) or not str(row.get('category') or '').strip():
                raise ValueError('Pre-opening ' + kind + ' requires a category')
            value = row.get('total', 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Pre-opening ' + kind + ' must be finite non-negative dollars')
            total += value
        if not math.isfinite(total): raise ValueError('Pre-opening total must be finite')
        amounts[kind] = total
    amounts['net_income'] = amounts['incomes'] - amounts['expenses']
    return amounts
