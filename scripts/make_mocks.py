"""Generate small mock versions of the pipeline artifacts (v0 contracts).

Lets the app track (API + dashboard) start before the models exist.
Writes to artifacts/mock/. Schemas follow docs/contracts.md.

Usage: python scripts/make_mocks.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "config.yaml").read_text())
OUT = ROOT / CFG["paths"]["artifacts"] / "mock"
N = 200

FEATURES = {
    "days_since_last_login": "Days since last login",
    "usage_trend_slope": "Usage trend (3-month slope)",
    "tenure_months": "Tenure (months)",
    "support_tickets_90d": "Support tickets (90 days)",
    "failed_payments_90d": "Failed payments (90 days)",
    "monthly_revenue": "Monthly revenue",
}
SEGMENTS = {0: "Engaged loyalists", 1: "Fading regulars", 2: "Price sensitive", 3: "Support heavy"}
OFFERS = ["discount_10", "discount_20", "free_month", "service_call", "none"]


def band(p: float) -> str:
    r = CFG["risk_bands"]
    return "green" if p <= r["green_max"] else "amber" if p <= r["amber_max"] else "red"


def main() -> None:
    rng = np.random.default_rng(CFG["seed"])
    OUT.mkdir(parents=True, exist_ok=True)
    ids = [f"C{i:05d}" for i in range(N)]
    snapshot = pd.Timestamp("2024-06-30").date()

    # scores
    raw = rng.beta(2, 5, N)
    cal = np.clip(raw * 0.8 + rng.normal(0, 0.02, N), 0.001, 0.999)
    value = rng.lognormal(5, 0.6, N)  # annual customer value
    drivers = []
    for _ in range(N):
        feats = rng.choice(list(FEATURES), 5, replace=False)
        contribs = np.sort(rng.normal(0, 0.3, 5))[::-1]
        drivers.append([
            {"feature": f, "label": FEATURES[f], "contribution": float(c)}
            for f, c in zip(feats, contribs)
        ])
    scores = pd.DataFrame({
        "customer_id": ids,
        "snapshot_date": snapshot,
        "p_churn_raw": raw,
        "p_churn_calibrated": cal,
        "risk_band": [band(p) for p in cal],
        "revenue_at_risk": cal * value,
        "top_drivers": drivers,
    })
    scores.to_parquet(OUT / "scores.parquet", index=False)

    # segments
    seg_id = rng.integers(0, len(SEGMENTS), N)
    tier = pd.qcut(value, 3, labels=CFG["segmentation"]["value_tiers"]).astype(str)
    pd.DataFrame({
        "customer_id": ids,
        "segment_id": seg_id,
        "segment_name": [SEGMENTS[s] for s in seg_id],
        "value_tier": tier,
    }).to_parquet(OUT / "segments.parquet", index=False)

    # allocations: spend on riskiest customers until the budget is used
    order = np.argsort(-scores["revenue_at_risk"].to_numpy())
    budget, spent = CFG["budget"]["total"] / 100, 0.0  # scaled down for 200 mock customers
    rows = []
    for i in order:
        spend = float(min(CFG["budget"]["max_spend_per_customer"] / 10, budget - spent))
        if spend <= 0:
            break
        spent += spend
        offer = OFFERS[int(rng.integers(0, len(OFFERS) - 1))]
        rows.append({
            "customer_id": ids[i],
            "segment_id": int(seg_id[i]),
            "value_tier": tier[i],
            "offer": offer,
            "spend": spend,
            "expected_revenue_saved": spend * float(rng.uniform(1.2, 3.5)),
            "reason": f"High revenue at risk; {SEGMENTS[int(seg_id[i])]} respond to {offer}",
        })
    pd.DataFrame(rows).to_parquet(OUT / "allocations.parquet", index=False)

    # forecast: 24 months of actuals, 6 months ahead, two scenarios
    months = pd.period_range("2022-07", periods=30, freq="M").to_timestamp()
    base = 100_000 + np.cumsum(rng.normal(-300, 1500, 30))
    frames = []
    for scenario, lift in [("no_intervention", 0.0), ("with_allocation", 400.0)]:
        fc = base.copy()
        fc[24:] += lift * np.arange(1, 7)
        frames.append(pd.DataFrame({
            "month": months,
            "actual": np.where(np.arange(30) < 24, base, np.nan),
            "forecast": np.where(np.arange(30) >= 24, fc, np.nan),
            "lower": np.where(np.arange(30) >= 24, fc - 4000, np.nan),
            "upper": np.where(np.arange(30) >= 24, fc + 4000, np.nan),
            "scenario": scenario,
        }))
    pd.concat(frames, ignore_index=True).to_parquet(OUT / "forecast.parquet", index=False)

    print(f"Wrote 4 mock files to {OUT}")


if __name__ == "__main__":
    main()
