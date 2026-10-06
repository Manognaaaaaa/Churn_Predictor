"""Step 5: GMM segments (BIC-chosen k) crossed with value tiers."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


def choose_gmm(x: pd.DataFrame, k_range: tuple[int, int], seed: int) -> tuple[GaussianMixture, pd.DataFrame]:
    ks = list(range(k_range[0], k_range[1] + 1))
    bics = []
    for k in ks:
        g = GaussianMixture(n_components=k, random_state=seed, n_init=3).fit(x)
        bics.append({"k": k, "bic": float(g.bic(x))})
    best_k = min(bics, key=lambda r: r["bic"])["k"]
    best = GaussianMixture(n_components=best_k, random_state=seed, n_init=3).fit(x)
    return best, pd.DataFrame(bics)


def name_segments(gmm: GaussianMixture, x: pd.DataFrame, labels: np.ndarray) -> dict[int, str]:
    """Name each segment by its most distinctive standardized trait."""
    names = {}
    overall, std = x.mean(), x.std() + 1e-9
    for s in range(gmm.n_components):
        gap = (x[labels == s].mean() - overall) / std
        top = gap.abs().idxmax()
        arrow = "+" if gap[top] > 0 else "-"
        names[s] = f"{top} ({arrow}{gap[top]:.1f} sd)"
    return names


def build_segments(scores: pd.DataFrame, features: pd.DataFrame,
                   feature_cols: list[str], cfg: dict) -> tuple[pd.DataFrame, dict]:
    """features: data/processed/features.parquet (has customer_value_raw + model features)."""
    seed = cfg["seed"]
    merged = features.set_index("customer_id").loc[scores["customer_id"]]
    num = merged[feature_cols].select_dtypes(include=[np.number])
    if "customer_value_raw" in merged.columns:
        num = num.assign(customer_value=merged["customer_value_raw"].to_numpy())

    scaler = StandardScaler().fit(num)
    xs = pd.DataFrame(scaler.transform(num), columns=num.columns)
    gmm, bics = choose_gmm(xs, tuple(cfg["segmentation"]["gmm_k_range"]), seed)
    labels = gmm.predict(xs)
    names = name_segments(gmm, num, labels)
    # de-duplicate names (two clusters can share a dominant trait)
    seen = {}
    for s in list(names):
        base = names[s]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            names[s] = f"{base} #{s}"

    tiers = pd.qcut(merged["customer_value_raw"], q=3,
                    labels=cfg["segmentation"]["value_tiers"]).astype(str)
    out = pd.DataFrame({
        "customer_id": scores["customer_id"].to_numpy(),
        "segment_id": labels,
        "segment_name": [names[s] for s in labels],
        "value_tier": tiers.to_numpy(),
    })
    return out, {"bic_table": bics.to_dict("records"), "chosen_k": gmm.n_components,
                 "segment_names": {str(k): v for k, v in names.items()}}
