"""Step 4 entrypoint: `make train` — models, calibration, SHAP, scores.parquet."""
from __future__ import annotations

import copy
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import average_precision_score
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from xgboost import XGBClassifier

from churn.config import ROOT, ensure_dirs, load_config
from churn.models import calibrate as cal
from churn.models.explain import top_drivers
from churn.models.lstm import predict_lstm, train_lstm
from churn.models.metrics import brier, calibration_curve, cost_threshold, ece, pr_auc

TARGET = "churned"
META_COLS = ["customer_id", "churned", "snapshot_date", "split", "customer_value_raw"]


def _build_zoo(cfg: dict, class_weight: bool) -> dict:
    m, x = cfg["models"], cfg["models"]["xgb"]
    cw = {"class_weight": "balanced"} if class_weight else {}
    return {
        # MLE: unregularised (C=inf). MAP: L2 penalty == Gaussian prior on weights.
        "logreg_mle": LogisticRegression(C=np.inf, max_iter=2000, **cw),
        "logreg_map": LogisticRegression(C=m["logreg_map_C"], max_iter=2000, **cw),
        "naive_bayes": GaussianNB(),
        "random_forest": RandomForestClassifier(n_estimators=m["rf"]["n_estimators"],
                                                min_samples_leaf=m["rf"]["min_samples_leaf"],
                                                random_state=cfg["seed"], n_jobs=-1),
        "xgboost": XGBClassifier(n_estimators=x["n_estimators"], learning_rate=x["learning_rate"],
                                 max_depth=x["max_depth"], subsample=x["subsample"],
                                 colsample_bytree=x["colsample_bytree"],
                                 eval_metric="logloss", random_state=cfg["seed"], n_jobs=-1),
    }


def _maybe_resample(x, y, strategy, seed):
    if strategy == "smote":
        return SMOTE(random_state=seed).fit_resample(x, y)
    if strategy == "undersample":
        return RandomUnderSampler(random_state=seed).fit_resample(x, y)
    return x, y


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    artifacts = ROOT / cfg["paths"]["artifacts"]
    processed = ROOT / cfg["paths"]["processed"]
    feats = pd.read_parquet(processed / "features.parquet")
    feature_cols = [c for c in feats.columns if c not in META_COLS]

    tr = feats[feats.split == "train"]
    va = feats[feats.split == "valid"]
    te = feats[feats.split == "test"]
    X_tr, y_tr = tr[feature_cols].to_numpy(float), tr[TARGET].to_numpy(int)
    X_va, y_va = va[feature_cols].to_numpy(float), va[TARGET].to_numpy(int)
    X_te, y_te = te[feature_cols].to_numpy(float), te[TARGET].to_numpy(int)

    imb = json.loads((artifacts / "imbalance.json").read_text())
    strategy, cw = imb["chosen"], imb["chosen"] == "class_weight"
    X_rs, y_rs = _maybe_resample(X_tr, y_tr, strategy, cfg["seed"])

    results, fitted = {}, {}
    for name, model in _build_zoo(cfg, cw).items():
        model.fit(X_rs, y_rs)
        fitted[name] = model
        p_va = model.predict_proba(X_va)[:, 1]
        bins = cfg["models"]["calibration"]["ece_bins"]
        results[name] = {"valid_pr_auc": pr_auc(y_va, p_va), "valid_brier": brier(y_va, p_va),
                         "valid_ece": ece(y_va, p_va, bins)}

    # LSTM on synthetic temporal sequences (see models/lstm.py caveat)
    lstm_cfg = cfg["models"]["lstm"]
    lstm, noise = train_lstm(X_rs, y_rs, cfg)
    p_va_lstm = predict_lstm(lstm, X_va, noise, lstm_cfg["seq_len"])
    fitted["lstm"] = ("__lstm__", lstm, noise)
    bins = cfg["models"]["calibration"]["ece_bins"]
    results["lstm"] = {"valid_pr_auc": pr_auc(y_va, p_va_lstm), "valid_brier": brier(y_va, p_va_lstm),
                       "valid_ece": ece(y_va, p_va_lstm, bins)}

    best_name = max(results, key=lambda k: results[k]["valid_pr_auc"])
    best = fitted[best_name]

    # stratified k-fold CV for the chosen model (stand-in for expanding window)
    skf = StratifiedKFold(n_splits=cfg["windows"]["cv_folds"], shuffle=True, random_state=cfg["seed"])
    cv_scores = []
    for tr_i, va_i in skf.split(X_tr, y_tr):
        Xr, yr = _maybe_resample(X_tr[tr_i], y_tr[tr_i], strategy, cfg["seed"])
        if best_name == "lstm":
            m2, n2 = train_lstm(Xr, yr, cfg)
            cv_scores.append(average_precision_score(y_tr[va_i],
                            predict_lstm(m2, X_tr[va_i], n2, lstm_cfg["seq_len"])))
        else:
            m2 = copy.deepcopy(best).fit(Xr, yr)
            cv_scores.append(average_precision_score(y_tr[va_i], m2.predict_proba(X_tr[va_i])[:, 1]))
    results[best_name]["cv_pr_auc"] = float(np.mean(cv_scores))

    # calibrate on valid (platt vs isotonic, lowest Brier wins)
    p_va_best = p_va_lstm if best_name == "lstm" else best.predict_proba(X_va)[:, 1]
    calib = cal.fit_best(p_va_best, y_va, methods=cfg["models"]["calibration"]["methods"])
    p_va_cal = cal.platt_apply(calib["model"], p_va_best) if calib["name"] == "platt" \
        else cal.isotonic_apply(calib["model"], p_va_best)

    # cost-based decision threshold on calibrated valid probabilities
    thr_params = cfg["models"]["threshold"]
    thr = cost_threshold(p_va_cal, va["customer_value_raw"].to_numpy(float),
                         offer_cost_frac=thr_params["offer_cost_frac"],
                         offer_uplift=thr_params["offer_uplift"],
                         fn_cost_multiple=cfg["budget"]["fn_cost_multiple"])

    # score the full population
    X_all = feats[feature_cols].to_numpy(float)
    if best_name == "lstm":
        p_raw = predict_lstm(best[1], X_all, best[2], lstm_cfg["seq_len"])
    else:
        p_raw = best.predict_proba(X_all)[:, 1]
    p_cal = cal.platt_apply(calib["model"], p_raw) if calib["name"] == "platt" \
        else cal.isotonic_apply(calib["model"], p_raw)
    bands = np.where(p_cal <= cfg["risk_bands"]["green_max"], "green",
                     np.where(p_cal <= cfg["risk_bands"]["amber_max"], "amber", "red"))

    te_mask = (feats["split"] == "test").to_numpy()
    test_metrics = {
        "pr_auc_raw": pr_auc(y_te, p_raw[te_mask]),
        "pr_auc_calibrated": pr_auc(y_te, p_cal[te_mask]),
        "brier_raw": brier(y_te, p_raw[te_mask]),
        "brier_calibrated": brier(y_te, p_cal[te_mask]),
        "ece_raw": ece(y_te, p_raw[te_mask], bins),
        "ece_calibrated": ece(y_te, p_cal[te_mask], bins),
    }

    # SHAP top-5 drivers (LSTM has no explainer -> explain logreg_map instead)
    expl_model = best if best_name != "lstm" else fitted["logreg_map"]
    drivers = top_drivers(pd.DataFrame(X_all, columns=feature_cols), expl_model, feature_cols)

    raw_value = feats["customer_value_raw"].to_numpy(float)
    scores = pd.DataFrame({
        "customer_id": feats["customer_id"].to_numpy(),
        "snapshot_date": feats["snapshot_date"].to_numpy(),
        "p_churn_raw": p_raw,
        "p_churn_calibrated": p_cal,
        "risk_band": bands,
        "revenue_at_risk": p_cal * raw_value,
        "top_drivers": drivers,
    })
    scores.to_parquet(artifacts / "scores.parquet", index=False)

    joblib.dump({
        "model_name": best_name,
        "model": None if best_name == "lstm" else best,
        "lstm_state": None if best_name != "lstm" else best[1].state_dict(),
        "lstm_noise": None if best_name != "lstm" else best[2],
        "calibrator_name": calib["name"],
        "calibrator": calib["model"],
        "threshold": thr["threshold"],
        "feature_names": feature_cols,
    }, artifacts / "model.joblib")

    metrics = {
        "models": results,
        "best_model": best_name,
        "calibration": calib["name"],
        "calibration_valid_brier": calib["valid_brier"],
        "threshold": thr,
        "test": test_metrics,
        "calibration_curve": calibration_curve(y_te, p_cal[te_mask]),
        "imbalance_strategy": strategy,
    }
    (artifacts / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))

    lines = ["# Model card", "",
             f"Dataset: `{cfg['datasets'][cfg['active_dataset']]['path']}` "
             "(static snapshots; **no timestamps** -> stratified splits, not time-based)", "",
             f"Imbalance strategy: **{strategy}** (CV comparison in artifacts/imbalance.json)", "",
             "## Validation (raw probabilities)", "",
             pd.DataFrame(results).T.round(4).to_markdown(), "",
             f"Chosen by valid PR-AUC: **{best_name}** "
             f"(CV PR-AUC {results[best_name].get('cv_pr_auc', float('nan')):.4f})", "",
             f"Calibration: **{calib['name']}** (valid Brier per method: "
             f"{ {k: round(v, 4) for k, v in calib['valid_brier'].items()} })", "",
             f"Cost-based threshold: {thr['threshold']:.3f} "
             f"-> {thr['n_flagged']} customers flagged on valid "
             f"(expected cost {thr['cost']:,.0f})", "",
             "## Test metrics", "", pd.Series(test_metrics).round(4).to_markdown(), "",
             "## Known limitations",
             "- LSTM consumes synthetic jittered sequences (dataset has no time axis).",
             "- `customer_value` is EstimatedSalary (income proxy), not true revenue.",
             "- Calibration fitted on a single valid split; drift is not monitored."]
    (ROOT / cfg["paths"]["reports"] / "model_card.md").write_text("\n".join(lines))

    print(f"best: {best_name} | valid PR-AUC {results[best_name]['valid_pr_auc']:.4f} | "
          f"calibration {calib['name']} | threshold {thr['threshold']:.3f} "
          f"({thr['n_flagged']} flagged on valid)")
    print(f"test: PR-AUC(cal) {test_metrics['pr_auc_calibrated']:.4f} "
          f"Brier(cal) {test_metrics['brier_calibrated']:.4f} "
          f"ECE(cal) {test_metrics['ece_calibrated']:.4f}")
    print(f"scores.parquet: {len(scores)} rows")


if __name__ == "__main__":
    main()
