"""Raw ingestion + schema checks (step 2). Reads only what configs/config.yaml allows."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from churn.config import ROOT, dataset_cfg


def load_raw(cfg: dict) -> pd.DataFrame:
    ds = dataset_cfg(cfg)
    path = ROOT / ds["path"]
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    elif path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported raw file type: {path.suffix}")
    return df


def schema_checks(df: pd.DataFrame, cfg: dict) -> dict:
    """Contract checks; raises on hard failures, returns a summary dict."""
    ds = dataset_cfg(cfg)
    required = [ds["id_col"], ds["label_col"], *ds["numeric"], *ds["categorical"]]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    problems = []
    if df[ds["id_col"]].duplicated().any():
        problems.append(f"duplicate ids in {ds['id_col']}")
    bad_labels = set(df[ds["label_col"]].dropna().unique()) - {0, 1, "0", "1", "Yes", "No", True, False}
    if bad_labels:
        problems.append(f"unexpected label values: {bad_labels}")
    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        problems.append(f"all-null columns: {empty_cols}")
    if problems:
        raise ValueError("; ".join(problems))

    return {
        "n_rows": int(len(df)),
        "n_unique_ids": int(df[ds["id_col"]].nunique()),
        "churn_rate": float(pd.to_numeric(df[ds["label_col"]], errors="coerce").mean()),
        "n_null_cells": int(df.isna().sum().sum()),
        "columns": list(df.columns),
    }


def standardize(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Drop configured junk columns, coerce label/value to numeric, keep canonical names."""
    ds = dataset_cfg(cfg)
    out = df.drop(columns=[c for c in ds["drop_cols"] if c in df.columns]).copy()
    out[ds["label_col"]] = pd.to_numeric(out[ds["label_col"]], errors="coerce")
    out = out.dropna(subset=[ds["label_col"]])
    out[ds["label_col"]] = out[ds["label_col"]].astype(int)
    if ds["value_col"] in out.columns:
        out[ds["value_col"]] = pd.to_numeric(out[ds["value_col"]], errors="coerce")
    # canonical names used by the rest of the pipeline
    out = out.rename(columns={ds["id_col"]: "customer_id", ds["label_col"]: "churned",
                              ds["value_col"]: "customer_value"})
    out["customer_id"] = out["customer_id"].astype(str)
    return out
