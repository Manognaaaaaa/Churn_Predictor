# Final report — churn & revenue risk platform

README steps 2-9 are implemented, trained on the user's own datasets, and verified end to end. Work lives on per-step branches (`step-2-data-eda` … `step-7-app`); `main` is untouched pending PR review.

## Results headline

- **Model:** Random Forest wins on validation PR-AUC (0.7224 vs 0.7183 XGBoost, 0.6720 LSTM, ≤0.5544 both logistic variants). Isotonic calibration cuts test ECE from 0.0396 → **0.0234** (−41%) at a small PR-AUC cost (0.7055 → 0.6756, expected since isotonic coarsens the ranking); Brier improves 0.1043 → 0.1018. Test set: 1,500 customers, held out and touched once.
- **Cost-optimal threshold 0.060** flags 1,061 of 1,500 validation customers at offer cost = 10% of customer value and assumed uplift = 30%.
- **Portfolio risk:** 208.1M revenue at risk across 10,000 customers; bands 7,151 green / 1,617 amber / 1,232 red (thresholds 0.20 / 0.50).
- **Forecast (Step 9, real series):** weekly UCI Online Retail II revenue (104 weeks, 8-week holdout). ADF d = 0, AIC picks ARIMA(1,0,1). Holdout MAE: ARIMA 114,173, moving average 84,865, seasonal naive 53,019, naive 42,339; rolling-origin MAE (10 origins): ARIMA 49,389, moving average 52,937, naive 40,877, seasonal naive 35,079. **ARIMA does not beat the simple baselines.** The earlier synthetic-history result (547,720 vs 685,324) was circular and is removed.
- **Allocation (Step 8, test split):** segment-aware KKT expects to save 88,005 at a 15,000 test budget (the 100k portfolio budget x the 15% population share) vs 75,331 for global KKT, 75,942 for top-k by risk, 17,704 for uniform (about 5x). After offer matching the figures are 82,423 / 77,772 / 78,113 / 8,875. Dual ascent reproduces the KKT optimum within 0.03%. The Step 6 figure (582,595 on all 10,000 customers, 70% of them training rows, scored with one global curve) is superseded.

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

## Strategy comparison (test split, budget 15,000)

| Strategy | Expected saved (continuous) | Expected saved (snapped) | Realized saved (labels) |
|---|---|---|---|
| Segment-aware KKT | 88,005 | 82,423 | 85,659 |
| Global KKT | 75,331 | 77,772 | 73,606 |
| Top-k by risk | 75,942 | 78,113 | 73,990 |
| Top-k by revenue at risk | 59,802 | 60,196 | 57,840 |
| Risk-proportional | 41,647 | 43,753 | 40,377 |
| Uniform | 17,704 | 8,875 | 17,815 |

Sensitivity (+-25%/50% on each of the 24 groups' a and t, and all together; 204 scenarios): segment-aware stays first in 204/204 and never loses to global KKT, margin +1.6% to +36.4%. A stress test with the assumed tier effect reversed does flip it (-19.8%). Full detail: `reports/allocation.md`.

## Claims

1. **Calibration matters more than ranking when scores drive spending: not supported.** Realized saved revenue (true labels, test split, 1,000-resample bootstrap) is not separable across six probability sources; all paired CIs against RF raw include zero. Calibration metrics correlate with realized savings more than PR-AUC (Spearman -0.89 ECE, -0.94 Brier, +0.64 PR-AUC), but with six points and Brier confounded by ranking this is not evidence. With a binding budget a uniform rescaling of p is absorbed by the Lagrange multiplier, which limits how much calibration can matter for a fixed-budget allocation. The earlier "calibrated saves 3,022 more" figure scored both allocations with the calibrated probabilities and was circular; it has been removed.
2. **Segment-aware allocation beats uniform discounting at equal budget: supported (about 5x).** The fairer comparison, against a global response curve, gives +16.8% expected savings (partly by construction), a realized-label difference of +12k with a CI that includes zero, and about +6% after offer snapping. The advantage depends on assumed (not measured) response curves.
3. **Reallocation rounds beat a single allocation: no.** 6 monthly rounds save 57,975 vs 85,872 for one-shot (paired difference -27,896, SE 6,722).

4. **ARIMA beats a moving-average baseline: not on real data.** On the weekly Online Retail II series ARIMA(1,0,1) is last of four on the 8-week holdout and third of four in a 10-origin rolling backtest; naive and seasonal-naive win. The Q4 peak and Christmas shutdown dominate and two years of history cannot support seasonal terms. Scenario totals over 12 weeks: no_intervention 2,071,244 GBP, with_allocation 2,072,661 GBP (+0.07%).

## Deviations from the original plan (documented)

- **No timestamps in the data** → stratified 70/15/15 splits and stratified k-fold CV replace time-based splits and expanding-window CV. Recorded in `configs/config.yaml` comments and `reports/model_card.md`. All other leakage rules hold: transformers, PCA, scaling, calibration and thresholds are fit on train/valid only.
- **LSTM** consumes jittered synthetic sequences because the dataset has no time axis; it still ranks 3rd of 6.
- **`customer_value` = EstimatedSalary** (income proxy), not observed revenue. Step 6 economics use the raw salary, never the Yeo-Johnson-transformed feature.
- **Frontend** uses plain Tailwind components instead of shadcn/ui (fewer deps, same look); `frontend/dist/` and `node_modules/` are gitignored, `package-lock.json` is committed.
- **Forecast data** is a different business from the churn data (UCI Online Retail II, GBP): the churn model only supplies a loss-rate ratio. `forecast.parquet` keeps the column name `month`, which holds the week-ending Sunday; `GET /forecast` now returns `freq`.
- **API** falls back to `artifacts/mock/` when real artifacts are absent, so the app track runs before the pipeline; `GET /model/metrics` returns each model's `valid_*` metrics (superset of the v0 contract in `docs/contracts.md`).

## Step summary

| Step | Branch | Key outputs | Tests |
|---|---|---|---|
| 2 Data + EDA | `step-2-data-eda` | ingest/label/clean, `reports/eda.md`, dataset mapping for Churn_Modelling + Telco | 7 |
| 3 Features + PCA | `step-3-features` | leakage-safe FeatureBuilder, 11 PCs @ 97.4% variance, imbalance "none" wins | (covered in 4) |
| 4 Modeling | `step-4-modeling` | 6 models, isotonic calibration, cost threshold, SHAP top-5 in `scores.parquet`, model card | 12 |
| 5 Risk | `step-5-risk` | revenue at risk, GMM k=8 segments, band counts (forecast replaced in step 9) | 16 |
| 6 Allocation | `step-6-allocation` | KKT solver + dual-ascent check, strategy comparison, sensitivity, `with_allocation` forecast | 22 |
| 7 App | `step-7-app` | FastAPI (8 endpoints + PDF reports), React dashboard (4 tabs), Makefile api/web, README + final report | 5 (API) |
| 8 Claims | `step-8-claims` | segment x tier response curves, offer catalog + matching, six strategies, label-based calibration test, sensitivity, rounds, API strategies + sweep | 77 total |
| 9 Time series | `step-9-timeseries` | real weekly series, ADF/ACF/PACF/AIC, residual checks, baselines + rolling-origin backtest, churn-adjusted scenarios | 94 total |

## How to run

```bash
pip install -r requirements.txt
make data && make features && make train && make risk && make allocate && make claims
make api   # http://localhost:8000
make web   # http://localhost:5173 (proxies API to :8000)
```

The dashboard was verified against live artifacts: Overview KPIs (10,000 customers / 208.1M at risk), Client Lookup search + detail + drivers + PDF, Budget Planner live solve (1M budget → 3.76M expected saved), Model & Data metrics + calibration curve.
