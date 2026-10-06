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
def _allocations() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "allocations.parquet")


@lru_cache(maxsize=1)
def _forecast() -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "forecast.parquet")


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


def reset_cache() -> None:
    for fn in (_scores, _segments, _allocations, _forecast, _metrics, _risk_summary):
        fn.cache_clear()


def joined() -> pd.DataFrame:
    """scores x segments x allocations, one row per customer."""
    df = _scores().merge(_segments(), on="customer_id", how="left")
    alloc = _allocations()[["customer_id", "offer", "spend", "expected_revenue_saved", "reason"]]
    return df.merge(alloc, on="customer_id", how="left")
