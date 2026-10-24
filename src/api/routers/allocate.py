"""Budget allocation endpoints. Validate input, call src/churn, return results (no ML here)."""
from __future__ import annotations

import json

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import artifacts
from churn.allocate import groups as gp
from churn.allocate import solver as sv
from churn.allocate import strategies as st
from churn.config import load_config

router = APIRouter(tags=["allocation"])

# API strategy name -> src/churn strategy name
STRATEGY_MAP = {"segment_aware": "segment_aware_kkt", "global": "global_kkt", "uniform": "uniform",
                "top_k_risk": "top_k_risk", "top_k_rar": "top_k_revenue_at_risk",
                "risk_proportional": "risk_proportional"}


MAX_ROWS = 500                              # allocation rows returned per call


class AllocateRequest(BaseModel):
    budget: float = Field(gt=0)
    strategy: str = Field("segment_aware", pattern="^(" + "|".join(STRATEGY_MAP) + ")$")


def _problem(cfg: dict) -> tuple[st.Problem, np.ndarray, np.ndarray]:
    """Whole-portfolio Problem from artifacts. Returns (problem, segment ids, segment names)."""
    scores, segments = artifacts._scores(), artifacts._segments()
    p = scores["p_churn_calibrated"].to_numpy(float)
    v = (scores["customer_value"].to_numpy(float) if "customer_value" in scores
         else scores["revenue_at_risk"].to_numpy(float) / np.maximum(p, 1e-9))
    seg = segments.set_index("customer_id").loc[scores["customer_id"]]
    seg_ids, tiers = seg["segment_id"].to_numpy(), seg["value_tier"].to_numpy()
    table = artifacts._group_params()
    ag, tg = gp.global_params(len(p), v, cfg)
    if table is not None:
        a, tau = gp.customer_params(seg_ids, tiers, table, v)
        eng = gp.customer_attr(seg_ids, tiers, table, "engagement_class")
    else:                                  # mock artifacts: no group table -> global curve
        a, tau, eng = ag, tg, np.full(len(p), "low")
    pr = st.Problem(p=p, v=v, a=a, tau=tau, a_glob=ag, tau_glob=tg,
                    cap=float(cfg["budget"]["max_spend_per_customer"]), tiers=tiers, engagement=eng)
    return pr, seg_ids, seg["segment_name"].to_numpy()


@router.post("/allocate")
def allocate(req: AllocateRequest):
    cfg = load_config()
    scores = artifacts._scores()
    pr, seg_ids, seg_names = _problem(cfg)
    name = STRATEGY_MAP[req.strategy]
    snapped = st.allocate_snapped(name, pr, req.budget, cfg["allocation"])
    s, offers = snapped["spend"], snapped["offer"]
    saved = sv.expected_saved(s, pr.p, pr.v, pr.a, pr.tau)
    table = artifacts._group_params()
    cid = scores["customer_id"].to_numpy()
    band = scores["risk_band"].to_numpy()
    rar = pr.p * pr.v

    targeted = np.flatnonzero(s > 0)
    top = targeted[np.argsort(-saved[targeted])][:MAX_ROWS]     # only the rows we return
    allocations = []
    for i in top:
        reason = (gp.explain_group(table, seg_ids[i], pr.tiers[i], cfg) if table is not None
                  else f"{pr.tiers[i]}-value customer, band {band[i]}")
        allocations.append({
            "customer_id": cid[i], "segment_id": int(seg_ids[i]), "segment_name": seg_names[i],
            "value_tier": pr.tiers[i], "offer": offers[i], "spend": round(float(s[i]), 2),
            "expected_revenue_saved": round(float(saved[i]), 2),
            "reason": f"{reason}. {offers[i]} ({s[i]:,.0f}) protects {saved[i]:,.0f} of {rar[i]:,.0f} at risk"})
    return {
        "budget": req.budget,
        "spent": round(float(s.sum()), 2),
        "expected_revenue_saved": round(float(saved.sum()), 2),
        "strategy": req.strategy,
        "n_targeted": int(len(targeted)),
        "allocations": allocations,
    }


@router.get("/allocate/sweep")
def allocate_sweep():
    """Budget sweep points (expected saved revenue per strategy) written by `make claims`."""
    path = artifacts.artifacts_dir() / "allocation_summary.json"
    if not path.exists():
        raise HTTPException(404, "allocation_summary.json not found - run `make claims`")
    summary = json.loads(path.read_text())
    return {"split": summary["split"], "portfolio_budgets": sorted({r["portfolio_budget"]
                                                                    for r in summary["budget_sweep"]}),
            "points": summary["budget_sweep"]}
