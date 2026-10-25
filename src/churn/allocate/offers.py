"""Stage 2 of allocation: snap solved spend to real offers and re-balance the budget.

Stage 1 (any strategy) gives a continuous spend x_i. Here each customer gets the cheapest
eligible offer whose cost covers x_i (or the largest eligible one if none does). Spend becomes the
offer's actual cost, so the total can overshoot the budget; the budget handed to stage 1 is
re-balanced (scale, then bisect) until the snapped total is as close to the budget as possible.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

NO_OFFER = "none"


def offer_matrix(v: np.ndarray, tiers: np.ndarray, engagement: np.ndarray,
                 catalog: dict, cap: float) -> tuple[list[str], np.ndarray]:
    """(offer names, n x K cost matrix); cost is inf where the offer is ineligible or above cap."""
    names = list(catalog)
    v, tiers, engagement = np.asarray(v, float), np.asarray(tiers), np.asarray(engagement)
    cost = np.full((len(v), len(names)), np.inf)
    for k, name in enumerate(names):
        o = catalog[name]
        c = o["flat"] + o["cost_frac"] * v
        ok = (np.isin(tiers, o["eligible"]["tiers"])
              & np.isin(engagement, o["eligible"]["engagement"]) & (c <= cap))
        cost[ok, k] = c[ok]
    return names, cost


def snap_to_offers(x: np.ndarray, cost: np.ndarray, names: list[str],
                   min_spend: float) -> tuple[np.ndarray, np.ndarray]:
    """Cheapest eligible offer with cost >= x (else the largest eligible). Returns (offer, spend)."""
    x = np.asarray(x, float)
    covers = np.where(cost >= x[:, None], cost, np.inf)
    pick_up = covers.argmin(axis=1)
    has_cover = np.isfinite(covers.min(axis=1))
    largest = np.where(np.isfinite(cost), cost, -np.inf)
    pick = np.where(has_cover, pick_up, largest.argmax(axis=1))
    spend = cost[np.arange(len(x)), pick]
    active = (x >= min_spend) & np.isfinite(spend)
    offer = np.where(active, np.asarray(names, dtype=object)[pick], NO_OFFER)
    return offer, np.where(active, spend, 0.0)


def allocate_with_offers(solve: Callable[[float], np.ndarray], v: np.ndarray,
                         tiers: np.ndarray, engagement: np.ndarray, budget: float,
                         cap: float, catalog: dict, min_spend: float,
                         max_iter: int, tol: float = 1e-3) -> dict:
    """Two-stage allocation: solve(B') -> continuous spend, snap to offers, re-balance B'.

    Snapping can overshoot (rounding up to the next offer) or undershoot (a group whose largest
    offer is below the solved spend). B' is scaled proportionally, then bisected, to get the
    snapped total as close to `budget` as possible without exceeding it (within `tol`).
    If no feasible B' is found in max_iter rounds, the lowest-priority (smallest solved spend)
    targeted customers are dropped until the budget holds, so total spend <= budget always.
    """
    names, cost = offer_matrix(v, tiers, engagement, catalog, cap)
    best, last_over = None, None
    lo, hi = None, None                       # lo: B' that fit (total <= budget); hi: B' that overshot
    b_eff = float(budget)
    for it in range(1, max_iter + 1):
        x = solve(b_eff)
        offer, spend = snap_to_offers(x, cost, names, min_spend)
        total = float(spend.sum())
        res = {"x_solved": x, "offer": offer, "spend": spend, "iterations": it,
               "effective_budget": b_eff, "dropped": 0}
        if total <= budget:
            if best is None or total > best["spend"].sum():
                best = res
            lo = b_eff if lo is None else max(lo, b_eff)
            if total >= (1 - tol) * budget:
                return res
        else:
            hi = b_eff if hi is None else min(hi, b_eff)
            last_over = res
        if lo is not None and hi is not None:
            b_eff = (lo + hi) / 2.0
        else:                                  # not bracketed yet: scale proportionally
            b_eff = b_eff * budget / max(total, 1e-12) * (1 + 1e-3 if total <= budget else 1 - 1e-3)
        if lo is not None and hi is not None and hi - lo < 1e-9 * budget:
            break
    if best is not None:
        best["iterations"] = it
        return best
    res = last_over                            # nothing fit: drop lowest priority
    for i in np.argsort(res["x_solved"]):
        if res["spend"].sum() <= budget:
            break
        if res["spend"][i] > 0:
            res["spend"][i], res["offer"][i] = 0.0, NO_OFFER
            res["dropped"] += 1
    res["iterations"] = it
    return res
