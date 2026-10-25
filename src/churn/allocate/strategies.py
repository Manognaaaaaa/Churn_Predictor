"""Allocation strategies compared at equal budget (Step 8 claim 2).

Every strategy returns a continuous spend vector. All are *evaluated* under the same
segment-aware response model (a, tau); they differ only in what they assume or ignore when
choosing the spend:

- segment_aware_kkt: KKT with the group-level a_g, t_g (the true-by-assumption model)
- global_kkt: same solver, one global a and t (isolates what segments add)
- uniform: B / n to everyone, capped
- top_k_risk: highest p first, each gets the cap until the budget runs out
- top_k_revenue_at_risk: highest p * v first, same rule
- risk_proportional: spend proportional to p * v, capped
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from churn.allocate import offers as of
from churn.allocate import solver as sv

STRATEGY_NAMES = ["segment_aware_kkt", "global_kkt", "uniform", "top_k_risk",
                  "top_k_revenue_at_risk", "risk_proportional"]


@dataclass
class Problem:
    """One allocation instance. a, tau: group-level truth; a_glob, tau_glob: global assumption."""
    p: np.ndarray
    v: np.ndarray
    a: np.ndarray
    tau: np.ndarray
    a_glob: np.ndarray
    tau_glob: np.ndarray
    cap: float
    tiers: np.ndarray
    engagement: np.ndarray


def top_k(score: np.ndarray, budget: float, cap: float) -> np.ndarray:
    """Give the cap to customers in descending score order until the budget runs out."""
    x = np.zeros(len(score))
    remaining = float(budget)
    for i in np.argsort(-score, kind="stable"):
        if remaining <= 0:
            break
        x[i] = min(cap, remaining)
        remaining -= x[i]
    return x


def allocate(name: str, pr: Problem, budget: float) -> np.ndarray:
    """Continuous spend for one strategy at the given budget."""
    if name == "segment_aware_kkt":
        return sv.kkt_allocate(pr.p, pr.v, pr.a, pr.tau, budget, pr.cap)
    if name == "global_kkt":
        return sv.kkt_allocate(pr.p, pr.v, pr.a_glob, pr.tau_glob, budget, pr.cap)
    if name == "uniform":
        return np.full(len(pr.p), min(budget / len(pr.p), pr.cap))
    if name == "top_k_risk":
        return top_k(pr.p, budget, pr.cap)
    if name == "top_k_revenue_at_risk":
        return top_k(pr.p * pr.v, budget, pr.cap)
    if name == "risk_proportional":
        share = pr.v * pr.p / max(float((pr.v * pr.p).sum()), 1e-12)
        return np.minimum(share * budget, pr.cap)
    raise ValueError(f"unknown strategy {name!r}")


def allocate_snapped(name: str, pr: Problem, budget: float, acfg: dict) -> dict:
    """Same strategy followed by offer snapping and budget re-balancing (stage 2)."""
    return of.allocate_with_offers(
        lambda b: allocate(name, pr, b), pr.v, pr.tiers, pr.engagement, budget, pr.cap,
        acfg["offers"], acfg["min_spend"], acfg["rebalance_max_iter"], acfg["rebalance_tol"])


def evaluate(pr: Problem, x: np.ndarray, y: np.ndarray | None = None,
             min_spend: float = 0.5) -> dict:
    """Spend, expected saved (model p), targeted count, saved per unit spend, realized saved (labels)."""
    saved = float(sv.expected_saved(x, pr.p, pr.v, pr.a, pr.tau).sum())
    out = {"spend": float(x.sum()), "expected_revenue_saved": saved,
           "n_targeted": int((x >= min_spend).sum()),
           "saved_per_spend": saved / max(float(x.sum()), 1e-12)}
    if y is not None:
        out["realized_revenue_saved"] = float(
            (np.asarray(y, float) * sv.expected_saved(x, np.ones_like(pr.p), pr.v, pr.a, pr.tau)).sum())
    return out


Strategy = Callable[[Problem, float], np.ndarray]
