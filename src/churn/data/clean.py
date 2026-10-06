"""Cleaning (steps 2-3): imputation, outlier capping, Yeo-Johnson.

Leakage rule (README): every fitted transform is fit on the training split only.
`CleaningPipeline` is constructed in the features step with the train indices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import PowerTransformer


class CleaningPipeline:
    """Column-wise cleaning, fitted on train rows only.

    numeric: median impute -> winsorize at fitted 1st/99th pct -> Yeo-Johnson
    categorical: mode impute (kept as strings; encoding happens in features)
    """

    def __init__(self, numeric: list[str], categorical: list[str], clip_pct: float = 0.01):
        self.numeric = list(numeric)
        self.categorical = list(categorical)
        self.clip_pct = clip_pct
        self.medians_: dict[str, float] = {}
        self.modes_: dict[str, str] = {}
        self.clip_lo_: dict[str, float] = {}
        self.clip_hi_: dict[str, float] = {}
        self._pt: PowerTransformer | None = None

    def fit(self, df: pd.DataFrame) -> "CleaningPipeline":
        num = df[self.numeric].astype(float)
        self.medians_ = num.median().to_dict()
        filled = num.fillna(pd.Series(self.medians_))
        lo = filled.quantile(self.clip_pct)
        hi = filled.quantile(1 - self.clip_pct)
        self.clip_lo_ = lo.to_dict()
        self.clip_hi_ = hi.to_dict()
        clipped = filled.clip(lower=lo, upper=hi, axis=1)
        # constant columns break PowerTransformer; keep them raw via tiny jitter
        safe = clipped.loc[:, clipped.std() > 1e-12]
        self._pt = PowerTransformer(method="yeo-johnson", standardize=False)
        self._pt.fit(safe)
        self._pt_cols = list(safe.columns)
        for c in self.categorical:
            self.modes_[c] = df[c].mode(dropna=True).iloc[0]
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        num = out[self.numeric].astype(float)
        num = num.fillna(pd.Series(self.medians_))
        num = num.clip(lower=pd.Series(self.clip_lo_), upper=pd.Series(self.clip_hi_), axis=1)
        out[self.numeric] = num
        if self._pt is not None and len(self._pt_cols):
            out[self._pt_cols] = self._pt.transform(out[self._pt_cols])
        for c in self.categorical:
            out[c] = out[c].fillna(self.modes_[c]).astype(str)
        return out

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(df).transform(df)


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """Static derived features shared by all models (no fitting involved)."""
    out = df.copy()
    if {"Balance", "customer_value"} <= set(out.columns):
        out["balance_value_ratio"] = out["Balance"] / (out["customer_value"].abs() + 1.0)
        out["zero_balance"] = (out["Balance"] <= 0).astype(int)
    return out
