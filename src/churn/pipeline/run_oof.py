"""Step 4b entrypoint: `make oof` - out-of-fold scores for every customer (fixes in-sample scoring).

Rewrites artifacts/scores.parquet with out-of-fold calibrated probabilities, writes
artifacts/customers.parquet (raw columns for the API) and adds a leakage check to metrics.json.
Run after `make train`; `make train` calls it at the end.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from churn.config import ROOT, load_config
from churn.models import oof
from churn.models.explain import top_drivers
from churn.models.metrics import brier, cost_threshold, ece, pr_auc
from churn.pipeline.run_train import META_COLS, TARGET, _maybe_resample

RAW_COLS = ["Surname", "Gender", "Age", "Geography", "Tenure", "Balance", "NumOfProducts", "CreditScore",
            "HasCrCard", "IsActiveMember", "EstimatedSalary", "Exited"]


def _metrics(y, p, bins) -> dict:
    return {"pr_auc": pr_auc(y, p), "brier": brier(y, p), "ece": ece(y, p, bins)}


def main() -> None:
    cfg = load_config()
    artifacts = ROOT / cfg["paths"]["artifacts"]
    ds = cfg["datasets"][cfg["active_dataset"]]
    feats = pd.read_parquet(ROOT / cfg["paths"]["processed"] / "features.parquet")
    feature_cols = [c for c in feats.columns if c not in META_COLS]
    bundle = joblib.load(artifacts / "model.joblib")
    if bundle["model"] is None:
        raise NotImplementedError("out-of-fold scoring supports sklearn-style models, not the LSTM")
    scores = pd.read_parquet(artifacts / "scores.parquet")
    if "p_churn_insample" in scores:                       # re-run: keep the original in-sample column
        before_p = scores["p_churn_insample"].to_numpy(float)
        before_band = scores["risk_band"].to_numpy()
    else:
        before_p = scores["p_churn_calibrated"].to_numpy(float)
        before_band = scores["risk_band"].to_numpy()
    assert (scores["customer_id"].to_numpy() == feats["customer_id"].to_numpy()).all()

    x, y = feats[feature_cols].to_numpy(float), feats[TARGET].to_numpy(int)
    strategy = json.loads((artifacts / "imbalance.json").read_text())["chosen"]
    p_raw = oof.oof_raw_scores(bundle["model"], x, y, lambda a, b: _maybe_resample(a, b, strategy, cfg["seed"]),
                               cfg["windows"]["cv_folds"] + 1, cfg["seed"])
    calibrator, p_cal = oof.calibrate_oof(p_raw, y, bundle["calibrator_name"])
    rb = cfg["risk_bands"]
    bands = np.where(p_cal <= rb["green_max"], "green", np.where(p_cal <= rb["amber_max"], "amber", "red"))

    raw = pd.read_csv(ROOT / ds["path"]).assign(customer_id=lambda d: d[ds["id_col"]].astype(str))
    raw = raw.set_index("customer_id").loc[feats["customer_id"].astype(str)].reset_index()
    values = oof.raw_feature_values(raw, feature_cols)
    drivers = top_drivers(pd.DataFrame(x, columns=feature_cols), bundle["model"], feature_cols, raw_values=values)

    new = scores.assign(p_churn_insample=before_p, p_churn_raw=p_raw, p_churn_calibrated=p_cal, risk_band=bands,
                        revenue_at_risk=p_cal * scores["customer_value"].to_numpy(float), top_drivers=drivers)
    new.to_parquet(artifacts / "scores.parquet", index=False)

    cust = raw[["customer_id", *RAW_COLS]].rename(columns={"Exited": "Exited"})
    cust["customer_id"] = cust["customer_id"].astype(str)
    cust.to_parquet(artifacts / "customers.parquet", index=False)

    bins = cfg["models"]["calibration"]["ece_bins"]
    split = scores["split"].to_numpy()
    te, tr = split == "test", split == "train"
    # cost-optimal threshold on the validation rows, now with out-of-fold calibrated probabilities
    va = split == "valid"
    tp = cfg["models"]["threshold"]
    thr = cost_threshold(p_cal[va], scores.loc[va, "customer_value"].to_numpy(float),
                         offer_cost_frac=tp["offer_cost_frac"], offer_uplift=tp["offer_uplift"],
                         fn_cost_multiple=cfg["budget"]["fn_cost_multiple"])
    leak = {
        "method": f"{cfg['windows']['cv_folds'] + 1}-fold stratified out-of-fold, calibrator={bundle['calibrator_name']} "
                  "fitted on the out-of-fold raw scores",
        "before": {"distribution": oof.distribution(before_p, before_band),
                   "train_in_sample": _metrics(y[tr], before_p[tr], bins),
                   "test_holdout": _metrics(y[te], before_p[te], bins)},
        "after": {"distribution": oof.distribution(p_cal, bands),
                  "all_oof": _metrics(y, p_cal, bins),
                  "train_rows_oof": _metrics(y[tr], p_cal[tr], bins),
                  "test_rows_oof": _metrics(y[te], p_cal[te], bins)},
    }
    mpath = artifacts / "metrics.json"
    metrics = json.loads(mpath.read_text())
    metrics.update({"leakage_check": leak, "threshold": thr, "oof_calibration": bundle["calibrator_name"],
                    "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    mpath.write_text(json.dumps(metrics, indent=2, default=float))
    (artifacts / "leakage_check.json").write_text(json.dumps(leak, indent=2, default=float))
    bundle["oof_calibrator"] = calibrator
    joblib.dump(bundle, artifacts / "model.joblib")
    print("before", json.dumps(leak["before"]["distribution"]))
    print("after ", json.dumps(leak["after"]["distribution"]))
    print("in-sample train", leak["before"]["train_in_sample"], "| oof all", leak["after"]["all_oof"],
          "| test (held out)", leak["before"]["test_holdout"])


if __name__ == "__main__":
    main()
