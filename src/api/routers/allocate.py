"""Budget allocation endpoint (runs the step-6 solver on demand)."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api import artifacts
from churn.allocate import solver as sv
from churn.config import load_config

router = APIRouter(tags=["allocation"])


class AllocateRequest(BaseModel):
    budget: float = Field(gt=0)
    strategy: str = Field("segment_aware", pattern="^(segment_aware|uniform|risk_proportional)$")


@router.post("/allocate")
def allocate(req: AllocateRequest):
    scores = artifacts._scores()
    segments = artifacts._segments()
    cfg = load_config()
    cap = float(cfg["budget"]["max_spend_per_customer"])

    p = scores["p_churn_calibrated"].to_numpy(float)
    rar = scores["revenue_at_risk"].to_numpy(float)
    v = rar / np.maximum(p, 1e-9)

    if req.strategy == "segment_aware":
        s = sv.kkt_allocate(p, v, req.budget, cap)
    elif req.strategy == "uniform":
        s = np.full(len(p), min(req.budget / len(p), cap))
    else:
        share = (v * p) / max((v * p).sum(), 1e-12)
        s = np.minimum(share * req.budget, cap)

    saved = sv.expected_saved(s, p, v)
    seg = segments.set_index("customer_id").loc[scores["customer_id"]]
    tier = seg["value_tier"].to_numpy()
    seg_id = seg["segment_id"].to_numpy()
    cid = scores["customer_id"].to_numpy()

    allocations = [{
        "customer_id": cid[i],
        "segment_id": int(seg_id[i]),
        "value_tier": tier[i],
        "offer": sv.match_offer(s[i], v[i]),
        "spend": round(float(s[i]), 2),
        "expected_revenue_saved": round(float(saved[i]), 2),
        "reason": f"{tier[i]}-value customer, band {scores['risk_band'][i]}; "
                  f"spend {s[i]:,.0f} to protect {saved[i]:,.0f}",
    } for i in np.argsort(-s) if s[i] > 0.5]

    return {
        "budget": req.budget,
        "spent": round(float(s.sum()), 2),
        "expected_revenue_saved": round(float(saved.sum()), 2),
        "strategy": req.strategy,
        "allocations": allocations[:500],
    }
