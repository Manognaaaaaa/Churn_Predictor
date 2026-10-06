"""Step 5 entrypoint: `make risk` — forecast.parquet + segments.parquet."""
from __future__ import annotations

import json

import pandas as pd

from churn.config import ROOT, ensure_dirs, load_config
from churn.risk import forecast as fc
from churn.risk.segments import build_segments


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    artifacts = ROOT / cfg["paths"]["artifacts"]
    processed = ROOT / cfg["paths"]["processed"]

    scores = pd.read_parquet(artifacts / "scores.parquet")
    feats = pd.read_parquet(processed / "features.parquet")
    feature_cols = [c for c in feats.columns
                    if c not in ("customer_id", "churned", "snapshot_date", "split",
                                 "customer_value_raw")]

    # ---- forecast (synthetic history, documented caveat)
    fcfg = cfg["forecast"]
    hist = fc.synthetic_history(scores, fcfg["history_months"], cfg["seed"])
    diag = fc.diagnostics(hist)
    # pick ARIMA order by backtest instead of trusting the config default
    candidates = [tuple(fcfg["arima_order"]), (1, 0, 0), (2, 0, 0), (1, 0, 1)]
    cands = []
    for order in candidates:
        b = fc.backtest(hist, order, fcfg["baseline_window"])
        cands.append({"order": list(order), **b})
    best_order = tuple(min(cands, key=lambda c: c["arima_mae"])["order"])
    bt = fc.backtest(hist, best_order, fcfg["baseline_window"])
    arima_fc = fc.fit_forecast(hist, best_order, fcfg["months_ahead"])
    ma_fc = fc.moving_average_baseline(hist, fcfg["baseline_window"], fcfg["months_ahead"])

    frames = [pd.DataFrame({"month": hist.index, "actual": hist.to_numpy(),
                            "forecast": [None] * len(hist), "lower": [None] * len(hist),
                            "upper": [None] * len(hist), "scenario": "no_intervention"}),
              arima_fc.assign(scenario="no_intervention")]
    f = pd.concat(frames, ignore_index=True)
    f.to_parquet(artifacts / "forecast.parquet", index=False)

    # ---- segments
    seg, seg_meta = build_segments(scores, feats, feature_cols, cfg)
    seg.to_parquet(artifacts / "segments.parquet", index=False)

    summary = {
        "forecast": {"diagnostics": diag, "backtest": bt,
                     "arima_order": list(best_order),
                     "order_candidates": cands,
                     "next_12m_forecast_total": float(arima_fc["forecast"].sum())},
        "segments": seg_meta,
        "portfolio": {
            "n_customers": int(len(scores)),
            "total_revenue_at_risk": float(scores["revenue_at_risk"].sum()),
            "band_counts": scores["risk_band"].value_counts().to_dict(),
            "red_revenue_share": float(
                scores.loc[scores.risk_band == "red", "revenue_at_risk"].sum()
                / scores["revenue_at_risk"].sum()),
        },
    }
    (artifacts / "risk_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(f"forecast: ARIMA MAE {bt['arima_mae']:,.0f} vs MA-baseline {bt['ma_baseline_mae']:,.0f}")
    print(f"segments: k={seg_meta['chosen_k']} (BIC), "
          f"{seg['segment_name'].nunique()} named segments")
    print(f"portfolio: total revenue at risk "
          f"{summary['portfolio']['total_revenue_at_risk']:,.0f}, "
          f"bands {summary['portfolio']['band_counts']}")


if __name__ == "__main__":
    main()
