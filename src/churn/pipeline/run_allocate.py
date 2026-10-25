"""Step 6 entrypoint: `make allocate`."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from churn.allocate import groups as gp
from churn.allocate import offers as of
from churn.allocate import strategies as st
from churn.allocate.evaluate import load_eval_problem
from churn.risk import scenarios as sc
from churn.risk.forecast_report import write_forecast_report
from churn.allocate.report import write_report
from churn.allocate import solver as sv
from churn.config import ROOT, ensure_dirs, load_config


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    artifacts = ROOT / cfg["paths"]["artifacts"]

    scores = pd.read_parquet(artifacts / "scores.parquet")
    seg = pd.read_parquet(artifacts / "segments.parquet")
    p_cal = scores["p_churn_calibrated"].to_numpy(float)
    v = (scores["customer_value"].to_numpy(float) if "customer_value" in scores
         else scores["revenue_at_risk"].to_numpy(float) / np.maximum(p_cal, 1e-9))
    budget = float(cfg["budget"]["total"])
    cap = float(cfg["budget"]["max_spend_per_customer"])
    feats = pd.read_parquet(ROOT / cfg["paths"]["processed"] / "features.parquet")
    table = gp.build_group_table(seg, feats, cfg)
    table.to_parquet(artifacts / "group_params.parquet", index=False)

    seg_idx = seg.set_index("customer_id").loc[scores["customer_id"]]
    a, tau = gp.customer_params(seg_idx["segment_id"].to_numpy(),
                                seg_idx["value_tier"].to_numpy(), table, v)

    # ---- chosen allocation: segment-aware KKT (README claim 2), then offer snapping
    acfg = cfg["allocation"]
    x_cont = sv.kkt_allocate(p_cal, v, a, tau, budget, cap)
    saved_cont = sv.expected_saved(x_cont, p_cal, v, a, tau)
    tier_all = seg_idx["value_tier"].to_numpy()
    eng_all = gp.customer_attr(seg_idx["segment_id"].to_numpy(), tier_all, table, "engagement_class")
    snapped = of.allocate_with_offers(
        lambda b: sv.kkt_allocate(p_cal, v, a, tau, b, cap), v, tier_all, eng_all, budget, cap,
        acfg["offers"], acfg["min_spend"], acfg["rebalance_max_iter"], acfg["rebalance_tol"])
    s, offer_arr = snapped["spend"], snapped["offer"]
    saved = sv.expected_saved(s, p_cal, v, a, tau)
    grad_s, grad_obj = sv.gradient_check(p_cal, v, a, tau, budget, cap)
    grad_saved = float(sv.expected_saved(grad_s, p_cal, v, a, tau).sum())
    rel_gap = abs(grad_saved - float(saved_cont.sum())) / float(saved_cont.sum())
    tol = cfg["allocation"]["dual_check_tolerance"]
    assert rel_gap <= tol, f"KKT vs dual ascent gap {rel_gap:.4%} exceeds {tol:.1%}"

    band_arr = scores["risk_band"].to_numpy()
    seg_id_arr = seg_idx["segment_id"].to_numpy()
    seg_name_arr = seg_idx["segment_name"].to_numpy()
    tier_arr = seg_idx["value_tier"].to_numpy()
    cid_arr = scores["customer_id"].to_numpy()
    rows = []
    for i in range(len(scores)):
        if s[i] <= 0:
            continue
        offer = offer_arr[i]
        reason = (f"{gp.explain_group(table, int(seg_id_arr[i]), tier_arr[i], cfg)}. "
                  f"{offer} ({s[i]:,.0f}) protects {saved[i]:,.0f} of "
                  f"{p_cal[i] * v[i]:,.0f} at risk")
        rows.append({
            "customer_id": cid_arr[i],
            "segment_id": int(seg_id_arr[i]),
            "segment_name": seg_name_arr[i],
            "value_tier": tier_arr[i],
            "offer": offer,
            "spend": float(s[i]),
            "expected_revenue_saved": float(saved[i]),
            "reason": reason,
        })
    alloc = pd.DataFrame(rows)
    alloc.to_parquet(artifacts / "allocations.parquet", index=False)

    # ---- with_allocation forecast scenario: L' = L - saved / sum(v) on the churn test split
    base = pd.read_parquet(artifacts / "forecast_base.parquet")
    meta = json.loads((artifacts / "forecast_meta.json").read_text())
    fcst = pd.read_parquet(artifacts / "forecast.parquet")
    fcst = fcst[fcst["scenario"] != "with_allocation"]
    pr_t, _, _, scale = load_eval_problem(cfg, cfg["allocation"]["eval_split"])
    snap_t = st.allocate_snapped("segment_aware_kkt", pr_t, budget * scale, cfg["allocation"])
    saved_t = float(sv.expected_saved(snap_t["spend"], pr_t.p, pr_t.v, pr_t.a, pr_t.tau).sum())
    loss_alloc = sc.reduced_loss_rate(meta["loss_rate"], saved_t, float(pr_t.v.sum()))
    alt = sc.scenario_frame(None, base, loss_alloc, "with_allocation", include_history=False)
    pd.concat([fcst, alt], ignore_index=True).to_parquet(artifacts / "forecast.parquet", index=False)
    meta.update({"saved": saved_t, "loss_rate_allocation": loss_alloc,
                 "allocation_budget_test": float(budget * scale)})
    (artifacts / "forecast_meta.json").write_text(json.dumps(meta, indent=2))
    write_forecast_report(cfg)

    report = {
        "budget": budget, "currency": cfg["budget"]["currency"],
        "gradient_check": {"kkt_objective": float(saved_cont.sum()), "gradient_objective": grad_saved,
                           "rel_gap": rel_gap},
        "allocated_customers": int(len(alloc)),
        "offer_snapping": {
            "continuous_saved": float(saved_cont.sum()), "snapped_saved": float(saved.sum()),
            "snapped_spend": float(s.sum()), "iterations": snapped["iterations"],
            "effective_budget": snapped["effective_budget"], "dropped": snapped["dropped"],
            "offer_counts": pd.Series(offer_arr[s > 0]).value_counts().to_dict()},
        "forecast_scenario": {"loss_rate": meta["loss_rate"], "loss_rate_allocation": loss_alloc,
                              "saved_test_split": saved_t},
        "assumptions": {
            "response_curve": "expected saved = p*v*a_g*(1-exp(-x/tau_i)), tau_i = t_g*v_i",
            "group_params": table.to_dict("records"),
            "note": "offer response curves are assumptions, not measured uplift",
        },
    }
    (artifacts / "allocation_report.json").write_text(json.dumps(report, indent=2, default=str))

    write_report(cfg)

    print(f"allocations.parquet: {len(alloc)} rows, spent {alloc['spend'].sum():,.0f}, "
          f"expected saved {alloc['expected_revenue_saved'].sum():,.0f}")


if __name__ == "__main__":
    main()
