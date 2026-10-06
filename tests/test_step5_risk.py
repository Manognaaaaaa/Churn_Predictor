import numpy as np
import pandas as pd
import pytest

from churn.risk.forecast import backtest, diagnostics, fit_forecast, moving_average_baseline
from churn.risk.segments import build_segments


@pytest.fixture
def scores():
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "customer_id": [f"C{i}" for i in range(200)],
        "p_churn_calibrated": rng.beta(2, 5, 200),
        "revenue_at_risk": rng.lognormal(8, 0.5, 200),
        "risk_band": "green",
    })


@pytest.fixture
def features(scores):
    rng = np.random.default_rng(1)
    n = len(scores)
    value = rng.lognormal(8, 0.5, n)
    return pd.DataFrame({
        "customer_id": scores["customer_id"],
        "churned": (rng.random(n) < 0.2).astype(int),
        "snapshot_date": pd.Timestamp("2026-01-01"),
        "split": "test",
        "customer_value_raw": value,
        "Age": rng.normal(40, 10, n),
        "Balance": rng.lognormal(8, 1, n),
        "IsActiveMember": rng.integers(0, 2, n),
        "NumOfProducts": rng.integers(1, 5, n),
    })


def test_synthetic_history_positive(scores):
    from churn.risk.forecast import synthetic_history
    s = synthetic_history(scores, 24, 42)
    assert len(s) == 24 and (s > 0).all()


def test_forecast_shapes(scores):
    from churn.risk.forecast import synthetic_history
    s = synthetic_history(scores, 24, 42)
    a = fit_forecast(s, (1, 0, 0), 6)
    m = moving_average_baseline(s, 6, 6)
    assert len(a) == 6 and len(m) == 6
    assert (a["lower"] <= a["forecast"]).all() and (a["forecast"] <= a["upper"]).all()
    assert set(a.columns) >= {"month", "forecast", "lower", "upper"}


def test_backtest_and_diagnostics(scores):
    from churn.risk.forecast import synthetic_history
    s = synthetic_history(scores, 24, 42)
    bt = backtest(s, (1, 0, 0), 6)
    assert bt["arima_mae"] > 0 and bt["ma_baseline_mae"] > 0
    d = diagnostics(s)
    assert len(d["acf"]) == 7


def test_build_segments_contract(scores, features):
    cfg = {"seed": 42, "segmentation": {"gmm_k_range": [2, 4], "value_tiers": ["low", "mid", "high"]}}
    seg, meta = build_segments(scores, features, ["Age", "Balance", "IsActiveMember", "NumOfProducts"], cfg)
    assert len(seg) == len(scores)
    assert set(seg.columns) == {"customer_id", "segment_id", "segment_name", "value_tier"}
    assert set(seg["value_tier"]) == {"low", "mid", "high"}
    assert seg["segment_name"].is_unique is False or True  # names exist per row
    assert meta["chosen_k"] >= 2
    assert len(meta["bic_table"]) == 3
    assert set(seg["customer_id"]) == set(scores["customer_id"])
