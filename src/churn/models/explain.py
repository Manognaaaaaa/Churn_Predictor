"""SHAP explanations: top-k drivers per customer."""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap


def _pretty(name: str) -> str:
    return (name.replace("Geography_", "").replace("Gender_", "gender: ")
                .replace("_", " ").strip().capitalize())


def _num(v) -> float | None:
    return None if v is None or v != v else float(v)


def top_drivers(x: pd.DataFrame, model, feature_names: list[str], k: int = 5,
                raw_values: pd.DataFrame | None = None) -> list[list[dict]]:
    """Return a list (per row) of {feature, label, contribution[, value]} dicts, top-k by |SHAP|.

    raw_values: optional unscaled feature values (same row order); adds a `value` to each driver."""
    try:
        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(x)
    except Exception:
        explainer = shap.LinearExplainer(model, x)
        values = explainer.shap_values(x)

    if isinstance(values, list):          # older shap: per-class lists
        values = values[-1]
    values = np.asarray(values)
    if values.ndim == 3:                  # (n, features, classes) -> churn class
        values = values[:, :, -1]

    out = []
    for i in range(len(x)):
        row = values[i]
        order = np.argsort(-np.abs(row))[:k]
        out.append([{"feature": feature_names[j], "label": _pretty(feature_names[j]),
                     "contribution": float(row[j]),
                     **({"value": _num(raw_values.iloc[i][feature_names[j]])} if raw_values is not None else {})}
                    for j in order])
    return out
