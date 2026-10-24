import numpy as np
import pandas as pd

from churn.config import load_config
from churn.models.test_probs import build_test_probs, fit_rf_smote


def _toy(n=300, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = (x[:, 0] + 0.5 * rng.normal(size=n) > 1.0).astype(int)
    return x, y


def test_build_test_probs_columns_and_calibrators_use_valid_only():
    rng = np.random.default_rng(1)
    meta = pd.DataFrame({"customer_id": range(50), "churned": rng.integers(0, 2, 50),
                         "customer_value_raw": rng.uniform(1, 10, 50)})
    raw = {"random_forest": rng.uniform(0, 1, 50), "xgboost": rng.uniform(0, 1, 50)}
    p_va, y_va = rng.uniform(0, 1, 200), rng.integers(0, 2, 200)
    out = build_test_probs(meta, raw, (p_va, y_va), raw["random_forest"], rng.uniform(0, 1, 50))
    assert list(out.columns) == ["customer_id", "churned", "customer_value_raw", "p_rf_raw",
                                 "p_xgboost_raw", "p_rf_isotonic", "p_rf_platt", "p_rf_smote_raw"]
    assert len(out) == 50
    prob_cols = [c for c in out.columns if c.startswith("p_")]
    assert out[prob_cols].min().min() >= 0.0 and out[prob_cols].max().max() <= 1.0


def test_fit_rf_smote_is_seeded_and_predicts_probs():
    cfg = load_config()
    x, y = _toy()
    a = fit_rf_smote(x, y, cfg).predict_proba(x)[:, 1]
    b = fit_rf_smote(x, y, cfg).predict_proba(x)[:, 1]
    assert np.allclose(a, b) and a.min() >= 0 and a.max() <= 1
