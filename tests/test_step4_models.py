import numpy as np
import pandas as pd
import pytest

from churn.models.calibrate import fit_best
from churn.models.metrics import cost_threshold, ece, pr_auc
from churn.models.explain import top_drivers


def test_ece_perfect_and_broken():
    y = np.array([0, 0, 1, 1, 0, 1])
    p = y.astype(float)  # perfectly calibrated
    assert ece(y, p) < 1e-9
    assert ece(y, np.ones_like(p) * 0.9) > 0.1


def test_pr_auc_bounds():
    y = np.array([0, 1, 0, 1])
    assert pr_auc(y, np.array([0.1, 0.9, 0.2, 0.8])) == 1.0
    assert pr_auc(y, np.array([0.1, 0.1, 0.1, 0.1])) == pytest.approx(0.5)


def test_cost_threshold_flag_count():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 500)
    v = np.full(500, 100_000.0)
    base = cost_threshold(p, v, offer_cost_frac=0.10, offer_uplift=0.30, fn_cost_multiple=4.0)
    strict = cost_threshold(p, v, offer_cost_frac=0.10, offer_uplift=0.30, fn_cost_multiple=0.5)
    assert base["n_flagged"] >= strict["n_flagged"]  # costlier misses -> more flagging
    assert 0.0 <= base["threshold"] <= 1.0
    # tiny values make offers pointless
    none = cost_threshold(p, np.full(500, 1.0), offer_cost_frac=0.10, offer_uplift=0.30,
                          fn_cost_multiple=4.0)
    assert none["n_flagged"] <= base["n_flagged"]


def test_fit_best_returns_valid_method():
    rng = np.random.default_rng(0)
    p = np.clip(rng.beta(2, 5, 400), 0.01, 0.99)
    y = (rng.random(400) < p).astype(int)
    out = fit_best(p, y)
    assert out["name"] in ("platt", "isotonic")
    assert set(out["valid_brier"]) == {"platt", "isotonic"}


def test_top_drivers_shape():
    from sklearn.ensemble import RandomForestClassifier
    rng = np.random.default_rng(0)
    x = pd.DataFrame(rng.normal(size=(60, 4)), columns=["f1", "f2", "f3", "f4"])
    y = (x["f1"] > 0).astype(int)
    model = RandomForestClassifier(n_estimators=10, random_state=0).fit(x, y)
    out = top_drivers(x, model, list(x.columns), k=3)
    assert len(out) == 60 and len(out[0]) == 3
    assert set(out[0][0]) == {"feature", "label", "contribution"}
    f1 = next(d for d in out[0] if d["feature"] == "f1")
    assert f1["contribution"] != 0.0
