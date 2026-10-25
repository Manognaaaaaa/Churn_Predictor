"""Artifact loading for the API. Reads parquet files only - no ML logic here."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from churn.config import ROOT, load_config


def artifacts_dir() -> Path:
    real = ROOT / load_config()["paths"]["artifacts"]
    if (real / "scores.parquet").exists():
        return real
    mock = real / "mock"
    if (mock / "scores.parquet").exists():
        return mock
    raise FileNotFoundError("No artifacts found - run the pipeline or `make mocks` first")


@lru_cache(maxsize=1)
def _scores() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "scores.parquet")


@lru_cache(maxsize=1)
def _segments() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "segments.parquet")


@lru_cache(maxsize=1)
def _group_params() -> pd.DataFrame | None:
    path = artifacts_dir() / "group_params.parquet"
    return pd.read_parquet(path) if path.exists() else None


@lru_cache(maxsize=1)
def _allocations() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "allocations.parquet")


@lru_cache(maxsize=1)
def _forecast() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "forecast.parquet")


@lru_cache(maxsize=1)
def _forecast_meta() -> dict:
    path = artifacts_dir() / "forecast_meta.json"
    return json.loads(path.read_text()) if path.exists() else {}


@lru_cache(maxsize=1)
def _metrics() -> dict:
    path = artifacts_dir() / "metrics.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"models": [], "calibration_curve": []}


@lru_cache(maxsize=1)
def _risk_summary() -> dict:
    path = artifacts_dir() / "risk_summary.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


@lru_cache(maxsize=1)
def _customers() -> pd.DataFrame:
    """Raw customer columns (Surname, Geography, ...) written by the pipeline."""
    return pd.read_parquet(artifacts_dir() / "customers.parquet")


def reset_cache() -> None:
    for fn in (_scores, _segments, _group_params, _allocations, _forecast, _forecast_meta, _metrics,
               _risk_summary, _customers, people):
        fn.cache_clear()


def joined() -> pd.DataFrame:
    """scores x segments x allocations, one row per customer."""
    df = _scores().merge(_segments(), on="customer_id", how="left")
    alloc = _allocations()[["customer_id", "offer", "spend", "expected_revenue_saved", "reason"]]
    return df.merge(alloc, on="customer_id", how="left")


@lru_cache(maxsize=1)
def people() -> pd.DataFrame:
    """One row per customer: raw fields, out-of-fold score, segment and allocation (sorted by value at risk)."""
    sc = _scores()
    df = sc.merge(_customers(), on="customer_id", how="left").merge(_segments(), on="customer_id", how="left")
    alloc = _allocations()[["customer_id", "offer", "spend", "expected_revenue_saved", "reason"]]
    df = df.merge(alloc, on="customer_id", how="left")
    if "customer_value" not in df:
        df["customer_value"] = df["EstimatedSalary"]
    df = df.rename(columns={"p_churn_calibrated": "p", "risk_band": "band", "revenue_at_risk": "rar"})
    return df.sort_values("rar", ascending=False).reset_index(drop=True)
