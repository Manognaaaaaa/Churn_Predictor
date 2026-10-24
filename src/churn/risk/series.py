"""Real revenue time series: Telco reconstruction (option A) and Online Retail II (option B).

Also the diagnostics used to pick between them: ADF on the level, linear trend, seasonal strength.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller


def reconstruct_telco_revenue(tenure: np.ndarray, charge: np.ndarray, snapshot_month: str,
                              months: int, freq: str = "MS") -> pd.Series:
    """Monthly active revenue for the `months` months ending at `snapshot_month`.

    A customer with tenure t contributes `charge` in each of the last min(t, months) months.
    Only customers alive at the snapshot are in the file (survivorship bias) and the charge is
    the current price, so the early months are under-counted.
    """
    t = np.clip(np.asarray(tenure, int), 0, months)
    c = np.asarray(charge, float)
    by_t = np.bincount(t, weights=c, minlength=months + 1)        # revenue of customers with tenure == t
    # active in month k (1 = oldest ... months = snapshot) iff t >= months - k + 1
    active = np.cumsum(by_t[::-1])[::-1]                           # sum over customers with tenure >= j
    revenue = np.array([active[months - k + 1] for k in range(1, months + 1)])
    idx = pd.period_range(end=snapshot_month, periods=months, freq="M").to_timestamp()
    return pd.Series(revenue, index=pd.DatetimeIndex(idx, freq=freq), name="revenue")


def clean_retail(df: pd.DataFrame, drop_prefix: str, min_qty: float, min_price: float) -> pd.DataFrame:
    """Keep real sales lines: not a cancellation (Invoice starts with prefix), Quantity and Price > min."""
    inv = df["Invoice"].astype(str)
    keep = ~inv.str.startswith(drop_prefix) & (df["Quantity"] > min_qty) & (df["Price"] > min_price)
    out = df.loc[keep, ["InvoiceDate", "Quantity", "Price"]].copy()
    out["revenue"] = out["Quantity"] * out["Price"]
    return out


def aggregate_retail(sales: pd.DataFrame, freq: str, raw_first: pd.Timestamp,
                     raw_last: pd.Timestamp) -> pd.Series:
    """Revenue per period, dropping incomplete first/last periods; empty periods inside are 0.

    freq: "MS" (month start) or "W-SUN" (weeks ending Sunday). A period is complete only if the
    raw data covers it entirely (`raw_first` .. `raw_last` are the first/last invoice timestamps).
    """
    s = sales.set_index("InvoiceDate")["revenue"].resample(freq).sum()
    if freq == "MS":
        start = s.index[0] if raw_first.day == 1 else s.index[0] + pd.offsets.MonthBegin(1)
        end_month = raw_last.to_period("M").to_timestamp()
        last_day = (end_month + pd.offsets.MonthEnd(0)).normalize()
        end = end_month if raw_last.normalize() >= last_day else end_month - pd.offsets.MonthBegin(1)
        s = s.loc[start:end]
    else:
        first_week_end = raw_first.normalize() + pd.offsets.Week(weekday=6)        # first Sunday
        if raw_first.normalize().weekday() != 0:                                   # not a full Mon..Sun week
            s = s.loc[first_week_end + pd.Timedelta(days=7):]
        if raw_last.normalize().weekday() != 6:
            s = s.iloc[:-1]
    s.name = "revenue"
    return s.asfreq(freq, fill_value=0.0)


def describe_series(s: pd.Series, period: int, adf_regression: str = "c",
                    decomposition: str = "additive") -> dict:
    """Points, ADF (level and first difference), linear trend, seasonal strength."""
    out = {"n": int(len(s)), "start": str(s.index[0].date()), "end": str(s.index[-1].date())}
    for name, x in (("level", s), ("diff1", s.diff().dropna())):
        stat, p, lags, nobs, crit, _ = adfuller(x.to_numpy(), regression=adf_regression, autolag="AIC")
        out[f"adf_{name}"] = {"stat": float(stat), "p": float(p), "lags": int(lags),
                              "crit_5pct": float(crit["5%"])}
    t = np.arange(len(s))
    lr = stats.linregress(t, s.to_numpy())
    out["trend"] = {"slope_per_step": float(lr.slope), "p": float(lr.pvalue), "r2": float(lr.rvalue ** 2),
                    "relative_change": float(lr.slope * (len(s) - 1) / max(abs(s.iloc[0]), 1e-9))}
    out["seasonal_period"] = period
    if len(s) >= 2 * period:
        dec = seasonal_decompose(s, model=decomposition, period=period)
        resid, seas, trend = dec.resid.dropna(), dec.seasonal, dec.trend.dropna()
        out["seasonal_strength"] = float(max(0.0, 1 - resid.var() / (resid + seas.loc[resid.index]).var()))
        out["trend_strength"] = float(max(0.0, 1 - resid.var() / (resid + trend.loc[resid.index]).var()))
    else:
        out["seasonal_strength"] = None
        out["trend_strength"] = None
    return out
