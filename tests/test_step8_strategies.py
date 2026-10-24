import numpy as np
import pytest

from churn.allocate import strategies as st
from churn.allocate.evaluate import bootstrap_ci, realized_saved
from churn.config import load_config

ACFG = load_config()["allocation"]
CAP = 500.0


def _problem(n=600, seed=0, heterogeneous=True) -> tuple[st.Problem, np.ndarray]:
    rng = np.random.default_rng(seed)
    p = rng.beta(2, 5, n)
    v = rng.uniform(2_000, 200_000, n)
    tiers = np.where(v < 70_000, "low", np.where(v < 140_000, "mid", "high"))
    eng = rng.choice(["low", "high"], n)
    a_glob = np.full(n, 0.30)
    tau_glob = 0.05 * v
    if heterogeneous:
        a = np.where(eng == "high", 0.36, 0.24)
        tau = tau_glob * np.where(tiers == "high", 1.25, np.where(tiers == "low", 0.8, 1.0))
    else:
        a, tau = a_glob.copy(), tau_glob.copy()
    y = (rng.random(n) < p).astype(int)
    return st.Problem(p, v, a, tau, a_glob, tau_glob, CAP, tiers, eng), y


@pytest.mark.parametrize("name", st.STRATEGY_NAMES)
@pytest.mark.parametrize("budget", [3_000.0, 30_000.0])
def test_every_strategy_respects_budget_and_caps(name, budget):
    pr, _ = _problem()
    x = st.allocate(name, pr, budget)
    assert x.sum() <= budget + 1e-6 and (x >= 0).all() and (x <= CAP + 1e-9).all()
    snap = st.allocate_snapped(name, pr, budget, ACFG)         # ... and after offer snapping
    assert snap["spend"].sum() <= budget + 1e-6
    assert (snap["spend"] >= 0).all() and (snap["spend"] <= CAP + 1e-9).all()


def test_segment_aware_equals_global_when_parameters_equal():
    pr, _ = _problem(heterogeneous=False)
    for b in (3_000.0, 30_000.0):
        assert np.array_equal(st.allocate("segment_aware_kkt", pr, b),
                              st.allocate("global_kkt", pr, b))


def test_segment_aware_differs_from_global_when_groups_differ():
    pr, _ = _problem(heterogeneous=True)
    assert not np.allclose(st.allocate("segment_aware_kkt", pr, 30_000.0),
                           st.allocate("global_kkt", pr, 30_000.0))


def test_kkt_beats_every_baseline_under_its_own_model():
    pr, _ = _problem()
    saved = {n: st.evaluate(pr, st.allocate(n, pr, 20_000.0))["expected_revenue_saved"]
             for n in st.STRATEGY_NAMES}
    assert saved["segment_aware_kkt"] == max(saved.values())   # optimal for the evaluation model
    assert saved["segment_aware_kkt"] >= saved["global_kkt"]


def test_top_k_gives_cap_to_highest_scores_until_budget_ends():
    score = np.array([0.1, 0.9, 0.5, 0.7])
    x = st.top_k(score, budget=1_250.0, cap=500.0)
    assert list(x) == [0.0, 500.0, 250.0, 500.0]


def test_top_k_risk_and_rar_rank_differently():
    pr, _ = _problem()
    assert not np.array_equal(st.allocate("top_k_risk", pr, 5_000.0),
                              st.allocate("top_k_revenue_at_risk", pr, 5_000.0))


def test_evaluate_reports_realized_from_labels_not_probabilities():
    # customer 0: model says very risky but did not churn; customer 1: model says safe but churned
    p = np.array([0.95, 0.05])
    pr = st.Problem(p, np.array([1000.0, 1000.0]), np.array([0.3, 0.3]), np.array([50.0, 50.0]),
                    np.array([0.3, 0.3]), np.array([50.0, 50.0]), CAP,
                    np.array(["mid", "mid"]), np.array(["high", "high"]))
    y = np.array([0, 1])
    x_follow_model = np.array([200.0, 0.0])      # spends on the "risky" customer
    x_follow_truth = np.array([0.0, 200.0])
    m = st.evaluate(pr, x_follow_model, y)
    t = st.evaluate(pr, x_follow_truth, y)
    assert m["expected_revenue_saved"] > t["expected_revenue_saved"]      # model's view
    assert t["realized_revenue_saved"] > m["realized_revenue_saved"] == 0.0  # label view wins
    assert realized_saved(x_follow_truth, y, pr.v, pr.a, pr.tau) == pytest.approx(
        t["realized_revenue_saved"])


def test_bootstrap_ci_contains_the_point_estimate_and_is_seeded():
    vals = np.random.default_rng(0).normal(10, 3, 400)
    m, lo, hi = bootstrap_ci(vals, 500, 42)
    assert lo < m < hi
    assert bootstrap_ci(vals, 500, 42) == (m, lo, hi)
