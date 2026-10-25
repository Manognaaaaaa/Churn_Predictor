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


PDF_FEATURES = {
    "NumOfProducts": "Number of bank products", "IsActiveMember": "Active member", "Age": "Age",
    "Tenure": "Years with the bank", "CreditScore": "Credit score", "Balance": "Account balance",
    "zero_balance": "Empty account", "HasCrCard": "Has a credit card", "customer_value": "Yearly value",
    "balance_value_ratio": "Balance compared with yearly value",
}
PDF_OFFERS = {"value_discount": "Better savings rate", "fee_waiver": "Waive account fees",
              "service_call": "Call from relationship manager", "retention_bonus": "Loyalty bonus",
              "loyalty_email": "Personal email from the bank"}


def _plain_feature(name: str) -> str:
    if name in PDF_FEATURES:
        return PDF_FEATURES[name]
    if name.startswith("Geography_"):
        return f"Based in {name[10:]}"
    if name.startswith("Gender_"):
        return f"{name[7:]} customer"
    return name.replace("_", " ").capitalize()


def _pdf_text(s: str) -> str:
    """The built-in PDF fonts are latin-1 only."""
    return s.encode("latin-1", "replace").decode("latin-1")


@router.get("/customers/{customer_id}/report.pdf")
def customer_pdf(customer_id: str):
    df = artifacts.people()
    row = df[df["customer_id"] == customer_id]
    if row.empty:
        raise HTTPException(404, f"Unknown customer {customer_id}")
    r = row.iloc[0]
    d = customer_detail(customer_id)
    name = f"{'Mr ' if r.get('Gender') == 'Male' else 'Ms ' if r.get('Gender') == 'Female' else ''}{r.get('Surname') or 'Customer'}"
    p = float(r.p)
    chance = "99%+" if p >= 0.99 else f"{round(p * 100)}%"
    word = {"red": "High risk", "amber": "Medium risk", "green": "Low risk"}[r.band]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 11, _pdf_text(f"Customer report: {name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Customer ID {customer_id}  |  {r.get('Geography', '')}  |  Age {int(r['Age']) if pd.notna(r.get('Age')) else '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.cell(0, 8, f"{word}: {chance} chance of leaving", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Yearly value (estimated salary): {r.customer_value:,.0f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Yearly value at risk: {r.rar:,.0f}", new_x="LMARGIN", new_y="NEXT")
    if pd.notna(r.get("Exited")) and int(r["Exited"]) == 1:
        pdf.cell(0, 8, "This customer left the bank in the data.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Why the model flags this customer", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for x in d["top_drivers"]:
        pdf.cell(0, 7, _pdf_text(f"  - {_plain_feature(x['feature'])}: {'raises' if x['contribution'] > 0 else 'lowers'} the risk"), new_x="LMARGIN", new_y="NEXT")
    if d["offers"]:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Suggested offers (estimated effect)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for o in d["offers"]:
            tag = "  (best value)" if o["best"] else ""
            pdf.multi_cell(0, 7, _pdf_text(f"  - {PDF_OFFERS.get(o['offer'], o['offer'])}{tag}: costs {o['cost']:,.0f}, "
                                           f"chance of leaving falls to {round(o['new_p_churn'] * 100)}%, keeps about {o['value_kept']:,.0f}"),
                           new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, "Offer effects are estimates from the allocation model; the project has no data from real offers.", new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f"inline; filename={customer_id}_report.pdf"})
