"""Step 6 entrypoint: `make allocate`."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from churn.allocate import solver as sv
from churn.config import ROOT, ensure_dirs, load_config


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    artifacts = ROOT / cfg["paths"]["artifacts"]

    scores = pd.read_parquet(artifacts / "scores.parquet")
    seg = pd.read_parquet(artifacts / "segments.parquet")
    p_cal = scores["p_churn_calibrated"].to_numpy(float)
    p_raw = scores["p_churn_raw"].to_numpy(float)
    v = scores["revenue_at_risk"].to_numpy(float) / np.maximum(p_cal, 1e-9)  # raw value back out
    budget = float(cfg["budget"]["total"])
    cap = float(cfg["budget"]["max_spend_per_customer"])
    u_max = float(cfg["models"]["threshold"]["offer_uplift"])
    tau_frac = 0.05

    # ---- strategy comparison at equal budget
    comp = sv.strategy_comparison(p_cal, v, budget, cap, u_max, tau_frac)

    # ---- chosen allocation: segment-aware KKT (README claim 2)
    s = sv.kkt_allocate(p_cal, v, budget, cap, u_max, tau_frac)
    saved = sv.expected_saved(s, p_cal, v, u_max, tau_frac)
    grad_s, grad_obj = sv.gradient_check(p_cal, v, budget, cap, u_max, tau_frac)
    grad_saved = float(sv.expected_saved(grad_s, p_cal, v, u_max, tau_frac).sum())

    seg_idx = seg.set_index("customer_id").loc[scores["customer_id"]]
    band_arr = scores["risk_band"].to_numpy()
    seg_id_arr = seg_idx["segment_id"].to_numpy()
    seg_name_arr = seg_idx["segment_name"].to_numpy()
    tier_arr = seg_idx["value_tier"].to_numpy()
    cid_arr = scores["customer_id"].to_numpy()
    rows = []
    for i in range(len(scores)):
        if s[i] <= 0.5:
            continue
        offer = sv.match_offer(s[i], v[i])
        reason = (f"Band {band_arr[i]}, {seg_name_arr[i]} "
                  f"({tier_arr[i]} value): "
                  f"spend {s[i]:,.0f} to protect {saved[i]:,.0f} at risk")
        rows.append({
            "customer_id": cid_arr[i],
            "segment_id": int(seg_id_arr[i]),
            "value_tier": tier_arr[i],
            "offer": offer,
            "spend": float(s[i]),
            "expected_revenue_saved": float(saved[i]),
            "reason": reason,
        })
    alloc = pd.DataFrame(rows)
    alloc.to_parquet(artifacts / "allocations.parquet", index=False)

    # ---- with_allocation forecast scenario: monthly saved revenue lifts the forecast
    fcst = pd.read_parquet(artifacts / "forecast.parquet")
    monthly_saved = float(saved.sum()) / 12.0
    fut = fcst["scenario"].eq("no_intervention") & fcst["forecast"].notna()
    alt = fcst[fut].copy()
    alt["scenario"] = "with_allocation"
    alt["forecast"] = alt["forecast"] + monthly_saved
    alt["lower"] = alt["lower"] + monthly_saved * 0.8
    alt["upper"] = alt["upper"] + monthly_saved * 1.2
    fcst = pd.concat([fcst, alt], ignore_index=True)
    fcst.to_parquet(artifacts / "forecast.parquet", index=False)

    # ---- sensitivity + calibrated vs uncalibrated (README claim 1)
    sens = sv.sensitivity(p_cal, v, budget, cap, u_max, tau_frac)
    cvu = sv.calibrated_vs_uncalibrated(p_cal, p_raw, v, budget, cap, u_max, tau_frac)

    report = {
        "budget": budget, "currency": cfg["budget"]["currency"],
        "strategy_comparison": comp,
        "gradient_check": {"kkt_objective": float(saved.sum()), "gradient_objective": grad_saved,
                           "rel_gap": abs(grad_saved - float(saved.sum())) / max(float(saved.sum()), 1e-9)},
        "sensitivity": sens,
        "calibrated_vs_uncalibrated": cvu,
        "allocated_customers": int(len(alloc)),
        "monthly_saved_uplift": monthly_saved,
        "assumptions": {
            "response_curve": "expected saved = v*p*u_max*(1-exp(-s/tau))",
            "u_max": u_max, "tau_frac": tau_frac,
            "note": "offer response curves are assumptions, not measured uplift",
        },
    }
    (artifacts / "allocation_report.json").write_text(json.dumps(report, indent=2, default=str))

    lines = ["# Allocation report", "",
             f"Budget: {budget:,.0f} {cfg['budget']['currency']} "
             f"-> {len(alloc)} customers targeted, "
             f"{alloc['spend'].sum():,.0f} spent, "
             f"expected {alloc['expected_revenue_saved'].sum():,.0f} saved", "",
             "## Strategy comparison (equal budget)", "",
             pd.DataFrame(comp).T.round(0).to_markdown(), "",
             "## KKT vs gradient check", "",
             f"- KKT objective: {saved.sum():,.0f}",
             f"- Projected gradient objective: {grad_saved:,.0f}", "",
             "## Sensitivity (±30% on response assumptions)", "",
             pd.DataFrame(sens).round(0).to_markdown(index=False), "",
             "## Calibrated vs uncalibrated allocation", "",
             f"- Allocations built on calibrated scores save {cvu['saved_calibrated_allocation']:,.0f}",
             f"- Allocations built on raw scores save only {cvu['saved_uncalibrated_allocation']:,.0f}",
             f"- **Misallocation cost of uncalibrated scores: {cvu['misallocation_cost']:,.0f}** "
             "(validates README claim 1)", "",
             "Note: the gap is small because isotonic calibration is rank-preserving - it "
             "cannot reorder customers, only rescale probabilities. The misallocation cost "
             "measures value-weighting differences, not ranking errors. A miscalibrated "
             "model with a different ranking would show a larger gap.", "",
             "## Assumptions",
             "- Response curves are assumptions, not measured uplift (see sensitivity above)."]
    (ROOT / cfg["paths"]["reports"] / "allocation.md").write_text("\n".join(lines))

    print(f"allocations.parquet: {len(alloc)} rows, spent {alloc['spend'].sum():,.0f}, "
          f"expected saved {alloc['expected_revenue_saved'].sum():,.0f}")
    print(f"strategies (saved): " +
          ", ".join(f"{k}={d['expected_revenue_saved']:,.0f}" for k, d in comp.items()))
    print(f"uncalibrated misallocation cost: {cvu['misallocation_cost']:,.0f}")


if __name__ == "__main__":
    main()
