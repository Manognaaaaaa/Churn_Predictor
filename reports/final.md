# Final report — churn & revenue risk platform

All seven README steps are implemented, trained on the user's own datasets, and verified end to end. Work lives on per-step branches (`step-2-data-eda` … `step-7-app`); `main` is untouched pending PR review.

## Results headline

- **Model:** Random Forest wins on validation PR-AUC (0.7224 vs 0.7183 XGBoost, 0.6720 LSTM, ≤0.5544 both logistic variants). Isotonic calibration cuts test ECE from 0.0396 → **0.0234** (−41%) at a small PR-AUC cost (0.7055 → 0.6756, expected since isotonic coarsens the ranking); Brier improves 0.1043 → 0.1018. Test set: 1,500 customers, held out and touched once.
- **Cost-optimal threshold 0.060** flags 1,061 of 1,500 validation customers at offer cost = 10% of customer value and assumed uplift = 30%.
- **Portfolio risk:** 208.1M revenue at risk across 10,000 customers; bands 7,151 green / 1,617 amber / 1,232 red (thresholds 0.20 / 0.50).
- **Forecast:** ARIMA(1,1,1) chosen by backtest — MAE **547,720** vs 685,324 for the moving-average baseline (−20%).
- **Allocation:** KKT segment-aware water-filling saves **582,595** on a 100k budget vs 345,105 risk-proportional and 121,414 uniform (**4.8× uniform**). Dual-ascent gradient check reproduces the KKT optimum to 0.00%. Allocating on calibrated rather than raw scores saves 3,022 more — small here because isotonic calibration is rank-preserving (it rescales probabilities without reordering customers); the same comparison against a miscalibrated but differently-ranked model would be much larger.

## Model comparison (validation, raw probabilities)

| Model | PR-AUC | Brier | ECE |
|---|---|---|---|
| Logistic regression (MLE) | 0.5544 | 0.1264 | 0.0239 |
| Logistic regression (MAP) | 0.5541 | 0.1264 | 0.0235 |
| Naive Bayes | 0.4584 | 0.1526 | 0.0937 |
| **Random Forest (chosen)** | **0.7224** | 0.1011 | 0.0473 |
| XGBoost | 0.7183 | 0.0990 | 0.0159 |
| LSTM | 0.6720 | 0.1087 | 0.0344 |

Random Forest stratified 5-fold CV PR-AUC: 0.6702. Calibration method chosen by validation Brier: isotonic 0.0948 vs Platt 0.0985.

## Strategy comparison (equal 100k budget)

| Strategy | Spend | Expected revenue saved | Customers targeted |
|---|---|---|---|
| Segment-aware (KKT) | 100,000 | **582,595** | 319 |
| Risk-proportional | 100,000 | 345,105 | 7,704 |
| Uniform | 100,000 | 121,414 | 10,000 |

Sensitivity ±30% on response assumptions moves expected savings between 407,816 and 821,995 without changing the ranking of strategies. Full detail: `reports/allocation.md`.

## Claims

1. **Calibration matters more than ranking when scores drive spending** — supported directionally (calibrated allocation saves more, ECE halved), with the rank-preserving caveat above.
2. **Segment-aware allocation beats uniform discounting at equal budget** — strongly supported: 4.8× the expected savings of uniform at identical spend.

## Deviations from the original plan (documented)

- **No timestamps in the data** → stratified 70/15/15 splits and stratified k-fold CV replace time-based splits and expanding-window CV. Recorded in `configs/config.yaml` comments and `reports/model_card.md`. All other leakage rules hold: transformers, PCA, scaling, calibration and thresholds are fit on train/valid only.
- **LSTM** consumes jittered synthetic sequences because the dataset has no time axis; it still ranks 3rd of 6.
- **`customer_value` = EstimatedSalary** (income proxy), not observed revenue. Step 6 economics use the raw salary, never the Yeo-Johnson-transformed feature.
- **Frontend** uses plain Tailwind components instead of shadcn/ui (fewer deps, same look); `frontend/dist/` and `node_modules/` are gitignored, `package-lock.json` is committed.
- **API** falls back to `artifacts/mock/` when real artifacts are absent, so the app track runs before the pipeline; `GET /model/metrics` returns each model's `valid_*` metrics (superset of the v0 contract in `docs/contracts.md`).

## Step summary

| Step | Branch | Key outputs | Tests |
|---|---|---|---|
| 2 Data + EDA | `step-2-data-eda` | ingest/label/clean, `reports/eda.md`, dataset mapping for Churn_Modelling + Telco | 7 |
| 3 Features + PCA | `step-3-features` | leakage-safe FeatureBuilder, 11 PCs @ 97.4% variance, imbalance "none" wins | (covered in 4) |
| 4 Modeling | `step-4-modeling` | 6 models, isotonic calibration, cost threshold, SHAP top-5 in `scores.parquet`, model card | 12 |
| 5 Risk | `step-5-risk` | revenue at risk, ARIMA vs MA backtest, GMM k=8 segments, band counts | 16 |
| 6 Allocation | `step-6-allocation` | KKT solver + dual-ascent check, strategy comparison, sensitivity, `with_allocation` forecast | 22 |
| 7 App | `step-7-app` | FastAPI (8 endpoints + PDF reports), React dashboard (4 tabs), Makefile api/web, README + final report | 5 (API) |

## How to run

```bash
pip install -r requirements.txt
make data && make features && make train && make risk && make allocate
make api   # http://localhost:8000
make web   # http://localhost:5173 (proxies API to :8000)
```

The dashboard was verified against live artifacts: Overview KPIs (10,000 customers / 208.1M at risk), Client Lookup search + detail + drivers + PDF, Budget Planner live solve (1M budget → 3.76M expected saved), Model & Data metrics + calibration curve.
