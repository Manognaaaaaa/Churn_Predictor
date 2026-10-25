"""Step 9: ARIMA on a real revenue series, compared with naive, moving-average and seasonal-naive.

Everything that is chosen (differencing order d, ARIMA order, moving-average window) is chosen on
the training part only; the holdout is used once for the comparison. A rolling-origin backtest
repeats the whole procedure at several origins so the verdict does not rest on one split.
"""
from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf, adfuller, pacf

from churn.config import ROOT
from churn.risk import series as sr


# ------------------------------------------------------------------ data
def load_revenue_series(cfg: dict) -> pd.Series:
    """Revenue series with a DatetimeIndex of fixed frequency and no gaps, per `forecast.source`."""
    fc = cfg["forecast"]
    src = fc["sources"][fc["source"]]
    if fc["source"] == "online_retail":
        raw = sr.load_retail_raw(src)
        sales = sr.clean_retail(raw, src["drop_invoice_prefix"], src["min_quantity"], src["min_price"])
        s = sr.aggregate_retail(sales, fc["freq"], raw["InvoiceDate"].min(), raw["InvoiceDate"].max())
    elif fc["source"] == "telco_reconstruction":
        tel = pd.read_excel(ROOT / src["path"])
        s = sr.reconstruct_telco_revenue(tel[src["tenure_col"]].to_numpy(), tel[src["charge_col"]].to_numpy(),
                                         src["snapshot_month"], src["months"], src["freq"])
    else:
        raise ValueError(f"unknown forecast.source {fc['source']!r}")
    if s.index.freq is None or s.isna().any():
        raise ValueError("series must have a fixed frequency and no gaps")
    return s


def split_holdout(series: pd.Series, h: int) -> tuple[pd.Series, pd.Series]:
    """(train, holdout): the last h points are the holdout."""
    return series.iloc[:-h], series.iloc[-h:]


def demo_ar1_series(n: int, phi: float, seed: int, sigma: float = 1.0, level: float = 0.0) -> pd.Series:
    """Seeded AR(1) toy series for tests only (the pipeline never calls this)."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0.0, sigma)
    return pd.Series(x + level, index=pd.date_range("2000-01-02", periods=n, freq="W-SUN"))


# ------------------------------------------------------------------ stationarity, ACF/PACF
def adf_report(x: pd.Series, regression: str = "c") -> dict:
    """ADF test (lag length by AIC): statistic, p-value, lags used, 5% critical value."""
    stat, p, lags, _, crit, _ = adfuller(np.asarray(x, float), regression=regression, autolag="AIC",
                                         result_object=False)
    return {"stat": float(stat), "p": float(p), "lags": int(lags), "crit_5pct": float(crit["5%"])}


def choose_d(train: pd.Series, adf_cfg: dict) -> dict:
    """Smallest d in 0..max_d whose differenced training series rejects a unit root (p < alpha)."""
    tests = []
    chosen = adf_cfg["max_d"]
    for d in range(adf_cfg["max_d"] + 1):
        x = train.diff(d).dropna() if d else train
        t = {"d": d, **adf_report(x, adf_cfg["regression"])}
        tests.append(t)
        if t["p"] < adf_cfg["alpha"]:
            chosen = d
            break
    return {"d": chosen, "tests": tests}


def acf_pacf_values(x: pd.Series, nlags: int) -> dict:
    """ACF/PACF values with the approximate 95% band 1.96 / sqrt(n)."""
    n = len(x)
    nlags = min(nlags, n // 2 - 1)
    return {"acf": acf(x, nlags=nlags, fft=True), "pacf": pacf(x, nlags=nlags), "band": 1.96 / np.sqrt(n),
            "n": n}


def _contiguous_cutoff(vals: np.ndarray, band: float, max_lag: int) -> int:
    """Number of consecutive significant lags starting at lag 1."""
    k = 0
    for lag in range(1, min(max_lag, len(vals) - 1) + 1):
        if abs(vals[lag]) > band:
            k = lag
        else:
            break
    return k


def suggest_pq(values: dict, max_p: int, max_q: int) -> dict:
    """Reading of ACF/PACF: PACF cutoff suggests p, ACF cutoff suggests q (consecutive significant lags).

    Also returns every significant lag, because a tail that dies out slowly (rather than cutting
    off) indicates a mixed ARMA process and the cutoff rule is then only a starting point.
    """
    band = values["band"]
    sig = lambda v: [int(l) for l in range(1, len(v)) if abs(v[l]) > band]
    return {"p_hat": _contiguous_cutoff(values["pacf"], band, max_p),
            "q_hat": _contiguous_cutoff(values["acf"], band, max_q),
            "significant_acf_lags": sig(values["acf"]), "significant_pacf_lags": sig(values["pacf"]),
            "band": band}


def plot_acf_pacf(x: pd.Series, nlags: int, path, title: str) -> None:
    """ACF and PACF side by side, saved to `path`."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    nlags = min(nlags, len(x) // 2 - 1)
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    plot_acf(x, lags=nlags, ax=axs[0], title=f"ACF: {title}")
    plot_pacf(x, lags=nlags, ax=axs[1], title=f"PACF: {title}", method="ywm")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------ ARIMA fitting and selection
def seasonal_justified(n_train: int, period: int, min_cycles: int) -> bool:
    """Seasonal ARIMA terms only if the training part holds at least `min_cycles` full cycles."""
    return n_train >= min_cycles * period


def _trend(d: int, D: int = 0) -> str:
    return "c" if d == 0 and D == 0 else "n"


def fit_arima(train: pd.Series, order: tuple[int, int, int],
              seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0)):
    """Fit ARIMA(order) (with a constant only when undifferenced)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ARIMA(train, order=order, seasonal_order=seasonal_order,
                     trend=_trend(order[1], seasonal_order[1])).fit()


def select_order(train: pd.Series, d: int, p_range: tuple[int, int], q_range: tuple[int, int],
                 seasonal: dict | None = None) -> dict:
    """AIC grid over (p, q) at fixed d (plus seasonal (P, Q) with D if `seasonal` is given).

    Uses only `train`. Returns the AIC table (sorted) and the winner.
    """
    seas_grid = [(0, 0, 0, 0)]
    if seasonal:
        seas_grid = [(P, seasonal["D"], Q, seasonal["period"])
                     for P in range(seasonal["P"][0], seasonal["P"][1] + 1)
                     for Q in range(seasonal["Q"][0], seasonal["Q"][1] + 1)]
    rows = []
    for p, q in itertools.product(range(p_range[0], p_range[1] + 1), range(q_range[0], q_range[1] + 1)):
        for so in seas_grid:
            try:
                res = fit_arima(train, (p, d, q), so)
            except Exception:                                # non-convergent / invalid orders are skipped
                continue
            if np.isfinite(res.aic):
                rows.append({"p": p, "d": d, "q": q, "seasonal": so if seasonal else None,
                             "aic": float(res.aic), "bic": float(res.bic)})
    table = pd.DataFrame(rows).sort_values("aic").reset_index(drop=True)
    best = table.iloc[0]
    return {"table": table, "order": (int(best.p), d, int(best.q)),
            "seasonal_order": tuple(best.seasonal) if seasonal else (0, 0, 0, 0)}


def ljung_box(resid: np.ndarray, lags: list[int], model_df: int) -> list[dict]:
    """Ljung-Box test on residuals at the given lags (degrees of freedom reduced by p + q)."""
    resid = np.asarray(resid, float)
    out = []
    for lag in lags:
        lb = acorr_ljungbox(resid, lags=[lag], model_df=min(model_df, lag - 1), return_df=True)
        out.append({"lag": int(lag), "stat": float(lb["lb_stat"].iloc[0]),
                    "p": float(lb["lb_pvalue"].iloc[0])})
    return out


def fit_pipeline(train: pd.Series, cfg: dict) -> dict:
    """d from ADF, order from the AIC grid, all on `train`. Returns the fitted model and the evidence."""
    fc = cfg["forecast"]
    dsel = choose_d(train, fc["adf"])
    seasonal = None
    if seasonal_justified(len(train), fc["seasonal_period"], fc["seasonal_grid"]["min_cycles"]):
        sg = fc["seasonal_grid"]
        seasonal = {"P": sg["P"], "Q": sg["Q"], "D": sg["D"], "period": fc["seasonal_period"]}
    sel = select_order(train, dsel["d"], tuple(fc["order_grid"]["p"]), tuple(fc["order_grid"]["q"]), seasonal)
    model = fit_arima(train, sel["order"], sel["seasonal_order"])
    return {"d_selection": dsel, "selection": sel, "model": model, "order": sel["order"],
            "seasonal_order": sel["seasonal_order"], "seasonal_used": seasonal is not None}


# ------------------------------------------------------------------ baselines
def naive_forecast(train: pd.Series, h: int) -> np.ndarray:
    """Last observed value repeated."""
    return np.repeat(float(train.iloc[-1]), h)


def moving_average_forecast(train: pd.Series, window: int, h: int) -> np.ndarray:
    """Mean of the last `window` values repeated."""
    return np.repeat(float(train.iloc[-window:].mean()), h)


def seasonal_naive_forecast(train: pd.Series, period: int, h: int) -> np.ndarray:
    """Value one season earlier (cycles through the last `period` values)."""
    last = train.iloc[-period:].to_numpy(float)
    return np.array([last[i % period] for i in range(h)])


def select_ma_window(train: pd.Series, windows: list[int], h: int, n_origins: int) -> dict:
    """Pick the moving-average window with the lowest h-step MAE over origins *inside* train."""
    y = train.to_numpy(float)
    last_origin = len(y) - h
    origins = [t for t in range(last_origin - n_origins + 1, last_origin + 1) if t >= max(windows)]
    scores = {}
    for w in windows:
        errs = [np.abs(y[t:t + h] - y[t - w:t].mean()).mean() for t in origins]
        scores[w] = float(np.mean(errs))
    return {"window": min(scores, key=scores.get), "scores": scores, "origins": len(origins)}


def mae(y: np.ndarray, f: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(f, float))))


def mape(y: np.ndarray, f: np.ndarray) -> float:
    """MAPE in percent over the points whose actual value is non-zero."""
    y, f = np.asarray(y, float), np.asarray(f, float)
    m = y != 0
    return float(np.mean(np.abs(y[m] - f[m]) / np.abs(y[m])) * 100) if m.any() else float("nan")


# ------------------------------------------------------------------ evaluation
def run_methods(train: pd.Series, test: pd.Series, cfg: dict) -> dict:
    """Fit ARIMA and the baselines on `train` only and forecast len(test) steps."""
    fc, h = cfg["forecast"], len(test)
    fit = fit_pipeline(train, cfg)
    ma = select_ma_window(train, fc["ma_windows"], h, fc["ma_select_origins"])
    preds = {"arima": np.asarray(fit["model"].forecast(h), float),
             "naive": naive_forecast(train, h),
             "moving_average": moving_average_forecast(train, ma["window"], h)}
    if len(train) >= fc["seasonal_period"]:
        preds["seasonal_naive"] = seasonal_naive_forecast(train, fc["seasonal_period"], h)
    y = test.to_numpy(float)
    metrics = {k: {"mae": mae(y, f), "mape": mape(y, f), "one_step_abs_error": float(abs(y[0] - f[0]))}
               for k, f in preds.items()}
    return {"fit": fit, "ma": ma, "predictions": preds, "metrics": metrics}


def evaluate_holdout(series: pd.Series, cfg: dict) -> dict:
    """Train on everything but the last h points, forecast them, compare all methods once."""
    train, test = split_holdout(series, cfg["forecast"]["holdout"])
    out = run_methods(train, test, cfg)
    out.update({"train": train, "test": test})
    return out


def rolling_origin(series: pd.Series, cfg: dict) -> dict:
    """Expanding-window backtest: refit everything at each origin, record one-step and h-step errors."""
    fc = cfg["forecast"]
    h, n_orig, step = fc["holdout"], fc["rolling"]["origins"], fc["rolling"]["step"]
    n = len(series)
    ends = [n - h - k * step for k in range(n_orig)][::-1]              # earliest origin first
    rows = []
    for end in ends:
        train, test = series.iloc[:end], series.iloc[end:end + h]
        res = run_methods(train, test, cfg)
        for method, m in res["metrics"].items():
            rows.append({"origin": str(train.index[-1].date()), "train_len": int(end), "method": method,
                         "order": list(res["fit"]["order"]) if method == "arima" else None,
                         "ma_window": res["ma"]["window"] if method == "moving_average" else None, **m})
    df = pd.DataFrame(rows)
    summary = (df.groupby("method")[["mae", "mape", "one_step_abs_error"]].mean()
               .rename(columns={"one_step_abs_error": "one_step_mae"}))
    wins = (df.pivot(index="origin", columns="method", values="mae").idxmin(axis=1)
              .value_counts().to_dict())
    return {"per_origin": df, "summary": summary, "n_origins": len(ends), "wins_by_mae": wins}


def final_forecast(series: pd.Series, cfg: dict) -> dict:
    """Refit the whole procedure on the full series and forecast `horizon` steps with a CI."""
    fc = cfg["forecast"]
    fit = fit_pipeline(series, cfg)
    pred = fit["model"].get_forecast(fc["horizon"])
    ci = pred.conf_int(alpha=1 - fc["ci_level"])
    idx = pd.date_range(series.index[-1] + series.index.freq, periods=fc["horizon"], freq=series.index.freq)
    frame = pd.DataFrame({"date": idx, "forecast": np.asarray(pred.predicted_mean, float),
                          "lower": np.maximum(ci.iloc[:, 0].to_numpy(float), 0.0),
                          "upper": ci.iloc[:, 1].to_numpy(float)})
    return {"frame": frame, "fit": fit}


# ------------------------------------------------------------------ one study, JSON-friendly
def plot_residual_acf(resid: np.ndarray, nlags: int, path) -> None:
    """ACF of the model residuals with the 95% band."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from statsmodels.graphics.tsaplots import plot_acf
    fig, ax = plt.subplots(figsize=(6, 3.5))
    plot_acf(np.asarray(resid, float), lags=min(nlags, len(resid) // 2 - 1), ax=ax, title="Residual ACF")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run_study(cfg: dict, make_figures: bool = True) -> dict:
    """Series, ADF, ACF/PACF, AIC grid, residual checks, holdout, rolling origin and the final forecast."""
    fc = cfg["forecast"]
    series = load_revenue_series(cfg)
    ev = evaluate_holdout(series, cfg)
    train, test, fit = ev["train"], ev["test"], ev["fit"]
    d = fit["d_selection"]["d"]
    xd = train.diff(d).dropna() if d else train
    vals = acf_pacf_values(xd, fc["acf_lags"])
    sugg = suggest_pq(vals, fc["order_grid"]["p"][1], fc["order_grid"]["q"][1])
    p_, _, q_ = fit["order"]
    resid = np.asarray(fit["model"].resid, float)[d:]
    lb = ljung_box(resid, fc["ljung_box_lags"], p_ + q_)
    if make_figures:
        plot_acf_pacf(xd, fc["acf_lags"], ROOT / fc["figures"]["acf_pacf"],
                      f"training series, d = {d}")
        plot_residual_acf(resid, fc["acf_lags"], ROOT / fc["figures"]["residual_acf"])
    roll = rolling_origin(series, cfg)
    final = final_forecast(series, cfg)
    table = fit["selection"]["table"]
    return {
        "series": series, "train": train, "test": test, "final_frame": final["frame"],
        "summary": {
            "source": fc["source"], "freq": fc["freq"], "n": int(len(series)), "n_train": int(len(train)),
            "holdout": int(len(test)), "start": str(series.index[0].date()), "end": str(series.index[-1].date()),
            "d_selection": fit["d_selection"],
            "acf_pacf": {"p_hat": sugg["p_hat"], "q_hat": sugg["q_hat"], "band": sugg["band"],
                         "significant_acf_lags": sugg["significant_acf_lags"],
                         "significant_pacf_lags": sugg["significant_pacf_lags"], "n": vals["n"]},
            "aic_table": table.drop(columns=["seasonal"]).head(16).to_dict("records"),
            "order": list(fit["order"]), "seasonal_used": fit["seasonal_used"],
            "aic_agrees_with_acf_pacf": bool(sugg["p_hat"] == p_ and sugg["q_hat"] == q_),
            "ljung_box": lb,
            "ma_window": fit["selection"] and ev["ma"]["window"], "ma_window_scores": ev["ma"]["scores"],
            "holdout_metrics": ev["metrics"],
            "holdout_predictions": {k: [float(x) for x in v] for k, v in ev["predictions"].items()},
            "holdout_actual": [float(x) for x in test.to_numpy()],
            "holdout_dates": [str(x.date()) for x in test.index],
            "rolling": {"n_origins": roll["n_origins"], "summary": roll["summary"].round(4).to_dict("index"),
                        "wins_by_mae": roll["wins_by_mae"],
                        "per_origin": roll["per_origin"].to_dict("records")},
            "final_order": list(final["fit"]["order"]),
            "final_d_selection": final["fit"]["d_selection"],
            "seasonal_justified": seasonal_justified(len(train), fc["seasonal_period"],
                                                     fc["seasonal_grid"]["min_cycles"]),
            "final_forecast": [{"date": str(r.date.date()), "forecast": float(r.forecast),
                                "lower": float(r.lower), "upper": float(r.upper)}
                               for r in final["frame"].itertuples()],
        },
    }
