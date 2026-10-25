import copy

import numpy as np
import pandas as pd
import pytest

from churn.config import ROOT, load_config
from churn.risk import forecast as fc
from churn.risk import scenarios as sc

BASE = load_config()


def _cfg(**overrides) -> dict:
    """Small, fast copy of the config (weekly toy series, short grid)."""
    cfg = copy.deepcopy(BASE)
    f = cfg["forecast"]
    f.update({"holdout": 8, "horizon": 6, "freq": "W-SUN", "seasonal_period": 52,
              "ma_windows": [2, 4, 8], "ma_select_origins": 6, "rolling": {"origins": 3, "step": 3},
              "order_grid": {"p": [0, 2], "q": [0, 2]}})
    f.update(overrides)
    return cfg


def _series(n=90, seed=0, level=100.0) -> pd.Series:
    return fc.demo_ar1_series(n, 0.6, seed, sigma=5.0, level=level)


# ------------------------------------------------------------------ no leakage
def test_no_holdout_point_is_used_for_selection_or_forecast():
    cfg = _cfg()
    s = _series()
    poisoned = s.copy()
    poisoned.iloc[-cfg["forecast"]["holdout"]:] = 1e9            # absurd holdout values
    a, b = fc.evaluate_holdout(s, cfg), fc.evaluate_holdout(poisoned, cfg)
    assert a["fit"]["d_selection"] == b["fit"]["d_selection"]
    assert a["fit"]["order"] == b["fit"]["order"]
    pd.testing.assert_frame_equal(a["fit"]["selection"]["table"], b["fit"]["selection"]["table"])
    assert a["ma"] == b["ma"]                                    # window scored inside train only
    for k in a["predictions"]:
        assert np.allclose(a["predictions"][k], b["predictions"][k])   # forecasts never saw the holdout
    assert a["metrics"]["arima"]["mae"] != b["metrics"]["arima"]["mae"]  # but the scores do use it


def test_ma_window_selection_only_scores_origins_inside_train():
    y = pd.Series(np.arange(60, dtype=float))
    out = fc.select_ma_window(y, [2, 4], h=4, n_origins=5)
    assert out["origins"] == 5
    assert out["window"] == 2                                     # a ramp: shorter window is closer


def test_rolling_origins_only_train_on_the_past():
    cfg = _cfg()
    s = _series(100)
    r = fc.rolling_origin(s, cfg)
    df = r["per_origin"]
    assert r["n_origins"] == cfg["forecast"]["rolling"]["origins"]
    origins = sorted(df["train_len"].unique())
    assert origins == sorted(set(origins))
    assert origins[-1] == len(s) - cfg["forecast"]["holdout"]    # last origin = start of the holdout
    assert set(df["method"]) >= {"arima", "naive", "moving_average"}


# ------------------------------------------------------------------ forecast shape
def test_final_forecast_length_and_interval_shape():
    cfg = _cfg()
    s = _series()
    out = fc.final_forecast(s, cfg)["frame"]
    h = cfg["forecast"]["horizon"]
    assert len(out) == h
    assert (out["lower"] <= out["forecast"]).all() and (out["forecast"] <= out["upper"]).all()
    assert out["date"].iloc[0] == s.index[-1] + s.index.freq
    assert out["date"].is_monotonic_increasing


def test_interval_widens_with_horizon_for_undifferenced_ar():
    cfg = _cfg()
    out = fc.final_forecast(_series(), cfg)["frame"]
    w = (out["upper"] - out["lower"]).to_numpy()
    assert w[-1] >= w[0]


# ------------------------------------------------------------------ order selection
def test_aic_recovers_ar1_on_known_series():
    """AIC on seeded AR(1) data (phi = 0.7): d = 0 always, and p = 1 is the modal choice.

    AIC is known to over-fit: with a pure-AR grid it picks p = 1 in about 60% of seeds (18 of 30
    measured when this test was written), p = 2 or 3 otherwise, and with a free q it picks (1, 0, 0)
    in only 12 of 30. So the claim tested is the realistic one: d is always 0 and p = 1 is the most
    frequent and a majority choice, not that AIC is exact on every sample.
    """
    seeds = range(20)
    picks = []
    for seed in seeds:
        s = fc.demo_ar1_series(300, 0.7, seed)
        dsel = fc.choose_d(s, BASE["forecast"]["adf"])
        assert dsel["d"] == 0
        picks.append(fc.select_order(s, dsel["d"], (0, 3), (0, 0))["order"])
    p_values = [o[0] for o in picks]
    assert p_values.count(1) == max(p_values.count(k) for k in (1, 2, 3))
    assert p_values.count(1) / len(p_values) >= 0.5
    assert all(o[0] >= 1 for o in picks)          # never misses the AR term


def test_adf_picks_d1_for_random_walk():
    rng = np.random.default_rng(1)
    s = pd.Series(np.cumsum(rng.normal(size=300)), index=pd.date_range("2000-01-02", periods=300, freq="W-SUN"))
    assert fc.choose_d(s, BASE["forecast"]["adf"])["d"] == 1


def test_seasonal_terms_need_enough_cycles():
    assert not fc.seasonal_justified(104, 52, 3)
    assert fc.seasonal_justified(156, 52, 3)


def test_suggest_pq_reads_ar1_signature():
    s = fc.demo_ar1_series(500, 0.7, 7)
    vals = fc.acf_pacf_values(s, 20)
    out = fc.suggest_pq(vals, 3, 3)
    assert out["p_hat"] == 1 and 1 in out["significant_acf_lags"]


def test_ljung_box_accepts_white_noise():
    lb = fc.ljung_box(np.random.default_rng(0).normal(size=300), [8, 16], model_df=2)
    assert all(r["p"] > 0.05 for r in lb)


# ------------------------------------------------------------------ baselines and metrics
def test_baselines_and_metrics():
    y = pd.Series(np.arange(1.0, 105.0))
    assert list(fc.naive_forecast(y, 3)) == [104.0] * 3
    assert list(fc.moving_average_forecast(y, 4, 2)) == [102.5, 102.5]
    sn = fc.seasonal_naive_forecast(y, 52, 3)
    assert list(sn) == [53.0, 54.0, 55.0]                         # values one season earlier
    assert fc.mae([1, 2, 3], [2, 2, 5]) == pytest.approx(1.0)
    assert fc.mape([0, 2, 4], [1, 1, 2]) == pytest.approx(50.0)  # the zero actual is excluded


# ------------------------------------------------------------------ loader
def test_loader_returns_fixed_frequency_series_without_gaps(tmp_path):
    days = pd.date_range("2010-01-04", "2010-07-30", freq="D")           # Mon .. Fri
    raw = pd.DataFrame({"Invoice": [f"{i}" for i in range(len(days))], "Quantity": 2, "Price": 1.5,
                        "InvoiceDate": days})
    raw = raw[(raw["InvoiceDate"] < "2010-03-01") | (raw["InvoiceDate"] >= "2010-03-15")]   # 2 empty weeks
    cache = tmp_path / "retail.parquet"
    raw.to_parquet(cache, index=False)
    cfg = copy.deepcopy(BASE)
    cfg["forecast"]["source"] = "online_retail"
    cfg["forecast"]["sources"]["online_retail"]["cache"] = str(cache)
    s = fc.load_revenue_series(cfg)
    assert isinstance(s.index, pd.DatetimeIndex) and s.index.freq is not None
    assert not s.isna().any()
    assert (s.index.to_series().diff().dropna() == pd.Timedelta(days=7)).all()       # no gaps
    assert (s == 0).sum() == 2
    assert s.index[-1] <= pd.Timestamp("2010-07-25")                                 # partial last week dropped


@pytest.mark.skipif(not (ROOT / BASE["forecast"]["sources"]["telco_reconstruction"]["path"]).exists(),
                    reason="raw Telco workbook is not in the repo (gitignored); runs locally only")
def test_loader_telco_source_is_monthly_and_gap_free():
    cfg = copy.deepcopy(BASE)
    cfg["forecast"]["source"] = "telco_reconstruction"
    s = fc.load_revenue_series(cfg)
    assert len(s) == cfg["forecast"]["sources"]["telco_reconstruction"]["months"]
    assert s.index.freq is not None


# ------------------------------------------------------------------ scenarios
def test_with_allocation_never_below_no_intervention():
    base = pd.DataFrame({"date": pd.date_range("2012-01-01", periods=6, freq="W-SUN"),
                         "forecast": np.linspace(200, 150, 6), "lower": np.linspace(100, 50, 6),
                         "upper": np.linspace(300, 250, 6)})
    p, v = np.array([0.5, 0.2, 0.1]), np.array([100.0, 200.0, 50.0])
    loss = sc.loss_rate(p, v)
    assert loss == pytest.approx((50 + 40 + 5) / 350)
    loss2 = sc.reduced_loss_rate(loss, saved=10.0, total_value=v.sum())
    assert loss2 < loss
    hist = pd.Series([1.0, 2.0], index=pd.date_range("2011-12-18", periods=2, freq="W-SUN"))
    no = sc.scenario_frame(hist, base, loss, "no_intervention", True)
    wa = sc.scenario_frame(hist, base, loss2, "with_allocation", False)
    f_no = no[no["forecast"].notna()].reset_index(drop=True)
    assert (wa["forecast"].to_numpy() >= f_no["forecast"].to_numpy()).all()
    assert (wa["lower"].to_numpy() >= f_no["lower"].to_numpy()).all()
    assert list(no.columns) == ["month", "actual", "forecast", "lower", "upper", "scenario"]
    assert (wa["lower"] <= wa["forecast"]).all() and (wa["forecast"] <= wa["upper"]).all()


def test_reduced_loss_rate_is_floored_at_zero():
    assert sc.reduced_loss_rate(0.05, saved=1e9, total_value=1.0) == 0.0
