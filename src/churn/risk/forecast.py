"""Step 5: portfolio revenue forecast — ARIMA vs moving-average baseline.

The source dataset has no timestamps, so this module forecasts the aggregate
monthly revenue-at-risk trajectory built from the empirical portfolio
distribution (bootstrap resampling with AR(1) dynamics around the observed
total). Clearly labelled synthetic history; swap in real monthly aggregates
when a temporal dataset is available.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf, pacf


def synthetic_history(scores: pd.DataFrame, months: int, seed: int,
                      churn_prob_col: str = "p_churn_calibrated",
                      value_col: str = "revenue_at_risk") -> pd.Series:
    """Monthly revenue-at-risk totals sampled from the portfolio distribution."""
    rng = np.random.default_rng(seed)
    p = scores[churn_prob_col].to_numpy(float)
    v = scores[value_col].to_numpy(float)
    share = rng.uniform(0.55, 0.75)                       # share of book reviewed monthly
    idx = rng.choice(len(scores), size=int(len(scores) * share), replace=False)
    base = float((p[idx] * v[idx]).sum())                  # observed steady-state level
    noise_std = base * 0.03
    eps = rng.normal(0, noise_std, months)
    x = np.zeros(months)
    x[0] = base
    for t in range(1, months):                             # AR(1) around the level
        x[t] = base * 0.97 + 0.03 * base + 0.6 * (x[t - 1] - base) + eps[t] * 0.5
    idxm = pd.period_range("2024-07", periods=months, freq="M").to_timestamp()
    return pd.Series(np.maximum(x, 0.0), index=idxm, name="revenue_at_risk")


def diagnostics(series: pd.Series) -> dict:
    a = acf(series, nlags=6, fft=True)
    p = pacf(series, nlags=6)
    return {"acf": [round(float(v), 3) for v in a], "pacf": [round(float(v), 3) for v in p]}


def fit_forecast(series: pd.Series, order: tuple[int, int, int], horizon: int) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(series, order=order).fit()
    fc = model.get_forecast(horizon)
    return pd.DataFrame({
        "month": fc.predicted_mean.index,
        "forecast": fc.predicted_mean.to_numpy(),
        "lower": fc.conf_int().iloc[:, 0].to_numpy(),
        "upper": fc.conf_int().iloc[:, 1].to_numpy(),
    })


def moving_average_baseline(series: pd.Series, window: int, horizon: int) -> pd.DataFrame:
    ma = series.rolling(window).mean().iloc[-1]
    idx = pd.period_range(series.index[-1] + pd.offsets.MonthBegin(1),
                          periods=horizon, freq="M").to_timestamp()
    resid = (series - series.rolling(window).mean()).dropna().std()
    return pd.DataFrame({
        "month": idx,
        "forecast": np.repeat(ma, horizon),
        "lower": np.repeat(ma - 1.96 * resid, horizon),
        "upper": np.repeat(ma + 1.96 * resid, horizon),
    })


def backtest(series: pd.Series, order, window: int, holdout: int = 6) -> dict:
    """MAE of both methods on the last `holdout` months."""
    train, test = series.iloc[:-holdout], series.iloc[-holdout:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        arima_pred = ARIMA(train, order=order).fit().forecast(holdout)
    ma_pred = np.repeat(train.rolling(window).mean().iloc[-1], holdout)
    return {
        "arima_mae": float(np.abs(arima_pred - test).mean()),
        "ma_baseline_mae": float(np.abs(ma_pred - test).mean()),
    }
