"""Observed leaving rates in the data (for the plain sentences next to each driver)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from api import artifacts

router = APIRouter(tags=["stats"])


def _table(df: pd.DataFrame, key) -> list[dict]:
    g = df.groupby(key, observed=True)["Exited"].agg(["size", "sum", "mean"])
    return [{"key": str(k), "customers": int(r["size"]), "left": int(r["sum"]), "rate": float(r["mean"])}
            for k, r in g.iterrows()]


@router.get("/stats/products")
def products():
    return {"by_products": [{"num_products": int(t["key"]), **{k: t[k] for k in ("customers", "left", "rate")}}
                            for t in _table(artifacts.people(), "NumOfProducts")]}


@router.get("/stats/rates")
def rates():
    df = artifacts.people()
    cut = lambda col, bins, labels: pd.cut(df[col], bins, labels=labels, right=False)
    return {
        "geography": _table(df, "Geography"),
        "active": _table(df, "IsActiveMember"),
        "age_band": _table(df.assign(b=cut("Age", [0, 30, 40, 50, 60, 200], ["under 30", "30s", "40s", "50s", "60 and over"])), "b"),
        "tenure_band": _table(df.assign(b=cut("Tenure", [0, 3, 6, 9, 100], ["0-2 years", "3-5 years", "6-8 years", "9 years or more"])), "b"),
        "credit_band": _table(df.assign(b=cut("CreditScore", [0, 500, 600, 700, 1000], ["under 500", "500-599", "600-699", "700 or more"])), "b"),
    }
