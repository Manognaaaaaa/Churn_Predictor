# Customer Churn & Revenue Risk Platform

From raw data to a calibrated churn model, revenue at risk, a segment-aware retention budget, a FastAPI backend and a React dashboard.

![CI](https://img.shields.io/badge/CI-placeholder-lightgrey) ![Python](https://img.shields.io/badge/python-3.11-blue) ![License](https://img.shields.io/badge/license-TBD-lightgrey)


## Problem

Customers who churn are cheaper to keep than to replace, but retention budgets are finite. Reacting after a customer leaves is too late. Flagging every customer who looks risky wastes money on those who would have stayed. The goal is to find who is likely to leave, estimate how much revenue that puts at risk, and spend a fixed budget where it saves the most.

## The two claims

1. **Calibration matters more than ranking when churn scores drive spending.** A model with high AUC but miscalibrated probabilities misallocates budget.
2. **Segment-aware allocation beats uniform discounting at equal budget.**

## Architecture

```mermaid
flowchart LR
    A[Raw data] --> B[Clean + label]
    B --> C[Features + PCA]
    C --> D[Models]
    D --> E[Calibrated scores + SHAP]
    E --> F[Revenue at risk + Segments]
    B --> G[ARIMA forecast]
    G --> F
    F --> H[Budget allocator - KKT]
    H --> I[artifacts/]
    I --> J[FastAPI]
    J --> K[React]
```

## Pipeline

| # | Step | What it involves | Depends on | Output | Owner | Status |
|---|---|---|---|---|---|---|
| 1 | Setup + dataset | Repo, config, Makefile. Dataset chosen against hard rules (real churn labels, timestamps, revenue per customer, behavioural features, ≥10k customers). Data contracts agreed. | none | repo, dataset choice, contracts | TBD | ✅ |
| 2 | Data + EDA | Ingestion + schema checks, monthly snapshot labeling, cleaning (imputation, outlier capping, Box-Cox/Yeo-Johnson). EDA: churn by tier and over time, correlation + VIF, engagement × support co-occurrence test. | 1 | clean labeled data, EDA report | TBD | ✅ |
| 3 | Features + PCA + imbalance | Recency, tenure, usage trend slope, payment and revenue features. Time-based split + expanding-window CV. PCA with interpreted loadings. Class weights vs SMOTE vs undersampling. | 2 | feature matrix, PCA, split | TBD | ✅ |
| 4 | Modeling + calibration + SHAP | Logistic regression MLE vs MAP, Naive Bayes, Random Forest, XGBoost, LSTM. PR-AUC, Brier, ECE. Platt/isotonic calibration, cost-based threshold, SHAP top 5 drivers, model card. | 3 | `scores.parquet`, model | TBD | ✅ |
| 5 | Revenue risk + forecast + segments | Revenue at risk = P(churn) × customer value. ARIMA vs moving-average baseline. GMM segments chosen by BIC, crossed with value tiers. | 4 (ARIMA needs only 2) | forecast, segments | TBD | ✅ |
| 6 | Budget allocation | Lagrangian/KKT solver + gradient-descent check, offer matching per segment, reallocation loop. Strategy comparison, sensitivity analysis, calibrated vs uncalibrated test. | 4, 5 (solver can use mock data) | `allocations.parquet`, allocation report | TBD | ✅ |
| 7 | App + ship | FastAPI endpoints + React dashboard (Overview, Client Lookup, Budget Planner, Model & Data). Tests + CI, Docker, deploy, final report. | 6 (can start on mock data after 1) | live app, docs | TBD | ✅ |

**Status legend:** ⬜ not started · 🟨 in progress · ✅ done

Owners update this table in their PRs.

**Implementation notes (steps 2–7 complete):** the datasets have no timestamps, so splits are stratified 70/15/15 with stratified k-fold CV instead of time-based windows (recorded in `configs/config.yaml` and `reports/model_card.md`). All other leakage rules hold — transformers, PCA and calibration are fit on train/valid only.

## Syllabus coverage

| Course topic | Step |
|---|---|
| Bayesian inference, MLE vs MAP | 4 |
| PCA | 3 |
| Time series (ARIMA, ACF/PACF, moving averages) | 5 |
| LSTM | 4 |
| Constrained optimization (Lagrange multipliers, KKT, gradient descent) | 6 |
| Data visualization | 2, 7 |

## Tech stack

| Area | Tools |
|---|---|
| Data + ML | Python 3.11, pandas, scikit-learn, imbalanced-learn, XGBoost, SHAP, statsmodels, PyTorch |
| API | FastAPI, Pydantic |
| Frontend | Vite, React, TypeScript, Tailwind, TanStack Query, Recharts |
| Ops | Docker, GitHub Actions |

## Repo structure

```
.
├── configs/config.yaml            # paths, seed, windows, budget, risk bands
├── data/{raw,interim,processed}/  # datasets (gitignored)
├── src/churn/                     # all ML and business logic
│   └── models/                    # model training and calibration code
├── src/api/                       # FastAPI app: validates and calls src/churn
│   └── routers/                   # one router per resource
├── frontend/                      # React dashboard (step 7)
├── notebooks/                     # EDA and exploration
├── reports/                       # EDA, allocation and final reports
├── artifacts/                     # step outputs: parquet files, models (gitignored)
├── scripts/                       # helpers, e.g. make_mocks.py
├── tests/                         # pytest
├── docs/contracts.md              # data and API contracts (v0)
├── requirements.txt
├── Makefile
└── README.md
```

## Getting started

```bash
git clone <repo-url>
cd <repo>
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

- Put the raw datasets in `data/raw/` (gitignored). Used here: `Churn_Modelling.csv` (10,000 customers, primary) and `Telco_customer_churn.xlsx` (7,043 rows, secondary); `configs/config.yaml` maps each schema and `active_dataset` picks one.
- `make help` lists all targets.
- `make mocks` writes fake artifacts to `artifacts/mock/` so the app track can start early.

| Command | Available from |
|---|---|
| `make data` | step 2 |
| `make features` | step 3 |
| `make train` | step 4 |
| `make risk` | step 5 |
| `make allocate` | step 6 |
| `make api`, `make web` | step 7 |

To run the app end to end:

```bash
make data && make features && make train && make risk && make allocate
make api      # FastAPI on http://localhost:8000 (falls back to artifacts/mock/ if empty)
make web      # React dashboard on http://localhost:5173, proxies API calls to :8000
```

The web target needs Node 18+. `make mocks` generates placeholder artifacts so the dashboard runs before the pipeline.

## Ground rules

- All ML and business logic lives in `src/churn/`. The API only validates and calls. React only displays.
- No leakage: transformers, PCA and SMOTE fit on the training window only. Splits are time-based, never random shuffles.
- All thresholds, dates, seeds and budgets live in `configs/config.yaml`.
- Each step writes outputs to `artifacts/` or `reports/`. Downstream steps read files and never retrain.
- Work on branches named `step-N-short-name`, open a PR, and the other person reviews.

## Results

Trained on `Churn_Modelling.csv`: 10,000 customers, 20.4% churn, stratified 70/15/15 split.

**Validation (raw probabilities):**

| Model | PR-AUC | Brier | ECE |
|---|---|---|---|
| Logistic regression (MLE) | 0.5544 | 0.1264 | 0.0239 |
| Logistic regression (MAP) | 0.5541 | 0.1264 | 0.0235 |
| Naive Bayes | 0.4584 | 0.1526 | 0.0937 |
| **Random Forest (chosen)** | **0.7224** | 0.1011 | 0.0473 |
| XGBoost | 0.7183 | 0.0990 | 0.0159 |
| LSTM | 0.6720 | 0.1087 | 0.0344 |

Held-out test with isotonic calibration: PR-AUC 0.6756, Brier 0.1018, ECE 0.0234 (raw: 0.7055 / 0.1043 / 0.0396) — calibration cuts ECE by ~40% at a small PR-AUC cost. Cost-optimal threshold 0.060 flags 1,061 of 1,500 validation customers.

**Portfolio snapshot:** 208.1M revenue at risk; risk bands 7,151 green / 1,617 amber / 1,232 red; ARIMA(1,1,1) forecast backtest MAE 547,720 vs 685,324 for the moving-average baseline.

**Strategy comparison (equal 100k budget):**

| Strategy | Spend | Expected revenue saved | Customers targeted |
|---|---|---|---|
| Segment-aware (KKT) | 100,000 | **582,595** | 319 |
| Risk-proportional | 100,000 | 345,105 | 7,704 |
| Uniform | 100,000 | 121,414 | 10,000 |

Allocating on calibrated instead of raw scores saves 3,022 more at equal spend — a small gap here because isotonic calibration is rank-preserving; see `reports/allocation.md` for the sensitivity analysis.

## Limitations

- Offer response curves are assumptions, not measured uplift; see sensitivity analysis in step 6.
- Churn is defined on static bank snapshots: the datasets carry no timestamps, so there is no true temporal validation and the LSTM consumes jittered synthetic sequences.
- `customer_value` is EstimatedSalary (an income proxy), not observed revenue; calibration is fit on a single validation split and drift is not monitored.


