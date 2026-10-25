"""Reallocation loop: monthly rounds versus a single up-front allocation of the same budget.

Assumptions (documented in reports/allocation.md; all are simulation assumptions):
- The horizon churn probability p_i is split into per-round hazards h_i = 1 - (1 - p_i)^(1/R),
  so a customer left alone for R rounds churns with probability p_i.
- An offer with cumulative spend X lowers a customer's churn probability from q to
  q * (1 - a * (1 - exp(-X/tau))) (the same response curve the solver optimises); the effect
  persists for the rest of the horizon in both the rounds plan and the one-shot plan.
- Churn is drawn with a common uniform u_i: without an offer the customer churns if u_i < q,
  with the offer if u_i < q_eff. Customers with q_eff <= u_i < q are *saved* (revenue v_i kept).
- Churned and saved customers leave the pool. Spend is debited only when delivered, so the share
  of budget that would have gone to a removed customer in later rounds stays in the pool.
- Each round solves the incremental KKT problem on the remaining customers with
  pool / (rounds left) as the round budget.
"""
from __future__ import annotations

import numpy as np

from churn.allocate import solver as sv


def offer_effect(x: np.ndarray, a: np.ndarray, tau: np.ndarray) -> np.ndarray:
    """Fraction of churn probability removed by spending x."""
    return a * (1.0 - np.exp(-np.asarray(x, float) / tau))


def one_shot(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray, budget: float,
             cap: float, rng: np.random.Generator) -> dict:
    """Allocate the whole budget up front on the horizon probabilities, then draw outcomes once."""
    x = sv.kkt_allocate(p, v, a, tau, budget, cap)
    u = rng.random(len(p))
    p_eff = p * (1.0 - offer_effect(x, a, tau))
    saved = (u < p) & ~(u < p_eff)
    return {"saved_value": float(v[saved].sum()), "spent": float(x.sum()),
            "n_saved": int(saved.sum())}


def simulate_rounds(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray, budget: float,
                    cap: float, rounds: int, rng: np.random.Generator) -> dict:
    """Run `rounds` monthly rounds with removal of churned/saved customers and a shared pool.

    Offer effect depends on a customer's cumulative spend X_i and persists, exactly as in the
    one-shot plan (so the comparison isolates adaptivity, not a different response model).
    The round-r problem is the *incremental* one: maximising h v a (e^{-X/tau})(1 - e^{-x/tau})
    over new spend x, with remaining cap (cap - X_i), which is the same KKT form.
    """
    n = len(p)
    hazard = 1.0 - (1.0 - p) ** (1.0 / rounds)
    alive = np.ones(n, bool)
    cum = np.zeros(n)                                  # cumulative spend per customer
    pool = float(budget)
    saved_value, n_saved = 0.0, 0
    spent_by_round, alive_history, x_history = [], [], []
    for r in range(rounds):
        alive_history.append(alive.copy())
        x = np.zeros(n)
        if alive.any() and pool > 0:
            a_inc = a * np.exp(-cum / tau)             # remaining headroom of the response curve
            x[alive] = sv.kkt_allocate(hazard[alive], v[alive], a_inc[alive], tau[alive],
                                       pool / (rounds - r), np.maximum(cap - cum[alive], 0.0))
        cum += x
        spent = float(x.sum())
        pool -= spent
        spent_by_round.append(spent)
        x_history.append(x)
        u = rng.random(n)
        q_eff = hazard * (1.0 - offer_effect(cum, a, tau))
        churned = alive & (u < q_eff)
        saved = alive & (u < hazard) & ~(u < q_eff)
        saved_value += float(v[saved].sum())
        n_saved += int(saved.sum())
        alive = alive & ~(churned | saved)
    return {"saved_value": saved_value, "spent": float(sum(spent_by_round)), "n_saved": n_saved,
            "spent_by_round": spent_by_round, "alive_history": alive_history,
            "x_history": x_history}


def compare(p: np.ndarray, v: np.ndarray, a: np.ndarray, tau: np.ndarray, budget: float,
            cap: float, rounds: int, n_seeds: int, seed: int, level: float) -> dict:
    """Rounds vs one-shot over n_seeds paired simulations: mean and central `level` interval."""
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    r_saved, o_saved, r_spent, o_spent = [], [], [], []
    for k in range(n_seeds):
        out_r = simulate_rounds(p, v, a, tau, budget, cap, rounds, np.random.default_rng([seed, k, 0]))
        out_o = one_shot(p, v, a, tau, budget, cap, np.random.default_rng([seed, k, 1]))
        r_saved.append(out_r["saved_value"])
        o_saved.append(out_o["saved_value"])
        r_spent.append(out_r["spent"])
        o_spent.append(out_o["spent"])
    r_saved, o_saved = np.array(r_saved), np.array(o_saved)

    def summ(x: np.ndarray) -> dict:
        return {"mean": float(x.mean()), "lo": float(np.quantile(x, lo_q)),
                "hi": float(np.quantile(x, hi_q))}

    diff = r_saved - o_saved
    se = float(diff.std(ddof=1) / np.sqrt(len(diff)))
    return {"rounds": rounds, "n_seeds": n_seeds, "level": level, "budget": budget,
            "rounds_saved": summ(r_saved), "one_shot_saved": summ(o_saved),
            "difference": {**summ(diff), "mean_se": se,
                           "share_seeds_rounds_better": float((diff > 0).mean())},
            "rounds_spent_mean": float(np.mean(r_spent)),
            "one_shot_spent_mean": float(np.mean(o_spent)),
            "max_spent": float(max(max(r_spent), max(o_spent)))}
