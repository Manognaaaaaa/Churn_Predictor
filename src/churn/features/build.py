"""Step 3: splits, cleaning+encoding, PCA, imbalance strategy (leakage-safe).

Static-mode adaptation: no timestamps exist in the dataset, so the README's
time-based split + expanding-window CV become a stratified split + stratified
k-fold CV on the training rows (same fold count, documented deviation).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

from churn.config import ROOT, dataset_cfg, ensure_dirs, load_config
from churn.data.clean import CleaningPipeline, derive_features

TARGET = "churned"


def make_splits(df: pd.DataFrame, cfg: dict) -> tuple[pd.Index, pd.Index, pd.Index]:
    fr = cfg["windows"]["split_fractions"]
    seed = cfg["seed"]
    idx = df.index
    y = df[TARGET]
    train_idx, rest = train_test_split(idx, train_size=fr["train"], random_state=seed, stratify=y)
    valid_frac = fr["valid"] / (fr["valid"] + fr["test"])
    y_rest = y.loc[rest]
    valid_idx, test_idx = train_test_split(rest, train_size=valid_frac, random_state=seed,
                                           stratify=y_rest)
    return train_idx, valid_idx, test_idx


class FeatureBuilder:
    """Fit cleaning + one-hot + scaler on train rows only; apply everywhere."""

    def __init__(self, cfg: dict):
        ds = dataset_cfg(cfg)
        self.ds = ds
        # value_col was renamed to customer_value by ingest.standardize
        self.numeric_cols = ["customer_value" if c == ds["value_col"] else c
                             for c in ds["numeric"]]
        self.cleaner = CleaningPipeline(numeric=self.numeric_cols, categorical=ds["categorical"])
        self.ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self.scaler = StandardScaler()
        self.feature_names_: list[str] = []

    def fit(self, df: pd.DataFrame) -> "FeatureBuilder":
        clean = self.cleaner.fit_transform(df)
        clean = derive_features(clean)
        cat = self.ds["categorical"]
        num_all = [c for c in clean.columns if c not in (*cat, "customer_id", "churned",
                                                         "snapshot_date")]
        self.num_cols_ = [c for c in num_all if pd.api.types.is_numeric_dtype(clean[c])]
        self.ohe.fit(clean[cat])
        cat_names = list(self.ohe.get_feature_names_out(cat))
        x = np.hstack([clean[self.num_cols_].to_numpy(float),
                       self.ohe.transform(clean[cat])])
        self.scaler.fit(x)
        self.feature_names_ = self.num_cols_ + cat_names
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        clean = derive_features(self.cleaner.transform(df))
        x = np.hstack([clean[self.num_cols_].to_numpy(float),
                       self.ohe.transform(clean[self.ds["categorical"]])])
        x = self.scaler.transform(x)
        return pd.DataFrame(x, columns=self.feature_names_, index=df.index)

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(df).transform(df)


def fit_pca(x_train: pd.DataFrame, cfg: dict, var_keep: float = 0.95) -> dict:
    pca = PCA(n_components=var_keep, random_state=cfg["seed"]).fit(x_train)
    loadings = pd.DataFrame(pca.components_.T, index=x_train.columns,
                            columns=[f"PC{i+1}" for i in range(pca.n_components_)])
    explained = pd.Series(pca.explained_variance_ratio_,
                          index=[f"PC{i+1}" for i in range(pca.n_components_)])
    return {"pca": pca, "loadings": loadings, "explained": explained}


def compare_imbalance_strategies(x_train: pd.DataFrame, y_train: pd.Series,
                                 cfg: dict) -> dict:
    """class_weight vs SMOTE vs undersampling via stratified CV PR-AUC."""
    folds = cfg["windows"]["cv_folds"]
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=cfg["seed"])
    X, y = x_train.to_numpy(), y_train.to_numpy()

    def cv_score(resample):
        scores = []
        for tr_i, va_i in skf.split(X, y):
            if resample == "class_weight":
                model = LogisticRegression(max_iter=2000, class_weight="balanced")
                xtr, ytr = X[tr_i], y[tr_i]
            elif resample == "smote":
                model = LogisticRegression(max_iter=2000)
                xtr, ytr = SMOTE(random_state=cfg["seed"]).fit_resample(X[tr_i], y[tr_i])
            elif resample == "undersample":
                model = LogisticRegression(max_iter=2000)
                xtr, ytr = RandomUnderSampler(random_state=cfg["seed"]).fit_resample(X[tr_i], y[tr_i])
            else:  # none
                model = LogisticRegression(max_iter=2000)
                xtr, ytr = X[tr_i], y[tr_i]
            model.fit(xtr, ytr)
            scores.append(average_precision_score(y[va_i], model.predict_proba(X[va_i])[:, 1]))
        return float(np.mean(scores)), scores

    out = {}
    for strat in ["none", "class_weight", "smote", "undersample"]:
        mean, scores = cv_score(strat)
        out[strat] = {"cv_pr_auc": round(mean, 4), "fold_scores": [round(s, 4) for s in scores]}
    best = max(out, key=lambda k: out[k]["cv_pr_auc"])
    return {"per_strategy": out, "chosen": best}
