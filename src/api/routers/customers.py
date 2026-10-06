"""Customer endpoints: list, detail, one-page PDF report."""
from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from fpdf import FPDF

from api import artifacts

router = APIRouter(tags=["customers"])

DRIVER_FMT = "p={:.2f} ({:+.2f})"


@router.get("/customers")
def list_customers(
    risk_band: str | None = Query(None, pattern="^(green|amber|red)$"),
    segment_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    df = artifacts.joined()
    if risk_band:
        df = df[df["risk_band"] == risk_band]
    if segment_id is not None:
        df = df[df["segment_id"] == segment_id]
    df = df.sort_values("revenue_at_risk", ascending=False)
    total = int(len(df))
    page = df.iloc[offset:offset + limit]
    items = [{
        "customer_id": r.customer_id,
        "p_churn_calibrated": round(float(r.p_churn_calibrated), 4),
        "risk_band": r.risk_band,
        "revenue_at_risk": round(float(r.revenue_at_risk), 2),
        "segment_name": r.segment_name if isinstance(r.segment_name, str) else None,
        "value_tier": r.value_tier if isinstance(r.value_tier, str) else None,
    } for r in page.itertuples()]
    return {"total": total, "items": items}


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: str):
    df = artifacts.joined()
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
    return {
        "customer_id": customer_id,
        "snapshot_date": str(r.snapshot_date),
        "p_churn_raw": round(float(r.p_churn_raw), 4),
        "p_churn_calibrated": round(float(r.p_churn_calibrated), 4),
        "risk_band": r.risk_band,
        "revenue_at_risk": round(float(r.revenue_at_risk), 2),
        "segment": seg,
        "top_drivers": list(r.top_drivers),
        "allocation": allocation,
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
