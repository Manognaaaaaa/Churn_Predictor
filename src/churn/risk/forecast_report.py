"""Writes reports/09_timeseries.md and the scenario figure from forecast artifacts."""
from __future__ import annotations

import json

import pandas as pd

from churn.config import ROOT
from churn.risk import scenarios as sc


def _read(path):
    return json.loads(path.read_text()) if path.exists() else None


def plot_scenarios(cfg: dict) -> None:
    """History, unadjusted ARIMA forecast with CI, and the two churn-adjusted scenarios."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    art = ROOT / cfg["paths"]["artifacts"]
    f = pd.read_parquet(art / "forecast.parquet")
    base = pd.read_parquet(art / "forecast_base.parquet")
    hist = f[f["scenario"] == "no_intervention"].dropna(subset=["actual"])
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(hist["month"], hist["actual"], color="black", lw=1, label="actual weekly revenue")
    ax.plot(base["date"], base["forecast"], color="grey", ls=":", label="ARIMA (before churn adjustment)")
    for name, color in (("no_intervention", "tab:red"), ("with_allocation", "tab:green")):
        g = f[(f["scenario"] == name) & f["forecast"].notna()]
        if g.empty:
            continue
        ax.plot(g["month"], g["forecast"], color=color, label=name)
        ax.fill_between(g["month"], g["lower"], g["upper"], color=color, alpha=0.12)
    ax.set_ylabel(f"revenue ({cfg['forecast']['currency']})")
    ax.set_title("Weekly revenue forecast (95% CI) with churn-adjusted scenarios", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / cfg["forecast"]["figures"]["scenarios"], dpi=130)
    plt.close(fig)


def write_forecast_report(cfg: dict) -> None:
    fc = cfg["forecast"]
    art = ROOT / cfg["paths"]["artifacts"]
    ev, meta = _read(art / "forecast_eval.json"), _read(art / "forecast_meta.json")
    if ev is None or meta is None:
        return
    frame = pd.read_parquet(art / "forecast.parquet")
    totals = sc.scenario_totals(frame)
    plot_scenarios(cfg)

    hm = pd.DataFrame(ev["holdout_metrics"]).T[["mae", "mape", "one_step_abs_error"]]
    hm.columns = ["MAE", "MAPE %", "1-step abs error"]
    ro = pd.DataFrame(ev["rolling"]["summary"]).T
    ro.columns = ["MAE", "MAPE %", "1-step MAE"]
    best_h = hm["MAE"].idxmin()
    best_r = ro["MAE"].idxmin()
    arima_h_rank = int(hm["MAE"].rank().loc["arima"])
    arima_r_rank = int(ro["MAE"].rank().loc["arima"])
    beats = {"holdout": [m for m in hm.index if m != "arima" and hm.loc["arima", "MAE"] < hm.loc[m, "MAE"]],
             "rolling": [m for m in ro.index if m != "arima" and ro.loc["arima", "MAE"] < ro.loc[m, "MAE"]]}
    d_tab = pd.DataFrame(ev["d_selection"]["tests"])
    aic = pd.DataFrame(ev["aic_table"])
    lb = pd.DataFrame(ev["ljung_box"])
    ac = ev["acf_pacf"]
    order = tuple(ev["order"])
    aic_gap = float(aic["aic"].iloc[1] - aic["aic"].iloc[0]) if len(aic) > 1 else float("nan")
    cur = fc["currency"]
    far_pacf = [l for l in ac["significant_pacf_lags"] if l > fc["order_grid"]["p"][1]]
    far_acf = [l for l in ac["significant_acf_lags"] if l > ac["q_hat"]]
    if ac["p_hat"] == 1 and ac["significant_pacf_lags"][:1] == [1]:
        ar_reading = (
            "Reading: the PACF has a single strong spike at lag 1 and the ACF decays gradually "
            "(positive for the first lags, then crossing zero) instead of cutting off. That is the "
            "signature of an AR(1) process, so p = 1 is the suggestion and the ACF cutoff count (q = "
            f"{ac['q_hat']}) is not meaningful when the ACF tails off. Significant lags further out "
            f"(ACF {far_acf}, PACF {far_pacf}) are isolated, beyond the grid, and are not modelled.")
    else:
        ar_reading = ("Reading: no single clean cutoff; both functions have several significant lags, "
                      "which points to a mixed ARMA structure, and the cutoff counts are only a starting point.")

    lines = [
        "# Step 9: ARIMA on a real revenue series", "",
        "## Data and its limits", "",
        f"Series: UCI Online Retail II (a UK gift wholesaler), weekly revenue = Quantity x Price, "
        f"excluding cancellations and non-positive quantities or prices; weeks end on Sunday. "
        f"{ev['n']} weeks, {ev['start']} to {ev['end']} (incomplete first and last weeks and December 2011 "
        f"are dropped); currency {cur}. Holdout: the last {ev['holdout']} weeks "
        f"({ev['holdout_dates'][0]} to {ev['holdout_dates'][-1]}); training part: {ev['n_train']} weeks.", "",
        "Limits that matter for reading the results:", "",
        "- **Different business from the churn data.** The churn model is trained on bank customers. "
        "The forecast is portfolio revenue of a different company; the churn model only supplies the "
        "share of revenue at risk (see the scenario section).",
        "- **Two years only.** The series contains two Q4 peaks and two Christmas shutdown weeks (zero "
        "sales). The training part contains one full year plus the 2010 peak, and the holdout is the "
        "2011 peak build-up, which a model trained on one earlier peak cannot anticipate unless it uses "
        "seasonal information.",
        "- Seasonal ARIMA terms were not fitted: with a 52-week period, two cycles cannot separate "
        f"seasonality from noise or identify seasonal ARMA terms (rule: at least "
        f"{fc['seasonal_grid']['min_cycles']} cycles; the series has {ev['n'] / fc['seasonal_period']:.1f}). "
        "Seasonality enters only through the seasonal-naive baseline.", "",
        "## Stationarity (training part)", "",
        d_tab.round(4).to_markdown(index=False), "",
        f"ADF with a constant, lag length by AIC. Chosen d = {ev['d_selection']['d']} "
        f"(smallest d whose p-value is below {fc['adf']['alpha']}). The test rejects a unit root for the "
        "level; this means the series reverts to a level after the spikes, not that it has no seasonal "
        "pattern.", "",
        "## ACF / PACF", "",
        "![ACF and PACF](figures/acf_pacf.png)", "",
        f"Approximate 95% band +-{ac['band']:.3f} (n = {ac['n']}). Significant ACF lags: "
        f"{ac['significant_acf_lags']}; significant PACF lags: {ac['significant_pacf_lags']}. "
        f"Cutoff rule (consecutive significant lags from lag 1): PACF suggests p = {ac['p_hat']}, ACF "
        f"suggests q = {ac['q_hat']}. " + ar_reading, "",
        "## Order selection (AIC on the training part)", "",
        aic.round(2).to_markdown(index=False), "",
        f"Chosen: ARIMA{order} (lowest AIC). ACF/PACF reading was p = {ac['p_hat']}, q = {ac['q_hat']}; "
        f"AIC agrees: {ev['aic_agrees_with_acf_pacf']}. The next-best order is only {aic_gap:.2f} AIC units "
        "behind, so several low orders are statistically indistinguishable and the choice is not "
        "sharp.", "",
        "## Residual diagnostics", "",
        lb.round(4).to_markdown(index=False), "",
        "Ljung-Box null: no residual autocorrelation (degrees of freedom reduced by p + q). "
        + ("Residuals show no leftover autocorrelation at these lags. " if (lb["p"] > 0.05).all()
           else "Some lags reject whiteness. ")
        + "This says the ARIMA captures the short-memory structure; it says nothing about the seasonal "
        "pattern, which a non-seasonal model cannot capture.", "",
        "![Residual ACF](figures/residual_acf.png)", "",
        "## Baseline comparison", "",
        f"Holdout ({ev['holdout']} weeks, one split). Moving-average window chosen on the training part: "
        f"{ev['ma_window']} (candidates scored inside the training part only). MAPE excludes zero-sales weeks.", "",
        hm.round(2).to_markdown(), "",
        f"Rolling-origin backtest: {ev['rolling']['n_origins']} expanding-window origins "
        f"({fc['rolling']['step']} weeks apart, last origin = start of the holdout); the order, d and "
        "window are re-selected from data before each origin. Mean over origins:", "",
        ro.round(2).to_markdown(), "",
        f"Lowest MAE per origin (count of origins won): {ev['rolling']['wins_by_mae']}.", "",
        "**Verdict.** "
        f"On the holdout ARIMA ranks {arima_h_rank} of {len(hm)} by MAE (best: {best_h}); in the rolling "
        f"backtest it ranks {arima_r_rank} of {len(ro)} (best: {best_r}). "
        + (f"ARIMA beats {', '.join(beats['holdout']) or 'no baseline'} on the holdout and "
           f"{', '.join(beats['rolling']) or 'no baseline'} in the rolling backtest. ")
        + ("ARIMA does not beat the simplest baselines on this series. " if best_h != "arima" and best_r != "arima"
           else "")
        + "The series is dominated by a recurring Q4 peak and a Christmas shutdown that a non-seasonal ARIMA "
        "cannot anticipate; the seasonal-naive baseline (same week a year earlier) uses that information "
        "directly. One earlier year of history is the binding limit, not the choice of ARIMA order.", "",
        "## Forecast and scenarios", "",
        f"Final fit on the full series: ARIMA{tuple(ev['final_order'])}, forecasting {fc['horizon']} weeks "
        f"with {fc['ci_level']:.0%} intervals (lower bound floored at 0). The weeks ahead include the "
        "Christmas shutdown; the model has no way to know that and will over-forecast those weeks.", "",
        "The two series come from different datasets. ARIMA forecasts portfolio revenue; the churn model "
        "estimates the share of that revenue at risk:", "",
        "- L = sum p_i v_i / sum v_i on the churn **test split** with calibrated probabilities "
        f"= {meta['loss_rate']:.4f} ({meta['n_test']} customers).",
        "- no_intervention = forecast x (1 - L).",
        "- L' = L - (expected revenue saved by the Step 8 segment-aware, offer-snapped allocation on the "
        "same test customers) / sum v_i; with_allocation = forecast x (1 - L')."
        + (f" Here saved = {meta['saved']:,.0f} of {meta['total_value']:,.0f} total customer value, so L' = "
           f"{meta['loss_rate_allocation']:.4f}." if "saved" in meta else ""), "",
        "Totals over the horizon: "
        + ", ".join(f"{k} {v:,.0f} {cur}" for k, v in sorted(totals.items())) + "."
        + (f" The allocation lifts the horizon total by {totals['with_allocation'] / totals['no_intervention'] - 1:.2%}"
           " (the two lines in the figure are almost on top of each other): the Step 8 budget is small next to the "
           "revenue at risk, so the mechanism is visible but the effect is small." if len(totals) == 2 else ""), "",
        "![Forecast scenarios](figures/forecast_scenarios.png)", "",
        "Caveats: L is a ratio from a bank dataset applied to a retailer's revenue forecast, so the "
        "scenario totals illustrate the mechanism; they are not an estimate for either business. The "
        "allocation saving is itself based on assumed response curves (Step 8). Weekly data keep the "
        "parquet column name `month`, which holds the week-ending Sunday; `GET /forecast` returns a "
        "`freq` field (`W-SUN`).", ""]
    (ROOT / cfg["paths"]["reports"] / "09_timeseries.md").write_text("\n".join(lines), encoding="utf-8")
