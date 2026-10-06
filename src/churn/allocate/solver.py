"""Step 6: budget allocation under concave response curves.

Response model (assumption, documented in the report): spending s on a customer
with value v and churn probability p yields expected saved revenue
    r(s) = v * p * u_max * (1 - exp(-s / tau)),
a concave curve with diminishing returns. Maximising total r subject to
sum(s) = B, 0 <= s <= cap has KKT conditions
    b/tau * exp(-s/tau) = lambda  with b = v * p * u_max
=>  s_i(λ) = clip(tau_i * ln(b_i / (tau_i * λ)), 0, cap)
and λ is found by bisection (water-filling). A projected-gradient solver
cross-checks the optimum.
"""
from __future__ import annotations

import numpy as np

OFFER_CATALOG = {
    "discount_10": {"cost_frac": 0.10, "flat": 0.0},    # 10% of customer value
    "service_call": {"cost_frac": 0.0, "flat": 100.0},  # flat retention call
    "loyalty_email": {"cost_frac": 0.0, "flat": 5.0},   # near-free touch
}


def _curves(p: np.ndarray, v: np.ndarray, u_max: float, tau_frac: float):
    b = v * p * u_max
    tau = np.maximum(tau_frac * v, 1e-6)
    return b, tau


def kkt_allocate(p: np.ndarray, v: np.ndarray, budget: float, cap: float,
                 u_max: float = 0.30, tau_frac: float = 0.05) -> np.ndarray:
    b, tau = _curves(p, v, u_max, tau_frac)
    cap = min(cap, float(b.sum() / max(len(b), 1)) * 1e9)  # cap never binds totals
    total_cap = cap * len(b)
    B = min(budget, total_cap)

    def spend(lam):
        with np.errstate(divide="ignore", invalid="ignore"):
            s = tau * np.log(np.maximum(b, 1e-12) / (tau * lam))
        return np.clip(s, 0.0, cap)

    lo, hi = 1e-12, float(b.max() / tau.min()) * 10
    for _ in range(200):
        mid = (lo + hi) / 2
        if spend(mid).sum() > B:
            lo = mid
        else:
            hi = mid
    s = spend((lo + hi) / 2)
    if s.sum() > B:                       # shave rounding overflow
        excess = s.sum() - B
        idx = np.argsort(-s)
        s[idx[0]] = max(0.0, s[idx[0]] - excess)
    return s


def gradient_check(p: np.ndarray, v: np.ndarray, budget: float, cap: float,
                   u_max: float = 0.30, tau_frac: float = 0.05,
                   iters: int = 12000, lr_s: float = 0.5, lr_lam: float = 0.05,
                   ) -> tuple[np.ndarray, float]:
    """Dual projected gradient ascent on the Lagrangian (KKT cross-check).

    L(s, lambda) = sum_i r_i(s_i) - lambda * (sum_i s_i - B), s_i in [0, cap],
    lambda >= 0. Alternates spend ascent (on dL/ds = r'(s) - lambda) with
    multiplier ascent (lambda += lr * surplus). Converges to the KKT point.
    """
    b, tau = _curves(p, v, u_max, tau_frac)
    B = min(budget, cap * len(b))
    s = np.full(len(b), B / len(b))
    lam = 0.0
    for t in range(1, iters + 1):
        grad = (b / tau) * np.exp(-s / tau) - lam
        s = np.clip(s + lr_s * grad, 0.0, cap)
        lam = max(0.0, lam + lr_lam * (s.sum() - B))
        # decaying step sizes for convergence
        if t % 2000 == 0:
            lr_s *= 0.5
            lr_lam *= 0.5
    obj = float((b * (1 - np.exp(-s / tau))).sum())
    return s, obj


def expected_saved(s: np.ndarray, p: np.ndarray, v: np.ndarray,
                   u_max: float = 0.30, tau_frac: float = 0.05) -> np.ndarray:
    b, tau = _curves(p, v, u_max, tau_frac)
    return b * (1 - np.exp(-s / tau))


def match_offer(spend: float, value: float) -> str:
    """Pick the catalog offer whose cost is closest to the solved spend."""
    best, best_gap = "loyalty_email", float("inf")
    for name, o in OFFER_CATALOG.items():
        cost = o["cost_frac"] * value + o["flat"]
        gap = abs(cost - spend)
        if gap < best_gap:
            best, best_gap = name, gap
    return best


def strategy_comparison(p: np.ndarray, v: np.ndarray, budget: float, cap: float,
                        u_max: float = 0.30, tau_frac: float = 0.05) -> dict:
    n = len(p)
    strat = {}
    strat["segment_aware_kkt"] = kkt_allocate(p, v, budget, cap, u_max, tau_frac)
    uniform = np.full(n, min(budget / n, cap))
    strat["uniform"] = uniform
    share = v * p / max((v * p).sum(), 1e-12)
    strat["risk_proportional"] = np.minimum(share * budget, cap)

    out = {name: {"spend": float(s.sum()),
                  "expected_revenue_saved": float(expected_saved(s, p, v, u_max, tau_frac).sum()),
                  "n_targeted": int((s > 0.5).sum())}
           for name, s in strat.items()}
    return out


def sensitivity(p: np.ndarray, v: np.ndarray, budget: float, cap: float,
                u_max: float = 0.30, tau_frac: float = 0.05,
                perturb: float = 0.30) -> list[dict]:
    """±perturb on the assumed response-curve parameters."""
    rows = []
    for label, (u, t) in {
        "base": (u_max, tau_frac),
        "uplift_low": (u_max * (1 - perturb), tau_frac),
        "uplift_high": (u_max * (1 + perturb), tau_frac),
        "tau_low": (u_max, tau_frac * (1 - perturb)),
        "tau_high": (u_max, tau_frac * (1 + perturb)),
    }.items():
        s = kkt_allocate(p, v, budget, cap, u, t)
        rows.append({"scenario": label, "u_max": u, "tau_frac": t,
                     "expected_revenue_saved": float(expected_saved(s, p, v, u, t).sum())})
    return rows


def calibrated_vs_uncalibrated(p_cal: np.ndarray, p_raw: np.ndarray, v: np.ndarray,
                               budget: float, cap: float,
                               u_max: float = 0.30, tau_frac: float = 0.05) -> dict:
    """Spend chosen with raw scores, evaluated under calibrated probabilities
    (which we treat as the ground-truth-ish view). Validates README claim 1."""
    s_cal = kkt_allocate(p_cal, v, budget, cap, u_max, tau_frac)
    s_raw = kkt_allocate(p_raw, v, budget, cap, u_max, tau_frac)
    truth_cal = expected_saved(s_cal, p_cal, v, u_max, tau_frac).sum()
    truth_raw = expected_saved(s_raw, p_cal, v, u_max, tau_frac).sum()
    return {
        "saved_calibrated_allocation": float(truth_cal),
        "saved_uncalibrated_allocation": float(truth_raw),
        "misallocation_cost": float(truth_cal - truth_raw),
    }
