"""Evaluation metrics: PR-AUC, Brier, ECE, cost-based threshold."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss


def ece(y_true: np.ndarray, p: np.ndarray, n_bins: int = 15) -> float:
    """Expected calibration error over equal-width bins."""
    y_true, p = np.asarray(y_true), np.asarray(p)
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    total, e = len(p), 0.0
    for b in range(n_bins):
        m = bins == b
        if m.sum() == 0:
            continue
        e += (m.sum() / total) * abs(y_true[m].mean() - p[m].mean())
    return float(e)


def pr_auc(y_true, p) -> float:
    return float(average_precision_score(y_true, p))


def brier(y_true, p) -> float:
    return float(brier_score_loss(y_true, p))


def calibration_curve(y_true, p, n_bins: int = 15) -> list[dict]:
    y_true, p = np.asarray(y_true, float), np.asarray(p, float)
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    out = []
    for b in range(n_bins):
        m = bins == b
        if m.sum() == 0:
            continue
        out.append({"bin_mean_pred": float(p[m].mean()),
                    "bin_frac_pos": float(y_true[m].mean()),
                    "n": int(m.sum())})
    return out


def cost_threshold(p, customer_value: np.ndarray, offer_cost_frac: float = 0.10,
                   offer_uplift: float = 0.30, fn_cost_multiple: float = 4.0) -> dict:
    """Expected-cost decision threshold (calibrated probabilities).

    Not targeting a customer costs fn_cost_multiple x p x value (lost value when
    they churn). Targeting costs offer_cost_frac x value plus the residual
    (1 - offer_uplift) x p x value of still churning. Flags the customers above
    the threshold that minimises total expected cost.
    """
    p = np.asarray(p, float)
    v = np.asarray(customer_value, float)
    order = np.argsort(-p)
    p_s, v_s = p[order], v[order]

    flag_cost = offer_cost_frac * v_s + (1.0 - offer_uplift) * p_s * v_s
    skip_cost = fn_cost_multiple * p_s * v_s
    gain = skip_cost - flag_cost          # positive -> worth flagging
    cum_gain = np.cumsum(gain)
    # flag the first i customers; total expected cost = sum(skip) - cum_gain[i]
    total_skip = skip_cost.sum()
    i_best = int(np.argmax(cum_gain))
    if cum_gain[i_best] <= 0:
        i_best = -1                        # nobody worth targeting
    n_flagged = i_best + 1
    threshold = float(p_s[n_flagged - 1]) if n_flagged > 0 else 1.0
    return {"threshold": threshold, "n_flagged": n_flagged,
            "cost": float(total_skip - (cum_gain[i_best] if n_flagged > 0 else 0.0))}
