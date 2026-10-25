"""Step 6: budget allocation under concave response curves.

Response model (assumption, documented in the report): spending x on a customer
with value v and churn probability p yields expected saved revenue
    r(x) = p * v * a * (1 - exp(-x / tau)),   tau = t_g * v,
a concave curve with diminishing returns; a and tau are per-customer (group-level
a_g, t_g, see allocate/groups.py). Maximising total r subject to sum(x) <= B,
0 <= x <= cap has KKT conditions
    b/tau * exp(-x/tau) = lambda  with b = p v a
=>  x_i(lam) = clip(tau_i * ln(b_i / (tau_i * lam)), 0, cap)
and lam is found by bisection (water-filling). A dual projected-gradient solver
cross-checks the optimum.
"""
from __future__ import annotations

import numpy as np

def _b(p: np.ndarray, v: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Maximum saveable revenue per customer, b_i = p_i * v_i * a_i."""
    return np.asarray(p, float) * np.asarray(v, float) * np.asarray(a, float)


def kkt_allocate(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray,
                 budget: float, cap: float) -> np.ndarray:
    """Closed-form KKT spend x_i(lam) = clip(tau_i ln(b_i / (tau_i lam)), 0, cap), lam by bisection.

    a, tau (and optionally cap) are per-customer arrays (a_i = a_g, tau_i = t_g * v_i).
    Total spend is monotone
    decreasing in lam, so bisection finds the lam where it equals the budget.
    """
    b, tau = _b(p, v, a), np.asarray(tau, float)
    cap_arr = np.broadcast_to(np.asarray(cap, float), b.shape)   # scalar or per-customer cap
    B = min(budget, float(cap_arr.sum()))
    if len(b) == 0 or b.max() <= 0 or B <= 0:
        return np.zeros(len(b))

    log_ratio = np.log(np.maximum(b, 1e-300) / tau)         # ln(b_i / tau_i), reused every step

    def spend(log_lam: float) -> np.ndarray:
        return np.clip(tau * (log_ratio - log_lam), 0.0, cap_arr)

    lo = float((log_ratio - cap_arr / tau).min()) - 1.0       # lo: every x_i at its cap
    hi = float(log_ratio.max()) + 1e-9                        # hi: every x_i = 0
    for _ in range(100):                                    # bisect on ln(lambda)
        mid = 0.5 * (lo + hi)
        if spend(mid).sum() > B:
            lo = mid
        else:
            hi = mid
    return spend(hi)                                        # hi side: total <= B


def gradient_check(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray,
                   budget: float, cap: float, iters: int = 12000, lr_s: float = 0.5,
                   lr_lam: float = 0.05) -> tuple[np.ndarray, float]:
    """Dual projected gradient ascent on the Lagrangian (KKT cross-check).

    L(x, lambda) = sum_i r_i(x_i) - lambda * (sum_i x_i - B), x_i in [0, cap],
    lambda >= 0. Alternates spend ascent (on dL/dx = r'(x) - lambda) with
    multiplier ascent (lambda += lr * surplus). Converges to the KKT point.
    """
    b, tau = _b(p, v, a), np.asarray(tau, float)
    B = min(budget, cap * len(b))
    x = np.full(len(b), B / len(b))
    lam = 0.0
    for t in range(1, iters + 1):
        grad = (b / tau) * np.exp(-x / tau) - lam
        x = np.clip(x + lr_s * grad, 0.0, cap)
        lam = max(0.0, lam + lr_lam * (x.sum() - B))
        if t % 2000 == 0:                                   # decaying step sizes
            lr_s *= 0.5
            lr_lam *= 0.5
    return x, float((b * (1 - np.exp(-x / tau))).sum())


def expected_saved(x: np.ndarray, p: np.ndarray, v: np.ndarray, a: np.ndarray,
                   tau: np.ndarray) -> np.ndarray:
    """Per-customer expected saved revenue r_i(x_i) = p v a (1 - exp(-x/tau))."""
    return _b(p, v, a) * (1 - np.exp(-np.asarray(x, float) / np.asarray(tau, float)))
