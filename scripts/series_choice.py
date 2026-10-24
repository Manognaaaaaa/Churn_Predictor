"""Phase 9.0: build both candidate series, run ADF / trend / seasonality, save plots and a JSON.

Usage: PYTHONPATH=src python scripts/series_choice.py
Writes artifacts/series_choice.json and reports/figures/series_option_{a,b}.png.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose

from churn.config import ROOT, load_config
from churn.risk import series as sr


def _load_retail(cfg_src: dict) -> pd.DataFrame:
    cache = ROOT / cfg_src["cache"]
    if cache.exists():
        return pd.read_parquet(cache)
    sheets = pd.read_excel(ROOT / cfg_src["path"], sheet_name=None,
                           usecols=["Invoice", "Quantity", "InvoiceDate", "Price"])
    df = pd.concat(sheets.values(), ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df["Invoice"] = df["Invoice"].astype(str)
    df.to_parquet(cache, index=False)
    return df


def _decomp_axes(axs, s: pd.Series, period: int, model: str, title: str) -> None:
    dec = seasonal_decompose(s, model=model, period=period)
    for ax, comp, lab in zip(axs, (dec.trend, dec.seasonal, dec.resid), ("trend", "seasonal", "residual")):
        ax.plot(comp.index, comp.to_numpy(), lw=1)
        ax.set_ylabel(lab, fontsize=8)
        ax.grid(alpha=0.3)
    axs[0].set_title(title, fontsize=9)


def main() -> None:
    cfg = load_config()
    fc = cfg["forecast"]
    ch = fc["choice_report"]
    figs = ROOT / cfg["paths"]["reports"] / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    results: dict = {}

    # ---------------- Option A: Telco reconstruction
    src = fc["sources"]["telco_reconstruction"]
    tel = pd.read_excel(ROOT / src["path"])
    a = sr.reconstruct_telco_revenue(tel[src["tenure_col"]].to_numpy(), tel[src["charge_col"]].to_numpy(),
                                     src["snapshot_month"], src["months"], src["freq"])
    results["A"] = {**sr.describe_series(a, ch["seasonal_period"][src["freq"]], ch["adf_regression"],
                                         ch["decomposition_model"]),
                    "n_customers": int(len(tel)), "first": float(a.iloc[0]), "last": float(a.iloc[-1]),
                    "share_monotone_up": float((a.diff().dropna() >= 0).mean()),
                    "n_customers_active_first_month": int((tel[src["tenure_col"]] >= src["months"]).sum())}
    fig, axs = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
    axs[0].plot(a.index, a.to_numpy())
    axs[0].set_title("Option A: Telco reconstructed monthly active revenue (72 months, assumed snapshot "
                     f"{src['snapshot_month']})", fontsize=9)
    axs[0].grid(alpha=0.3)
    _decomp_axes(axs[1:], a, ch["seasonal_period"][src["freq"]], ch["decomposition_model"], "decomposition (period 12)")
    fig.tight_layout()
    fig.savefig(figs / "series_option_a.png", dpi=120)
    plt.close(fig)

    # ---------------- Option B: Online Retail II
    rsrc = fc["sources"]["online_retail"]
    raw = _load_retail(rsrc)
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"])
    first, last = raw["InvoiceDate"].min(), raw["InvoiceDate"].max()
    sales = sr.clean_retail(raw, rsrc["drop_invoice_prefix"], rsrc["min_quantity"], rsrc["min_price"])
    b_w = sr.aggregate_retail(sales, "W-SUN", first, last)
    b_m = sr.aggregate_retail(sales, "MS", first, last)
    results["B"] = {"rows_raw": int(len(raw)), "rows_kept": int(len(sales)),
                    "first_invoice": str(first), "last_invoice": str(last),
                    "weekly": {**sr.describe_series(b_w, ch["seasonal_period"]["W-SUN"], ch["adf_regression"],
                                                    ch["decomposition_model"]),
                               "zero_weeks": int((b_w == 0).sum())},
                    "monthly": sr.describe_series(b_m, ch["seasonal_period"]["MS"], ch["adf_regression"],
                                                  ch["decomposition_model"])}
    fig, axs = plt.subplots(2, 1, figsize=(9, 6))
    axs[0].plot(b_w.index, b_w.to_numpy())
    axs[0].set_title(f"Option B: Online Retail II weekly revenue ({len(b_w)} weeks)", fontsize=9)
    axs[1].plot(b_m.index, b_m.to_numpy(), marker="o", ms=3)
    axs[1].set_title(f"monthly revenue ({len(b_m)} months; Dec 2011 partial month dropped)", fontsize=9)
    for ax in axs:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "series_option_b.png", dpi=120)
    plt.close(fig)

    fig, axs = plt.subplots(3, 2, figsize=(11, 7), sharex="col")
    _decomp_axes(axs[:, 0], b_w, ch["seasonal_period"]["W-SUN"], ch["decomposition_model"], "weekly (period 52)")
    _decomp_axes(axs[:, 1], b_m, ch["seasonal_period"]["MS"], ch["decomposition_model"], "monthly (period 12)")
    fig.tight_layout()
    fig.savefig(figs / "series_option_b_decomposition.png", dpi=120)
    plt.close(fig)

    (ROOT / cfg["paths"]["artifacts"] / "series_choice.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
