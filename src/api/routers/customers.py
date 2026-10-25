"""Customer endpoints: list, detail, one-page PDF report."""
from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from fpdf import FPDF

import math

import pandas as pd

from api import artifacts
from api.serialize import item
from churn.config import load_config

router = APIRouter(tags=["customers"])

DRIVER_FMT = "p={:.2f} ({:+.2f})"


@router.get("/customers")
def list_customers(
    risk_band: str | None = Query(None, pattern="^(green|amber|red)$"),
    band: str | None = Query(None, pattern="^(green|amber|red)$"),
    segment_id: int | None = None,
    search: str | None = None,
    country: str | None = None,
    min_products: int | None = Query(None, ge=1, le=4),
    active: bool | None = None,
    exited: bool | None = None,
    sort: str = Query("value_at_risk", pattern="^(value_at_risk|chance|value)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Filtered, searchable customer list (sorted by value at risk unless `sort` says otherwise)."""
    df = artifacts.people()
    b = band or risk_band
    if b:
        df = df[df["band"] == b]
    if segment_id is not None:
        df = df[df["segment_id"] == segment_id]
    if country:
        df = df[df["Geography"] == country]
    if min_products:
        df = df[df["NumOfProducts"] >= min_products]
    if active is not None:
        df = df[df["IsActiveMember"] == int(active)]
    if exited is not None:
        df = df[df["Exited"] == int(exited)]
    if search and search.strip():
        q = search.strip().lower()
        df = df[df["Surname"].fillna("").str.lower().str.contains(q, regex=False)
                | df["customer_id"].astype(str).str.lower().str.contains(q, regex=False)]
    key = {"value_at_risk": "rar", "chance": "p", "value": "customer_value"}[sort]
    df = df.sort_values(key, ascending=False, kind="stable")
    total = int(len(df))
    return {"total": total, "items": [item(r) for r in df.iloc[offset:offset + limit].itertuples(index=False)]}


@router.get("/customers/points")
def customer_points():
    """Compact arrays for every customer (galaxy-style plots): chance, value, band index, in people() order."""
    df = artifacts.people()
    return {"customer_id": df["customer_id"].tolist(), "p": df["p"].round(4).tolist(),
            "value": df["customer_value"].round(0).tolist(), "band": df["band"].tolist()}


def _offers(r, cfg: dict) -> list[dict]:
    """Eligible catalog offers for one customer: cost, estimated new chance of leaving, value kept.

    Same response curve the allocation solver uses: kept = p v a (1 - exp(-cost / tau)), tau = t_g v.
    These effects are assumptions (the project has no uplift data).
    """
    table = artifacts._group_params()
    v, p = float(r["customer_value"]), float(r["p"])
    a, t, eng = cfg["allocation"]["response_curves"]["a"], cfg["allocation"]["response_curves"]["t"], "low"
    if table is not None and not pd.isna(r.get("segment_id")):
        row = table[(table["segment_id"] == int(r["segment_id"])) & (table["value_tier"] == r["value_tier"])]
        if len(row):
            a, t, eng = float(row.iloc[0]["a_g"]), float(row.iloc[0]["t_g"]), row.iloc[0]["engagement_class"]
    tau, cap = max(t * v, 1e-6), float(cfg["budget"]["max_spend_per_customer"])
    out = []
    for code, o in cfg["allocation"]["offers"].items():
        cost = o["flat"] + o["cost_frac"] * v
        ok = (r.get("value_tier") in o["eligible"]["tiers"] if table is not None else True)             and (eng in o["eligible"]["engagement"]) and cost <= cap
        if not ok:
            continue
        kept = p * v * a * (1 - math.exp(-cost / tau))
        out.append({"offer": code, "cost": round(cost, 2), "new_p_churn": round(p * (1 - a * (1 - math.exp(-cost / tau))), 4),
                    "value_kept": round(kept, 2), "net_value_kept": round(kept - cost, 2)})
    out.sort(key=lambda o: -o["net_value_kept"])
    for k, o in enumerate(out):
        o["best"] = k == 0 and o["net_value_kept"] > 0
    return out


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: str):
    df = artifacts.people()
    row = df[df["customer_id"] == customer_id]
    if row.empty:
        raise HTTPException(404, f"Unknown customer {customer_id}")
    r = row.iloc[0]
    seg = None
    if isinstance(r.segment_name, str):
        seg = {"segment_id": int(r.segment_id), "segment_name": r.segment_name,
               "value_tier": r.value_tier}
    allocation = None
    if isinstance(r.offer, str):
        allocation = {"offer": r.offer, "spend": float(r.spend),
                      "expected_revenue_saved": float(r.expected_revenue_saved),
                      "reason": r.reason}
    drivers = [{"feature": d["feature"], "label": d["label"], "value": d.get("value"),
                "contribution": float(d["contribution"])} for d in list(r.top_drivers)]
    return {
        **item(r),
        "snapshot_date": str(r.snapshot_date),
        "p_churn_raw": round(float(r.p_churn_raw), 4),
        "segment": seg,
        "top_drivers": drivers,
        "allocation": allocation,
        "offers": _offers(r, load_config()),
    }


@router.get("/customers/{customer_id}/report.pdf")
def customer_pdf(customer_id: str):
    df = artifacts.joined()
    row = df[df["customer_id"] == customer_id]
    if row.empty:
        raise HTTPException(404, f"Unknown customer {customer_id}")
    r = row.iloc[0]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Churn risk report - {customer_id}", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Snapshot: {r.snapshot_date}", ln=1)
    pdf.cell(0, 8, f"P(churn) calibrated: {r.p_churn_calibrated:.2f} "
                   f"(raw {r.p_churn_raw:.2f}) - band {r.risk_band}", ln=1)
    pdf.cell(0, 8, f"Revenue at risk: {r.revenue_at_risk:,.2f}", ln=1)
    if isinstance(r.segment_name, str):
        pdf.cell(0, 8, f"Segment: {r.segment_name} ({r.value_tier} value)", ln=1)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Top churn drivers", ln=1)
    pdf.set_font("Helvetica", "", 11)
    for d in list(r.top_drivers):
        pdf.cell(0, 7, f"  - {d['label']}: {DRIVER_FMT.format(d['contribution'], 0)}", ln=1)
    if isinstance(r.offer, str):
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Recommended action", ln=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, f"Offer: {r.offer} (spend {r.spend:,.2f}, "
                             f"expected saved {r.expected_revenue_saved:,.2f})\n{r.reason}")

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f"inline; filename={customer_id}_report.pdf"})
