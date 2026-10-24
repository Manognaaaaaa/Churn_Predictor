# Allocation report

## Response-curve groups (segment x value tier)

Response model for customer *i* in group *g* = (segment, value tier):

`r_i(x) = p_i · v_i · a_g · (1 − exp(−x / τ_i))`, with `τ_i = t_g · v_i`,
`a_g = a · m_seg · m_tier`, `t_g = t · n_seg · n_tier`.

**These parameters are assumptions.** The dataset has no treatment or uplift data (nobody was
randomly offered anything), so how strongly a group responds to an offer cannot be estimated.
Every number is in `configs/config.yaml` under `allocation.response_curves`.

**Rule (written before looking at which strategy wins, not tuned):**

1. *Segment → a.* Engagement index `e_s` = mean of the across-segment z-scores of the segment's
   train-split mean `IsActiveMember` and mean `NumOfProducts`. `m_seg = clip(1 + 0.15·e_s, 0.5, 1.5)`.
   More engaged segments (active members, more products) are assumed to respond more to offers.
2. *Segment → t.* No evidence that segments differ in how large an offer must be, so `n_seg = 1`
   (slope 0).
3. *Tier → t.* Tier index k = −1, 0, +1 for low, mid, high; `n_tier = 1.25^k`. High-value customers
   need a bigger offer to move. Nothing suggests tiers differ in maximum response, so `m_tier = 1`.
4. Defaults `a = 0.30` (the previous global offer uplift) and `t = 0.05` (the previous global
   `tau_frac`).

Caveat: the GMM segments are only weakly separated on engagement (segment means of
`IsActiveMember` range 0.47–0.56 and of `NumOfProducts` 1.28–1.79), so the segment multipliers
are modest by construction. Since `m_tier = n_seg = 1`, tiers affect only `t_g` and segments only `a_g`.


|   segment_id | value_tier   |   engagement | engagement_class   |   m_seg |   m_tier |   n_seg |   n_tier |    a_g |    t_g |
|-------------:|:-------------|-------------:|:-------------------|--------:|---------:|--------:|---------:|-------:|-------:|
|            0 | low          |      -1.0905 | low                |  0.8364 |        1 |       1 |     0.8  | 0.2509 | 0.04   |
|            0 | mid          |      -1.0905 | low                |  0.8364 |        1 |       1 |     1    | 0.2509 | 0.05   |
|            0 | high         |      -1.0905 | low                |  0.8364 |        1 |       1 |     1.25 | 0.2509 | 0.0625 |
|            1 | low          |       0.7941 | high               |  1.1191 |        1 |       1 |     0.8  | 0.3357 | 0.04   |
|            1 | mid          |       0.7941 | high               |  1.1191 |        1 |       1 |     1    | 0.3357 | 0.05   |
|            1 | high         |       0.7941 | high               |  1.1191 |        1 |       1 |     1.25 | 0.3357 | 0.0625 |
|            2 | low          |       0.3898 | high               |  1.0585 |        1 |       1 |     0.8  | 0.3175 | 0.04   |
|            2 | mid          |       0.3898 | high               |  1.0585 |        1 |       1 |     1    | 0.3175 | 0.05   |
|            2 | high         |       0.3898 | high               |  1.0585 |        1 |       1 |     1.25 | 0.3175 | 0.0625 |
|            3 | low          |      -0.4104 | low                |  0.9384 |        1 |       1 |     0.8  | 0.2815 | 0.04   |
|            3 | mid          |      -0.4104 | low                |  0.9384 |        1 |       1 |     1    | 0.2815 | 0.05   |
|            3 | high         |      -0.4104 | low                |  0.9384 |        1 |       1 |     1.25 | 0.2815 | 0.0625 |
|            4 | low          |      -0.5993 | low                |  0.9101 |        1 |       1 |     0.8  | 0.273  | 0.04   |
|            4 | mid          |      -0.5993 | low                |  0.9101 |        1 |       1 |     1    | 0.273  | 0.05   |
|            4 | high         |      -0.5993 | low                |  0.9101 |        1 |       1 |     1.25 | 0.273  | 0.0625 |
|            5 | low          |       0.3087 | high               |  1.0463 |        1 |       1 |     0.8  | 0.3139 | 0.04   |
|            5 | mid          |       0.3087 | high               |  1.0463 |        1 |       1 |     1    | 0.3139 | 0.05   |
|            5 | high         |       0.3087 | high               |  1.0463 |        1 |       1 |     1.25 | 0.3139 | 0.0625 |
|            6 | low          |       0.4132 | high               |  1.062  |        1 |       1 |     0.8  | 0.3186 | 0.04   |
|            6 | mid          |       0.4132 | high               |  1.062  |        1 |       1 |     1    | 0.3186 | 0.05   |
|            6 | high         |       0.4132 | high               |  1.062  |        1 |       1 |     1.25 | 0.3186 | 0.0625 |
|            7 | low          |       0.1945 | high               |  1.0292 |        1 |       1 |     0.8  | 0.3088 | 0.04   |
|            7 | mid          |       0.1945 | high               |  1.0292 |        1 |       1 |     1    | 0.3088 | 0.05   |
|            7 | high         |       0.1945 | high               |  1.0292 |        1 |       1 |     1.25 | 0.3088 | 0.0625 |

## KKT derivation

**Problem.** Choose spend `x_i` for each customer to maximise expected saved revenue under a budget
and per-customer caps:

`max Σ_i r_i(x_i)`, `r_i(x) = b_i (1 − e^{−x/τ_i})`, `b_i = p_i v_i a_i`,
subject to `Σ_i x_i ≤ B` and `0 ≤ x_i ≤ c` (c = `max_spend_per_customer`).

Each `r_i` is strictly concave (`r_i'' = −(b_i/τ_i²) e^{−x/τ_i} < 0`) and the constraints are
affine, so the problem is convex, Slater holds (x = 0 is strictly feasible when B > 0), and the
KKT conditions are necessary and sufficient for the global optimum.

**Lagrangian.** With multiplier `λ ≥ 0` for the budget and `μ_i ≥ 0`, `ν_i ≥ 0` for the box:

`L = Σ r_i(x_i) − λ(Σ x_i − B) + Σ μ_i x_i − Σ ν_i (x_i − c)`

**Stationarity.** `∂L/∂x_i = (b_i/τ_i) e^{−x_i/τ_i} − λ + μ_i − ν_i = 0`.

**Complementary slackness.** `λ(Σ x_i − B) = 0`, `μ_i x_i = 0`, `ν_i (x_i − c) = 0`.

Three cases per customer:

- *Interior* (`0 < x_i < c`): `μ_i = ν_i = 0`, so `(b_i/τ_i) e^{−x_i/τ_i} = λ`, i.e.
  `x_i = τ_i ln(b_i / (τ_i λ))`. Marginal return equals the common price λ.
- *Lower bound* (`x_i = 0`): `μ_i ≥ 0` gives `b_i/τ_i ≤ λ`: the first euro already returns less
  than λ, so the customer is not worth targeting. Note `b_i/τ_i = p_i a_i / t_g`, independent of v.
- *Upper bound* (`x_i = c`): `ν_i ≥ 0` gives `(b_i/τ_i) e^{−c/τ_i} ≥ λ`: still worth more than λ at the cap.

All three collapse to the closed form `x_i(λ) = clip(τ_i ln(b_i/(τ_i λ)), 0, c)`.

**Finding λ.** Each `x_i(λ)` is non-increasing in λ (ln is increasing, so larger λ lowers the unclipped
value, and clipping preserves monotonicity), continuous, equal to the cap for small enough λ, and equal
to 0 for `λ ≥ max_i b_i/τ_i`. Hence total spend `S(λ) = Σ x_i(λ)` is continuous and monotone
decreasing, so `S(λ) = B` has a solution whenever `B ≤ n·c` (otherwise every customer sits at the cap).
Bisection on λ (in log space) converges to it; we return the iterate on the feasible side so
`Σ x_i ≤ B` holds exactly.

**Cross-check.** A separate dual projected-gradient ascent alternates `x ← clip(x + η(r'(x) − λ), 0, c)`
and `λ ← max(0, λ + η'(Σx − B))`. `run_allocate` asserts its objective agrees with the closed form
within 0.5% (`allocation.dual_check_tolerance`).


Budget: 100,000 EUR -> 544 customers targeted, 99,811 spent, expected 567,354 saved

## Strategy comparison (equal budget)

|                   |   spend |   expected_revenue_saved |   n_targeted |
|:------------------|--------:|-------------------------:|-------------:|
| segment_aware_kkt |  100000 |                   600757 |          428 |
| uniform           |  100000 |                   117909 |        10000 |
| risk_proportional |  100000 |                   299599 |         7704 |

## Offer matching (stage 2)

Continuous KKT saves 600,757; after snapping to the catalog (budget re-balanced in 31 rounds, effective stage-1 budget 156,005) the plan spends 99,811 and saves 567,354.

|                 |   customers |
|:----------------|------------:|
| value_discount  |         238 |
| service_call    |         175 |
| retention_bonus |         105 |
| fee_waiver      |          23 |
| loyalty_email   |           3 |

## KKT vs gradient check

- KKT objective (continuous spend): 600,757
- Dual-ascent objective: 600,604 (gap 0.025%, tolerance 0.5%)

## Sensitivity (interim ±30%; rebuilt in Phase 8.5)

| scenario   |   a_factor |   tau_factor |   expected_revenue_saved |
|:-----------|-----------:|-------------:|-------------------------:|
| base       |          1 |            1 |                   600757 |
| a_low      |          1 |            1 |                   420530 |
| a_high     |          1 |            1 |                   780985 |
| tau_low    |          1 |            1 |                   832060 |
| tau_high   |          1 |            1 |                   471520 |

## Calibrated vs uncalibrated allocation

- Allocations built on calibrated scores save 600,757
- Allocations built on raw scores save only 597,945
- **Misallocation cost of uncalibrated scores: 2,812** (validates README claim 1)

Note: the gap is small because isotonic calibration is rank-preserving - it cannot reorder customers, only rescale probabilities. The misallocation cost measures value-weighting differences, not ranking errors. A miscalibrated model with a different ranking would show a larger gap.

## Assumptions
- Response curves are assumptions, not measured uplift (see sensitivity above).