# Model card

Dataset: `data/raw/Churn_Modelling.csv` (static snapshots; **no timestamps** -> stratified splits, not time-based)

Imbalance strategy: **none** (CV comparison in artifacts/imbalance.json)

## Validation (raw probabilities)

|               |   valid_pr_auc |   valid_brier |   valid_ece |   cv_pr_auc |
|:--------------|---------------:|--------------:|------------:|------------:|
| logreg_mle    |         0.5544 |        0.1264 |      0.0239 |    nan      |
| logreg_map    |         0.5541 |        0.1264 |      0.0235 |    nan      |
| naive_bayes   |         0.4584 |        0.1526 |      0.0937 |    nan      |
| random_forest |         0.7224 |        0.1011 |      0.0473 |      0.6702 |
| xgboost       |         0.7183 |        0.099  |      0.0159 |    nan      |
| lstm          |         0.672  |        0.1087 |      0.0344 |    nan      |

Chosen by valid PR-AUC: **random_forest** (CV PR-AUC 0.6702)

Calibration: **isotonic** (valid Brier per method: {'platt': 0.0985, 'isotonic': 0.0948})

Cost-based threshold: 0.060 -> 1061 customers flagged on valid (expected cost 34,244,089)

## Test metrics

|                   |      0 |
|:------------------|-------:|
| pr_auc_raw        | 0.7055 |
| pr_auc_calibrated | 0.6756 |
| brier_raw         | 0.1043 |
| brier_calibrated  | 0.1018 |
| ece_raw           | 0.0396 |
| ece_calibrated    | 0.0234 |

## Known limitations
- LSTM consumes synthetic jittered sequences (dataset has no time axis).
- `customer_value` is EstimatedSalary (income proxy), not true revenue.
- Calibration fitted on a single valid split; drift is not monitored.