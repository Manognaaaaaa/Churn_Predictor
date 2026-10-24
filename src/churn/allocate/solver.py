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

    a, tau are per-customer arrays (a_i = a_g, tau_i = t_g * v_i). Total spend is monotone
    decreasing in lam, so bisection finds the lam where it equals the budget.
    """
    b, tau = _b(p, v, a), np.asarray(tau, float)
    B = min(budget, cap * len(b))

    def spend(lam: float) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            s = tau * np.log(np.maximum(b, 1e-300) / (tau * lam))
        return np.clip(np.nan_to_num(s, nan=0.0, neginf=0.0), 0.0, cap)

    lo, hi = 1e-300, float((b / tau).max()) * (1 + 1e-9)   # at hi every x_i = 0
    for _ in range(300):
        mid = np.sqrt(lo * hi)                              # bisect in log space
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


def strategy_comparison(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray,
                        budget: float, cap: float) -> dict:
    """Interim comparison (rewritten with all baselines in Phase 8.3)."""
    n = len(p)
    strat = {"segment_aware_kkt": kkt_allocate(p, v, a, tau, budget, cap),
             "uniform": np.full(n, min(budget / n, cap))}
    share = v * p / max((v * p).sum(), 1e-12)
    strat["risk_proportional"] = np.minimum(share * budget, cap)
    return {name: {"spend": float(x.sum()),
                   "expected_revenue_saved": float(expected_saved(x, p, v, a, tau).sum()),
                   "n_targeted": int((x > 0.5).sum())}
            for name, x in strat.items()}


def sensitivity(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray,
                budget: float, cap: float, perturb: float = 0.30) -> list[dict]:
    """Interim ±perturb sensitivity on a and tau (rewritten in Phase 8.5)."""
    rows = []
    for label, (fa, ft) in {"base": (1.0, 1.0), "a_low": (1 - perturb, 1.0),
                            "a_high": (1 + perturb, 1.0), "tau_low": (1.0, 1 - perturb),
                            "tau_high": (1.0, 1 + perturb)}.items():
        x = kkt_allocate(p, v, a * fa, tau * ft, budget, cap)
        rows.append({"scenario": label, "a_factor": fa, "tau_factor": ft,
                     "expected_revenue_saved":
                         float(expected_saved(x, p, v, a * fa, tau * ft).sum())})
    return rows


def calibrated_vs_uncalibrated(p_cal: np.ndarray, p_raw: np.ndarray, v: np.ndarray,
                               a: np.ndarray, tau: np.ndarray, budget: float,
                               cap: float) -> dict:
    """Interim (circular: scores both with p_cal). Replaced by the label-based test in 8.4."""
    x_cal = kkt_allocate(p_cal, v, a, tau, budget, cap)
    x_raw = kkt_allocate(p_raw, v, a, tau, budget, cap)
    truth_cal = expected_saved(x_cal, p_cal, v, a, tau).sum()
    truth_raw = expected_saved(x_raw, p_cal, v, a, tau).sum()
    return {"saved_calibrated_allocation": float(truth_cal),
            "saved_uncalibrated_allocation": float(truth_raw),
            "misallocation_cost": float(truth_cal - truth_raw)}
