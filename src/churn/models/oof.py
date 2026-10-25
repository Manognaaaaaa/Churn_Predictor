"""Out-of-fold scoring: every customer is scored by a model that never saw their label.

The step-4 model is fitted on the train split, so scoring the whole population with it leaves 70% of
customers scored in-sample (their labels were memorised). Here the chosen model (same hyper-parameters,
same imbalance strategy) is refitted 5 times; each customer is scored by the fold model that held
them out. Calibration (same method as step 4) is then fitted on the out-of-fold raw scores.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold

from churn.models import calibrate as cal


def oof_raw_scores(model, x: np.ndarray, y: np.ndarray, resample, folds: int, seed: int) -> np.ndarray:
    """Out-of-fold raw P(churn). `resample(x, y)` is the step-4 imbalance strategy (train folds only)."""
    p = np.zeros(len(y), float)
    for tr, va in StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(x, y):
        xr, yr = resample(x[tr], y[tr])
        p[va] = clone(model).fit(xr, yr).predict_proba(x[va])[:, 1]
    return p


def calibrate_oof(p_raw: np.ndarray, y: np.ndarray, method: str) -> tuple[object, np.ndarray]:
    """Fit the named calibrator on the out-of-fold scores and apply it."""
    if method == "platt":
        m = cal.platt_fit(p_raw, y)
        return m, cal.platt_apply(m, p_raw)
    m = cal.isotonic_fit(p_raw, y)
    return m, cal.isotonic_apply(m, p_raw)


def raw_feature_values(raw: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Unscaled value of every model feature, from the raw customer table (aligned to `raw`)."""
    out = {}
    for f in feature_cols:
        if f == "customer_value":
            out[f] = raw["EstimatedSalary"].astype(float)
        elif f == "balance_value_ratio":
            out[f] = raw["Balance"] / raw["EstimatedSalary"].replace(0, np.nan)
        elif f == "zero_balance":
            out[f] = (raw["Balance"] == 0).astype(float)
        elif f.startswith("Geography_"):
            out[f] = (raw["Geography"] == f.split("_", 1)[1]).astype(float)
        elif f.startswith("Gender_"):
            out[f] = (raw["Gender"] == f.split("_", 1)[1]).astype(float)
        else:
            out[f] = raw[f].astype(float)
    return pd.DataFrame(out)


def distribution(p: np.ndarray, bands: np.ndarray) -> dict:
    """Summary of a probability vector, for the before/after leakage report."""
    q = np.quantile(p, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    return {"mean": float(p.mean()),
            "quantiles": {k: float(v) for k, v in zip(["p10", "p25", "p50", "p75", "p90", "p99"], q)},
            "n_ge_0.99": int((p >= 0.99).sum()), "n_le_0.01": int((p <= 0.01).sum()),
            "n_eq_1": int((p >= 0.9999).sum()),
            "band_counts": {k: int((bands == k).sum()) for k in ["green", "amber", "red"]}}


def crossfit_calibrated(p_raw: np.ndarray, y: np.ndarray, method: str, folds: int, seed: int) -> np.ndarray:
    """Calibrated scores where each customer's calibrator never saw their own label.

    The calibrator used on the dashboard is fitted on all out-of-fold scores and applied to the same
    customers, which flatters ECE. Here it is fitted on the other folds only, so the error is honest.
    """
    from sklearn.model_selection import StratifiedKFold

    out = np.zeros(len(y), float)
    for tr, va in StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(p_raw.reshape(-1, 1), y):
        m, _ = calibrate_oof(p_raw[tr], y[tr], method)
        out[va] = cal.platt_apply(m, p_raw[va]) if method == "platt" else cal.isotonic_apply(m, p_raw[va])
    return out
