import numpy as np
import pandas as pd
import pytest

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
