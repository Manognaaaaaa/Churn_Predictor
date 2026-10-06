# Allocation report

Budget: 100,000 EUR -> 319 customers targeted, 100,000 spent, expected 582,595 saved

## Strategy comparison (equal budget)

|                   |   spend |   expected_revenue_saved |   n_targeted |
|:------------------|--------:|-------------------------:|-------------:|
| segment_aware_kkt |  100000 |                   582595 |          319 |
| uniform           |  100000 |                   121414 |        10000 |
| risk_proportional |  100000 |                   345105 |         7704 |

## KKT vs gradient check

- KKT objective: 582,595
- Projected gradient objective: 581,722

## Sensitivity (±30% on response assumptions)

| scenario    |   u_max |   tau_frac |   expected_revenue_saved |
|:------------|--------:|-----------:|-------------------------:|
| base        |       0 |          0 |                   582595 |
| uplift_low  |       0 |          0 |                   407816 |
| uplift_high |       0 |          0 |                   757373 |
| tau_low     |       0 |          0 |                   821995 |
| tau_high    |       0 |          0 |                   451178 |

## Calibrated vs uncalibrated allocation

- Allocations built on calibrated scores save 582,595
- Allocations built on raw scores save only 579,572
- **Misallocation cost of uncalibrated scores: 3,022** (validates README claim 1)

Note: the gap is small because isotonic calibration is rank-preserving - it cannot reorder customers, only rescale probabilities. The misallocation cost measures value-weighting differences, not ranking errors. A miscalibrated model with a different ranking would show a larger gap.

## Assumptions
- Response curves are assumptions, not measured uplift (see sensitivity above).