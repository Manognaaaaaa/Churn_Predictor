"""Shared JSON shape for a customer row (list, home rows and detail all use it)."""
from __future__ import annotations

import pandas as pd


def _s(v) -> str | None:
    return v if isinstance(v, str) else None


def item(r) -> dict:
    """r: a row (namedtuple or Series) of artifacts.people()."""
    g = r._asdict() if hasattr(r, "_asdict") else r.to_dict()
    return {
        "customer_id": g["customer_id"],
        "surname": _s(g.get("Surname")), "gender": _s(g.get("Gender")),
        "age": None if pd.isna(g.get("Age")) else int(g["Age"]),
        "geography": _s(g.get("Geography")),
        "tenure": None if pd.isna(g.get("Tenure")) else int(g["Tenure"]),
        "balance": None if pd.isna(g.get("Balance")) else round(float(g["Balance"]), 2),
        "num_products": None if pd.isna(g.get("NumOfProducts")) else int(g["NumOfProducts"]),
        "credit_score": None if pd.isna(g.get("CreditScore")) else int(g["CreditScore"]),
        "active": None if pd.isna(g.get("IsActiveMember")) else int(g["IsActiveMember"]),
        "estimated_salary": None if pd.isna(g.get("EstimatedSalary")) else round(float(g["EstimatedSalary"]), 2),
        "exited": None if pd.isna(g.get("Exited")) else int(g["Exited"]),
        "p_churn_calibrated": round(float(g["p"]), 4),
        "risk_band": g["band"],
        "revenue_at_risk": round(float(g["rar"]), 2),
        "segment_name": _s(g.get("segment_name")),
        "value_tier": _s(g.get("value_tier")),
    }
