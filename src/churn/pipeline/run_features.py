"""Step 3 entrypoint: `make features`."""
from __future__ import annotations

import joblib
import pandas as pd

from churn.config import ROOT, ensure_dirs, load_config
from churn.features.build import FeatureBuilder, compare_imbalance_strategies, fit_pca, make_splits


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    processed = ROOT / cfg["paths"]["processed"]
    artifacts = ROOT / cfg["paths"]["artifacts"]

    df = pd.read_parquet(processed / "labeled.parquet")
    train_idx, valid_idx, test_idx = make_splits(df, cfg)

    fb = FeatureBuilder(cfg)
    x_train = fb.fit_transform(df.loc[train_idx])
    x_valid = fb.transform(df.loc[valid_idx])
    x_test = fb.transform(df.loc[test_idx])

    pca_art = fit_pca(x_train, cfg)
    joblib.dump({"pca": pca_art["pca"],
                 "loadings": pca_art["loadings"],
                 "explained": pca_art["explained"]}, artifacts / "pca.joblib")

    imb = compare_imbalance_strategies(x_train, df.loc[train_idx, "churned"], cfg)
    (artifacts / "imbalance.json").write_text(pd.Series(imb).to_json(indent=2))

    joblib.dump(fb, artifacts / "feature_builder.joblib")
    splits = {
        "train": df.loc[train_idx, "customer_id"].tolist(),
        "valid": df.loc[valid_idx, "customer_id"].tolist(),
        "test": df.loc[test_idx, "customer_id"].tolist(),
    }
    (artifacts / "splits.json").write_text(pd.Series(splits).to_json(indent=2))

    # single feature matrix with split column for downstream steps
    frames = []
    for name, idx in [("train", train_idx), ("valid", valid_idx), ("test", test_idx)]:
        part = df.loc[idx, ["customer_id", "churned", "snapshot_date"]].copy()
        part["split"] = name
        frames.append(part)
    meta = pd.concat(frames, ignore_index=False)

    x_all = pd.concat([x_train, x_valid, x_test])
    out = pd.concat([meta, x_all.reset_index(drop=True)], axis=1)
    out.to_parquet(processed / "features.parquet", index=False)

    print(f"features.parquet: {len(out)} rows x {len(fb.feature_names_)} features")
    print(f"pca components kept: {pca_art['pca'].n_components_} "
          f"({pca_art['explained'].sum():.1%} variance)")
    print(f"imbalance strategy chosen: {imb['chosen']} "
          f"(cv PR-AUC {imb['per_strategy'][imb['chosen']]['cv_pr_auc']})")


if __name__ == "__main__":
    main()
