"""Shared search routines for the Bank Design Lab and reverse stress (r501).

Derivative-free and honest: every evaluation is a real engine run supplied by the caller, ``None`` means
"could not evaluate here", and nothing assumes a single crossing.
"""
from __future__ import annotations


def bisect(f, a, b, fa, *, tol, budget):
    """Bisection on a bracket [a, b] with f(a) = fa and a sign change inside.

    ``budget()`` returns False when the caller's evaluation budget is spent. Returns the last midpoint
    (or the converged one); the Lab's goal seek and reverse stress both use this exact loop."""
    sol = None
    while budget():
        mid = 0.5 * (a + b)
        fm = f(mid)
        if fm is None:
            break
        if abs(fm) <= tol or (b - a) < tol * max(1.0, abs(mid)) * 1e-3:
            sol = mid
            break
        if fa * fm < 0:
            b = mid
        else:
            a, fa = mid, fm
        sol = mid
    return sol


def bisect_x(f, a, b, fa, *, xtol, budget):
    """Bisection until the bracket is narrower than ``xtol`` in x. Returns (a, b) with the sign change inside."""
    while (b - a) > xtol and budget():
        mid = 0.5 * (a + b)
        fm = f(mid)
        if fm is None:
            break
        if (fa < 0) == (fm < 0):
            a, fa = mid, fm
        else:
            b = mid
    return a, b


def grid(lo, hi, n):
    n = max(2, int(n))
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def sign_changes(points):
    """Adjacent grid points whose values differ in sign (None points are skipped)."""
    pts = [(x, y) for x, y in points if y is not None]
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1) if (pts[i][1] < 0) != (pts[i + 1][1] < 0)]


def monotonic(points):
    ys = [y for _, y in points if y is not None]
    return all(b <= a + 1e-12 for a, b in zip(ys, ys[1:])) or all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))
