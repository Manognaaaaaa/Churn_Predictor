"""Budget allocation endpoints. Validate input, call src/churn, return results (no ML here)."""
from __future__ import annotations

import csv
import io
import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
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


def _run(budget: float, strategy: str):
    """Solve and snap one allocation. Returns (problem, seg ids, seg names, spend, offers, saved)."""
    cfg = load_config()
    pr, seg_ids, seg_names = _problem(cfg)
    snapped = st.allocate_snapped(STRATEGY_MAP[strategy], pr, budget, cfg["allocation"])
    s, offers = snapped["spend"], snapped["offer"]
    return pr, seg_ids, seg_names, s, offers, sv.expected_saved(s, pr.p, pr.v, pr.a, pr.tau)


def _group(keys: np.ndarray, targeted: np.ndarray, s: np.ndarray, saved: np.ndarray) -> list[dict]:
    df = pd.DataFrame({"k": keys[targeted], "spend": s[targeted], "kept": saved[targeted]})
    g = df.groupby("k").agg(customers=("spend", "size"), spend=("spend", "sum"), kept=("kept", "sum"))
    return [{"key": k, "customers": int(r.customers), "spend": round(float(r.spend), 2),
             "expected_revenue_saved": round(float(r.kept), 2)} for k, r in g.sort_values("spend", ascending=False).iterrows()]


@router.post("/allocate")
def allocate(req: AllocateRequest):
    cfg = load_config()
    scores = artifacts._scores()
    pr, seg_ids, seg_names, s, offers, saved = _run(req.budget, req.strategy)
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
    by_offer = [{"offer": g.pop("key"), **g} for g in _group(np.asarray(offers, dtype=object), targeted, s, saved)]
    by_segment = [{"segment_name": g.pop("key"), **g} for g in _group(np.asarray(seg_names, dtype=object), targeted, s, saved)]
    return {
        "budget": req.budget,
        "spent": round(float(s.sum()), 2),
        "expected_revenue_saved": round(float(saved.sum()), 2),
        "strategy": req.strategy,
        "n_targeted": int(len(targeted)),
        "allocations": allocations,
        "by_offer": by_offer,
        "by_segment": by_segment,
    }


@router.get("/allocate/export")
def allocate_export(budget: float = Query(gt=0), strategy: str = Query("segment_aware", pattern="^(" + "|".join(STRATEGY_MAP) + ")$")):
    """Every targeted customer for one budget and strategy, as CSV (the /allocate response is capped)."""
    pr, seg_ids, seg_names, s, offers, saved = _run(budget, strategy)
    people = artifacts.people().set_index("customer_id")
    cid = artifacts._scores()["customer_id"].to_numpy()
    targeted = np.flatnonzero(s > 0)
    targeted = targeted[np.argsort(-saved[targeted])]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["customer_id", "surname", "country", "group", "offer", "cost", "value_kept"])
    for i in targeted:
        p = people.loc[cid[i]] if cid[i] in people.index else None
        w.writerow([cid[i], "" if p is None or pd.isna(p.get("Surname")) else p["Surname"],
                    "" if p is None or pd.isna(p.get("Geography")) else p["Geography"], seg_names[i], offers[i],
                    f"{s[i]:.2f}", f"{saved[i]:.2f}"])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=retention-offers.csv"})


CURVE_BUDGETS = list(range(100_000, 5_000_001, 100_000))
_curves: dict[str, dict] = {}


class CurveRequest(BaseModel):
    strategy: str = Field("segment_aware", pattern="^(" + "|".join(STRATEGY_MAP) + ")$")


@router.post("/allocate/curve")
def allocate_curve(req: CurveRequest):
    """Value kept at budgets 100K to 5M (step 100K) from the real solver. Cached in memory and on disk."""
    stamp = (artifacts.artifacts_dir() / "scores.parquet").stat().st_mtime
    cached = _curves.get(req.strategy)
    path = artifacts.artifacts_dir() / f"allocation_curve_{req.strategy}.json"
    if cached is None and path.exists():
        disk = json.loads(path.read_text())
        cached = disk if disk.get("stamp") == stamp else None
    if cached is None or cached.get("stamp") != stamp:
        pts = []
        for b in CURVE_BUDGETS:
            pr, _, _, s, _, saved = _run(float(b), req.strategy)
            pts.append({"budget": b, "spent": round(float(s.sum()), 2),
                        "expected_revenue_saved": round(float(saved.sum()), 2),
                        "n_targeted": int((s > 0).sum())})
        cached = {"strategy": req.strategy, "stamp": stamp, "points": pts}
        path.write_text(json.dumps(cached))
    _curves[req.strategy] = cached
    return {"strategy": req.strategy, "points": cached["points"]}


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
