"""Step 5 entrypoint: `make risk` — forecast.parquet + segments.parquet."""
from __future__ import annotations

import json

import pandas as pd

from churn.config import ROOT, ensure_dirs, load_config
from churn.risk import forecast as fc
from churn.risk import scenarios as sc
from churn.risk.forecast_report import write_forecast_report
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

    # ---- forecast: ARIMA on the real revenue series, no_intervention scenario
    fcfg = cfg["forecast"]
    study = fc.run_study(cfg)
    summ = study["summary"]
    test = scores[scores["split"] == "test"]
    p_t = test["p_churn_calibrated"].to_numpy(float)
    v_t = test["customer_value"].to_numpy(float)
    loss = sc.loss_rate(p_t, v_t)
    base = study["final_frame"]
    frame = sc.scenario_frame(study["series"], base, loss, "no_intervention", include_history=True)
    frame.to_parquet(artifacts / "forecast.parquet", index=False)
    base.to_parquet(artifacts / "forecast_base.parquet", index=False)
    meta = {"loss_rate": loss, "n_test": int(len(test)), "total_value": float(v_t.sum()),
            "freq": fcfg["freq"], "source": fcfg["source"], "currency": fcfg["currency"]}
    (artifacts / "forecast_meta.json").write_text(json.dumps(meta, indent=2))
    (artifacts / "forecast_eval.json").write_text(json.dumps(summ, indent=2, default=float))
    write_forecast_report(cfg)

    # ---- segments
    seg, seg_meta = build_segments(scores, feats, feature_cols, cfg)
    seg.to_parquet(artifacts / "segments.parquet", index=False)

    summary = {
        "forecast": {"source": fcfg["source"], "freq": fcfg["freq"], "arima_order": summ["order"],
                     "holdout_metrics": summ["holdout_metrics"],
                     "rolling_summary": summ["rolling"]["summary"],
                     "loss_rate": loss,
                     "horizon_forecast_total": float(base["forecast"].sum())},
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

    hm = summ["holdout_metrics"]
    print(f"forecast ({fcfg['source']}, {fcfg['freq']}): ARIMA{tuple(summ['order'])} holdout MAE "
          + ", ".join(f"{k} {v['mae']:,.0f}" for k, v in hm.items()) + f" | churn loss rate L={loss:.4f}")
    print(f"segments: k={seg_meta['chosen_k']} (BIC), "
          f"{seg['segment_name'].nunique()} named segments")
    print(f"portfolio: total revenue at risk "
          f"{summary['portfolio']['total_revenue_at_risk']:,.0f}, "
          f"bands {summary['portfolio']['band_counts']}")


if __name__ == "__main__":
    main()
