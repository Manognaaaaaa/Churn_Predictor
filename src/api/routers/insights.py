"""Portfolio, forecast and model metrics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api import artifacts

router = APIRouter(tags=["insights"])


@router.get("/portfolio/summary")
def portfolio_summary():
    df = artifacts.joined()
    total_rar = float(df["revenue_at_risk"].sum())
    by_segment = (df.groupby("segment_name", dropna=True)
                    .agg(customers=("customer_id", "count"),
                         revenue_at_risk=("revenue_at_risk", "sum"))
                    .reset_index())
    return {
        "n_customers": int(len(df)),
        "total_revenue_at_risk": round(total_rar, 2),
        "band_counts": df["risk_band"].value_counts().to_dict(),
        "by_segment": [{"segment_name": r.segment_name,
                        "customers": int(r.customers),
                        "revenue_at_risk": round(float(r.revenue_at_risk), 2)}
                       for r in by_segment.itertuples()],
    }


@router.get("/forecast")
def forecast(scenario: str = Query("no_intervention",
                                   pattern="^(no_intervention|with_allocation)$")):
    fc = artifacts._forecast()
    fc = fc[fc["scenario"] == scenario]
    if fc.empty:
        raise HTTPException(404, f"No forecast for scenario {scenario}")
    points = [{"month": str(r.month),
               "actual": None if pd_isna(r.actual) else round(float(r.actual), 2),
               "forecast": None if pd_isna(r.forecast) else round(float(r.forecast), 2),
               "lower": None if pd_isna(r.lower) else round(float(r.lower), 2),
               "upper": None if pd_isna(r.upper) else round(float(r.upper), 2)}
              for r in fc.itertuples()]
    return {"scenario": scenario, "points": points}


def pd_isna(x) -> bool:
    return x is None or x != x


@router.get("/model/metrics")
def model_metrics():
    m = artifacts._metrics()
    models = m.get("models", {})
    if isinstance(models, dict):
        models = [{"name": name, **vals} for name, vals in models.items()]
    thr = m.get("threshold", {})
    return {
        "models": models,
        "best_model": m.get("best_model"),
        "calibration": m.get("calibration"),
        "test": m.get("test", {}),
        "threshold": thr,
        "calibration_curve": m.get("calibration_curve", []),
    }
