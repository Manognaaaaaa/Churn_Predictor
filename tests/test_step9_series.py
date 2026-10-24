import numpy as np
import pandas as pd

from churn.risk import series as sr


def test_telco_reconstruction_counts_active_months():
    # tenures 1, 3, 12 with charges 10, 20, 30 over a 12-month window ending 2020-06
    s = sr.reconstruct_telco_revenue(np.array([1, 3, 12]), np.array([10.0, 20.0, 30.0]), "2020-06", 12)
    assert len(s) == 12 and s.index.freq is not None
    assert s.index[-1] == pd.Timestamp("2020-06-01")
    assert s.iloc[-1] == 60.0                    # all three alive in the snapshot month
    assert s.iloc[-2] == 50.0 and s.iloc[-3] == 50.0   # tenure-1 customer not yet joined
    assert s.iloc[0] == 30.0                     # only the tenure-12 customer covers month 1
    assert s.is_monotonic_increasing             # survivors only: a ramp by construction


def test_telco_reconstruction_clips_tenure_to_window():
    s = sr.reconstruct_telco_revenue(np.array([100, 0]), np.array([5.0, 7.0]), "2020-06", 6)
    assert (s == 5.0).all()                      # zero-tenure customer never contributes


def test_clean_retail_drops_cancellations_and_nonpositive():
    df = pd.DataFrame({"Invoice": ["1", "C2", "3", "4"], "Quantity": [2, 5, -1, 3],
                       "Price": [1.5, 2.0, 2.0, 0.0],
                       "InvoiceDate": pd.date_range("2010-01-01", periods=4)})
    out = sr.clean_retail(df, "C", 0, 0)
    assert list(out["revenue"]) == [3.0]


def test_aggregate_retail_drops_partial_periods_and_fills_empty_weeks():
    days = pd.date_range("2010-01-06", "2010-03-12", freq="D")        # starts Wed, ends Fri
    sales = pd.DataFrame({"InvoiceDate": days, "revenue": 1.0})
    sales = sales[(sales["InvoiceDate"] < "2010-02-01") | (sales["InvoiceDate"] >= "2010-02-15")]  # 2 empty weeks
    m = sr.aggregate_retail(sales, "MS", days[0], days[-1])
    assert list(m.index) == [pd.Timestamp("2010-02-01")]               # Jan and Mar are partial months
    w = sr.aggregate_retail(sales, "W-SUN", days[0], days[-1])
    assert w.index.freq is not None and w.index.is_monotonic_increasing
    assert w.index[0] == pd.Timestamp("2010-01-17")                    # first full Mon..Sun week
    assert w.index[-1] == pd.Timestamp("2010-03-07")                   # last full week before the Friday end
    assert (w == 0).sum() == 2                                         # empty weeks stay as zeros


def test_describe_series_flags_trend_and_seasonality():
    idx = pd.date_range("2018-01-01", periods=72, freq="MS")
    t = np.arange(72)
    s = pd.Series(100 + 2.0 * t + 10 * np.sin(2 * np.pi * t / 12)
                  + np.random.default_rng(42).normal(0, 1, 72), index=idx)
    d = sr.describe_series(s, 12)
    assert d["n"] == 72 and d["trend"]["p"] < 0.01
    assert d["seasonal_strength"] > 0.5
    assert d["adf_level"]["p"] > d["adf_diff1"]["p"] or d["adf_diff1"]["p"] < 0.05
