"""Phase 9.2: connect the revenue forecast to the churn model without pretending they are one business.

ARIMA forecasts portfolio revenue (a different dataset); the churn model estimates the share of
revenue at risk. Formulas (also in configs/config.yaml and reports/09_timeseries.md):

    L  = sum_i p_i v_i / sum_i v_i                      expected churn loss rate (churn test split)
    L' = L - saved / sum_i v_i                          saved = expected revenue saved by the allocation
    no_intervention = forecast * (1 - L)
    with_allocation = forecast * (1 - L')
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def loss_rate(p: np.ndarray, v: np.ndarray) -> float:
    """Expected churn loss rate: sum p_i v_i / sum v_i."""
    v = np.asarray(v, float)
    return float((np.asarray(p, float) * v).sum() / v.sum())


def reduced_loss_rate(loss: float, saved: float, total_value: float) -> float:
    """L' = L minus the expected saved revenue as a share of total customer value (never below 0)."""
    return float(max(loss - saved / total_value, 0.0))


def scenario_frame(history: pd.Series, base: pd.DataFrame, loss: float, scenario: str,
                   include_history: bool) -> pd.DataFrame:
    """Rows in the forecast.parquet schema: month, actual, forecast, lower, upper, scenario.

    `month` holds the period label (the week-ending Sunday for weekly series). `base` has columns
    date, forecast, lower, upper (no churn adjustment); the scenario scales all three by (1 - loss).
    """
    keep = 1.0 - loss
    fut = pd.DataFrame({"month": base["date"].to_numpy(), "actual": np.nan,
                        "forecast": base["forecast"].to_numpy() * keep,
                        "lower": base["lower"].to_numpy() * keep,
                        "upper": base["upper"].to_numpy() * keep, "scenario": scenario})
    if not include_history:
        return fut
    hist = pd.DataFrame({"month": history.index, "actual": history.to_numpy(), "forecast": np.nan,
                         "lower": np.nan, "upper": np.nan, "scenario": scenario})
    return pd.concat([hist, fut], ignore_index=True)


def scenario_totals(frame: pd.DataFrame) -> dict:
    """Sum of the forecast over the horizon per scenario."""
    f = frame[frame["forecast"].notna()]
    return {k: float(v) for k, v in f.groupby("scenario")["forecast"].sum().items()}
