"""Claim 2 experiments: strategy comparison at one budget and a budget sweep."""
from __future__ import annotations

import numpy as np

from churn.allocate import strategies as st
from churn.allocate.evaluate import bootstrap_ci
from churn.allocate import solver as sv


def strategy_table(pr: st.Problem, y: np.ndarray, budget: float, acfg: dict) -> dict:
    """Per strategy: continuous and offer-snapped evaluation at the same budget."""
    out = {}
    for name in st.STRATEGY_NAMES:
        x = st.allocate(name, pr, budget)
        snap = st.allocate_snapped(name, pr, budget, acfg)
        out[name] = {"continuous": st.evaluate(pr, x, y, acfg["min_spend"]),
                     "snapped": st.evaluate(pr, snap["spend"], y, acfg["min_spend"])}
    return out


def realized_paired_bootstrap(pr: st.Problem, y: np.ndarray, budget: float, a_name: str,
                              b_name: str, n_boot: int, seed: int, level: float) -> dict:
    """Bootstrap CI (over customers) of realized saved(a_name) - realized saved(b_name), fixed spends."""
    def per_customer(name: str) -> np.ndarray:
        x = st.allocate(name, pr, budget)
        return y * sv.expected_saved(x, np.ones_like(pr.p), pr.v, pr.a, pr.tau)

    diff = per_customer(a_name) - per_customer(b_name)
    mean, lo, hi = bootstrap_ci(diff, n_boot, seed, level)
    return {"a": a_name, "b": b_name, "diff": mean, "lo": lo, "hi": hi, "level": level}


def budget_sweep(pr: st.Problem, y: np.ndarray, budgets: list[float], scale: float,
                 acfg: dict) -> list[dict]:
    """Expected saved revenue per strategy over a grid of portfolio budgets (scaled to the split)."""
    rows = []
    for B in budgets:
        b = B * scale
        for name in st.STRATEGY_NAMES:
            x = st.allocate(name, pr, b)
            snap = st.allocate_snapped(name, pr, b, acfg)
            rows.append({"portfolio_budget": B, "split_budget": b, "strategy": name,
                         "saved_continuous": st.evaluate(pr, x)["expected_revenue_saved"],
                         "saved_snapped": st.evaluate(pr, snap["spend"])["expected_revenue_saved"],
                         "spend_snapped": float(snap["spend"].sum())})
    return rows
