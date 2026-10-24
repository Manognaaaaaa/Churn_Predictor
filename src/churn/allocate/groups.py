"""Group (segment x value tier) response-curve parameters a_g, t_g.

Rule (config `allocation.response_curves`): engaged segments respond more (higher a),
high-value tiers need bigger offers (higher t). Assumptions, not measured uplift.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def segment_engagement(profile: pd.DataFrame) -> pd.Series:
    """Engagement index per segment: mean of across-segment z-scores of each feature mean.

    profile: rows = segments, columns = engagement features (segment means).
    """
    z = (profile - profile.mean()) / profile.std(ddof=0).replace(0.0, 1.0)
    return z.mean(axis=1)


def _tier_multipliers(tiers: list[str], step: float) -> dict[str, float]:
    """step ** k with k centred on the middle tier (low -> -1, mid -> 0, high -> +1)."""
    mid = (len(tiers) - 1) / 2.0
    return {t: float(step ** (i - mid)) for i, t in enumerate(tiers)}


def build_group_table(seg: pd.DataFrame, feats: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per (segment_id, value_tier) with a_g and t_g.

    seg: customer_id, segment_id, value_tier. feats: features.parquet (needs split + the
    engagement features). Segment profiles use the train split only.
    """
    rc = dict(cfg["allocation"]["response_curves"])
    rc["engagement_split"] = cfg["allocation"]["engagement_split"]
    tiers = list(cfg["segmentation"]["value_tiers"])
    train = feats[feats["split"] == "train"].copy()
    train["customer_id"] = train["customer_id"].astype(str)
    s = seg.assign(customer_id=seg["customer_id"].astype(str))
    prof = (train.merge(s[["customer_id", "segment_id"]], on="customer_id")
            .groupby("segment_id")[rc["engagement_features"]].mean())
    e = segment_engagement(prof).reindex(sorted(seg["segment_id"].unique())).fillna(0.0)
    m_seg = np.clip(1 + rc["a_segment_slope"] * e, *rc["a_segment_bounds"])
    n_seg = np.clip(1 + rc["t_segment_slope"] * e, *rc["t_segment_bounds"])
    m_tier = _tier_multipliers(tiers, rc["a_tier_step"])
    n_tier = _tier_multipliers(tiers, rc["t_tier_step"])
    rows = []
    for sid in e.index:
        for tier in tiers:
            rows.append({"segment_id": int(sid), "value_tier": tier,
                         "engagement": float(e[sid]),
                         "engagement_class": "high" if e[sid] > rc.get("engagement_split", 0.0)
                         else "low",
                         "m_seg": float(m_seg[sid]), "m_tier": m_tier[tier],
                         "n_seg": float(n_seg[sid]), "n_tier": n_tier[tier],
                         "a_g": float(rc["a"] * m_seg[sid] * m_tier[tier]),
                         "t_g": float(rc["t"] * n_seg[sid] * n_tier[tier])})
    return pd.DataFrame(rows)


def customer_attr(seg_ids: np.ndarray, tiers: np.ndarray, table: pd.DataFrame,
                  col: str) -> np.ndarray:
    """Look up one group-table column (e.g. engagement_class) for every customer."""
    idx = pd.MultiIndex.from_arrays([np.asarray(seg_ids), np.asarray(tiers)])
    return table.set_index(["segment_id", "value_tier"])[col].reindex(idx).to_numpy()


def customer_params(seg_ids: np.ndarray, tiers: np.ndarray, table: pd.DataFrame,
                    v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-customer (a_i, tau_i = t_g * v_i) looked up from the group table."""
    key = table.set_index(["segment_id", "value_tier"])
    idx = pd.MultiIndex.from_arrays([np.asarray(seg_ids), np.asarray(tiers)])
    a = key["a_g"].reindex(idx).to_numpy(float)
    t = key["t_g"].reindex(idx).to_numpy(float)
    return a, np.maximum(t * np.asarray(v, float), 1e-6)


def global_params(n: int, v: np.ndarray, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """One global (a, t) for every customer: the `global_kkt` baseline."""
    rc = cfg["allocation"]["response_curves"]
    return np.full(n, float(rc["a"])), np.maximum(rc["t"] * np.asarray(v, float), 1e-6)
