"""Probability calibration (Platt scaling / isotonic), fitted on the valid split."""
from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


def platt_fit(p_valid: np.ndarray, y_valid: np.ndarray) -> LogisticRegression:
    lr = LogisticRegression()
    lr.fit(np.asarray(p_valid, float).reshape(-1, 1), np.asarray(y_valid, int))
    return lr


def isotonic_fit(p_valid: np.ndarray, y_valid: np.ndarray) -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(p_valid, float), np.asarray(y_valid, int))
    return iso


def platt_apply(model: LogisticRegression, p: np.ndarray) -> np.ndarray:
    return model.predict_proba(np.asarray(p, float).reshape(-1, 1))[:, 1]


def isotonic_apply(model: IsotonicRegression, p: np.ndarray) -> np.ndarray:
    return np.clip(model.predict(np.asarray(p, float)), 0.0, 1.0)


def fit_best(p_valid, y_valid, methods=("platt", "isotonic")) -> dict:
    """Fit every method, keep the one with the lowest valid Brier score."""
    from churn.models.metrics import brier

    fitted = {}
    if "platt" in methods:
        m = platt_fit(p_valid, y_valid)
        fitted["platt"] = (m, platt_apply(m, p_valid))
    if "isotonic" in methods:
        m = isotonic_fit(p_valid, y_valid)
        fitted["isotonic"] = (m, isotonic_apply(m, p_valid))
    scored = {name: brier(y_valid, cal) for name, (_, cal) in fitted.items()}
    best_name = min(scored, key=scored.get)
    best_model = fitted[best_name][0]
    return {"name": best_name, "model": best_model, "valid_brier": scored}
