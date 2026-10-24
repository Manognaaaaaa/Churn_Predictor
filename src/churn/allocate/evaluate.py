"""Evaluation helpers: realized saved revenue from true labels, bootstrap CIs, data loading."""
from __future__ import annotations

import numpy as np
import pandas as pd

from churn.allocate import groups as gp
from churn.allocate.strategies import Problem
from churn.config import ROOT


def realized_saved(x: np.ndarray, y: np.ndarray, v: np.ndarray, a: np.ndarray,
                   tau: np.ndarray) -> float:
    """sum_i y_i * v_i * a_i * (1 - exp(-x_i / tau_i)): uses the actual outcome, no model p."""
    return float((np.asarray(y, float) * v * a * (1 - np.exp(-np.asarray(x, float) / tau))).sum())


def bootstrap_ci(per_customer: np.ndarray, n_boot: int, seed: int,
                 level: float = 0.90) -> tuple[float, float, float]:
    """(mean, lo, hi) of the *sum* of per-customer values over customer resamples."""
    rng = np.random.default_rng(seed)
    n = len(per_customer)
    idx = rng.integers(0, n, size=(n_boot, n))
    sums = per_customer[idx].sum(axis=1)
    lo, hi = np.quantile(sums, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(per_customer.sum()), float(lo), float(hi)


def budget_scale(n_split: int, n_all: int) -> float:
    """Config budgets are for the whole portfolio; a split gets its population share."""
    return n_split / n_all


def load_eval_problem(cfg: dict, split: str = "test") -> tuple[Problem, np.ndarray, pd.DataFrame, float]:
    """Build the Problem for one split from artifacts. Returns (problem, y, frame, budget_scale)."""
    art = ROOT / cfg["paths"]["artifacts"]
    scores = pd.read_parquet(art / "scores.parquet")
    seg = pd.read_parquet(art / "segments.parquet")
    table = pd.read_parquet(art / "group_params.parquet")
    n_all = len(scores)
    sc = scores[scores["split"] == split].reset_index(drop=True)
    sc["customer_id"] = sc["customer_id"].astype(str)
    seg = seg.assign(customer_id=seg["customer_id"].astype(str)).set_index("customer_id")
    s = seg.loc[sc["customer_id"]]
    seg_ids, tiers = s["segment_id"].to_numpy(), s["value_tier"].to_numpy()
    v = sc["customer_value"].to_numpy(float)
    a, tau = gp.customer_params(seg_ids, tiers, table, v)
    ag, tg = gp.global_params(len(sc), v, cfg)
    eng = gp.customer_attr(seg_ids, tiers, table, "engagement_class")
    pr = Problem(p=sc["p_churn_calibrated"].to_numpy(float), v=v, a=a, tau=tau,
                 a_glob=ag, tau_glob=tg, cap=float(cfg["budget"]["max_spend_per_customer"]),
                 tiers=tiers, engagement=eng)
    frame = sc.assign(segment_id=seg_ids, value_tier=tiers, segment_name=s["segment_name"].to_numpy(),
                      engagement_class=eng)
    return pr, sc["churned"].to_numpy(int), frame, budget_scale(len(sc), n_all)
