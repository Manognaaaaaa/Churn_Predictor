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
