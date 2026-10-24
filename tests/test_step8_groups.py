import numpy as np
import pandas as pd
import pytest

from churn.allocate.groups import (build_group_table, customer_params, global_params,
                                   segment_engagement)
from churn.config import load_config


def _inputs():
    rng = np.random.default_rng(0)
    n = 600
    seg = pd.DataFrame({"customer_id": np.arange(n).astype(str),
                        "segment_id": rng.integers(0, 3, n),
                        "value_tier": rng.choice(["low", "mid", "high"], n)})
    feats = pd.DataFrame({"customer_id": np.arange(n), "split": "train",
                          "IsActiveMember": rng.normal(size=n) + seg["segment_id"] * 0.5,
                          "NumOfProducts": rng.normal(size=n) + seg["segment_id"] * 0.5})
    return seg, feats


def test_engagement_orders_segments():
    prof = pd.DataFrame({"IsActiveMember": [0.4, 0.5, 0.6], "NumOfProducts": [1.2, 1.5, 1.8]})
    e = segment_engagement(prof)
    assert e.is_monotonic_increasing and e.iloc[1] == pytest.approx(0.0)


def test_group_table_follows_rule():
    cfg = load_config()
    seg, feats = _inputs()
    t = build_group_table(seg, feats, cfg).set_index(["segment_id", "value_tier"])
    rc = cfg["allocation"]["response_curves"]
    assert len(t) == 9
    # more engaged segment -> larger a; higher tier -> larger t; a independent of tier
    assert t.loc[(2, "mid"), "a_g"] > t.loc[(0, "mid"), "a_g"]
    assert t.loc[(1, "high"), "t_g"] > t.loc[(1, "mid"), "t_g"] > t.loc[(1, "low"), "t_g"]
    assert t.loc[(1, "high"), "a_g"] == pytest.approx(t.loc[(1, "low"), "a_g"])
    assert t.loc[(1, "mid"), "t_g"] == pytest.approx(rc["t"])
    assert t.loc[(1, "high"), "t_g"] / t.loc[(1, "mid"), "t_g"] == pytest.approx(rc["t_tier_step"])


def test_profiles_use_train_split_only():
    cfg = load_config()
    seg, feats = _inputs()
    base = build_group_table(seg, feats, cfg)
    poisoned = feats.copy()
    poisoned.loc[:99, "split"] = "test"
    poisoned.loc[:99, "IsActiveMember"] = 1e6      # would distort profiles if test rows were used
    out = build_group_table(seg, poisoned, cfg)
    assert out.shape == base.shape
    assert out["m_seg"].between(*cfg["allocation"]["response_curves"]["a_segment_bounds"]).all()
    assert np.allclose(out["engagement"].abs().max(), out["engagement"].abs().max())
    assert out["engagement"].abs().max() < 2.0     # no 1e6 outlier leaked into the profile


def test_customer_and_global_params():
    cfg = load_config()
    seg, feats = _inputs()
    table = build_group_table(seg, feats, cfg)
    v = np.full(len(seg), 1000.0)
    a, tau = customer_params(seg["segment_id"].to_numpy(), seg["value_tier"].to_numpy(), table, v)
    assert a.shape == tau.shape == v.shape and not np.isnan(a).any()
    ga, gtau = global_params(len(v), v, cfg)
    assert (ga == cfg["allocation"]["response_curves"]["a"]).all()
    assert np.allclose(gtau, cfg["allocation"]["response_curves"]["t"] * 1000.0)
