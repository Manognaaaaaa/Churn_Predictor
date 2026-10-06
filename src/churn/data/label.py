"""Churn labeling (step 2).

The chosen dataset (Churn_Modelling) already carries an observed churn label and has
no timestamps, so static mode simply validates and passes the label through.
`monthly_snapshot_labels` implements the README's temporal scheme for future datasets
that have per-month activity: churn = no activity within prediction_horizon_months.
"""
from __future__ import annotations

import pandas as pd


def static_labels(df: pd.DataFrame, label_col: str = "churned") -> pd.DataFrame:
    """Static dataset: one snapshot per customer, label as given."""
    out = df.copy()
    out["snapshot_date"] = pd.Timestamp.today().normalize()
    if not out[label_col].isin([0, 1]).all():
        raise ValueError("static_labels expects a binary churn column")
    return out


def monthly_snapshot_labels(
    activity: pd.DataFrame,
    customer_col: str,
    month_col: str,
    horizon_months: int = 3,
) -> pd.DataFrame:
    """Temporal datasets: label each customer-month by future inactivity.

    activity: one row per (customer, month) with any activity.
    Returns one row per customer-month with `churned` = 1 if the customer has no
    activity in the `horizon_months` months that follow. The final `horizon_months`
    of the calendar are dropped (label not yet observable).
    """
    a = activity[[customer_col, month_col]].drop_duplicates()
    months = sorted(a[month_col].unique())
    last_labelable = months[-(horizon_months + 1)]
    a = a[a[month_col] <= last_labelable]

    sets = a.groupby(month_col)[customer_col].apply(set).to_dict()
    rows = []
    for m in months:
        if m > last_labelable:
            continue
        future = set()
        for k in range(1, horizon_months + 1):
            future |= sets.get(m + k, set())
        churned = set(sets[m]) - future
        rows.append(pd.DataFrame({customer_col: sorted(churned), month_col: m, "churned": 1}))
        stayed = set(sets[m]) & future
        rows.append(pd.DataFrame({customer_col: sorted(stayed), month_col: m, "churned": 0}))
    out = pd.concat(rows, ignore_index=True).rename(columns={month_col: "snapshot_date"})
    return out
