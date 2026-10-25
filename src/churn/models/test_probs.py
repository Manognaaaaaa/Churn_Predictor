"""Test-split probability table for the Step 8 claim tests (calibration vs ranking).

Everything fit here (RF calibrators, the SMOTE variant) uses train/valid only;
the test split is only scored.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier

from churn.models import calibrate as cal

# zoo key -> short column stem used in test_probs.parquet
COLUMN_STEM = {"logreg_mle": "logreg_mle", "logreg_map": "logreg_map",
               "naive_bayes": "naive_bayes", "random_forest": "rf",
               "xgboost": "xgboost", "lstm": "lstm"}


def fit_rf_smote(x_train: np.ndarray, y_train: np.ndarray, cfg: dict) -> RandomForestClassifier:
    """Random Forest trained on SMOTE-resampled *training* rows only (miscalibrated on purpose)."""
    x_rs, y_rs = SMOTE(random_state=cfg["seed"]).fit_resample(x_train, y_train)
    rf = cfg["models"]["rf"]
    model = RandomForestClassifier(n_estimators=rf["n_estimators"],
                                   min_samples_leaf=rf["min_samples_leaf"],
                                   random_state=cfg["seed"], n_jobs=-1)
    return model.fit(x_rs, y_rs)


def build_test_probs(test_meta: pd.DataFrame, raw_probs: dict[str, np.ndarray],
                     rf_valid: tuple[np.ndarray, np.ndarray], rf_test_raw: np.ndarray,
                     rf_smote_test: np.ndarray) -> pd.DataFrame:
    """Assemble the test-split table.

    test_meta: customer_id, churned, customer_value_raw for the test rows.
    raw_probs: zoo key -> raw test probabilities (same row order as test_meta).
    rf_valid: (raw RF valid probs, valid labels) used to fit Platt/isotonic.
    """
    p_va, y_va = rf_valid
    out = test_meta[["customer_id", "churned", "customer_value_raw"]].reset_index(drop=True).copy()
    for key, p in raw_probs.items():
        out[f"p_{COLUMN_STEM[key]}_raw"] = np.asarray(p, float)
    out["p_rf_isotonic"] = cal.isotonic_apply(cal.isotonic_fit(p_va, y_va), rf_test_raw)
    out["p_rf_platt"] = cal.platt_apply(cal.platt_fit(p_va, y_va), rf_test_raw)
    out["p_rf_smote_raw"] = np.asarray(rf_smote_test, float)
    return out
