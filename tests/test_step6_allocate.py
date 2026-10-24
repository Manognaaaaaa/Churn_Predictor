import numpy as np
import pytest

from churn.allocate.solver import (calibrated_vs_uncalibrated, expected_saved,
                                   gradient_check, kkt_allocate, match_offer,
                                   strategy_comparison)


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    n = 400
    p = rng.beta(2, 5, n)
    v = rng.lognormal(8, 0.5, n)
    a = rng.uniform(0.15, 0.45, n)                      # per-customer response ceiling
    tau = rng.choice([0.04, 0.05, 0.0625], n) * v        # per-customer saturation
    return p, v, a, tau


def test_kkt_respects_budget_and_caps(data):
    p, v, a, tau = data
    B, cap = 50_000.0, 500.0
    x = kkt_allocate(p, v, a, tau, B, cap)
    assert x.sum() <= B + 1e-6
    assert (x >= 0).all() and (x <= cap + 1e-6).all()
    assert (x > 0).sum() > 0
    assert x.sum() == pytest.approx(B, rel=1e-6)         # budget binds here


def test_kkt_targets_high_value_first(data):
    p, v, a, tau = data
    x = kkt_allocate(p, v, a, tau, 20_000.0, cap=500.0)
    score = v * p
    assert score[x > 0].mean() > score.mean()


def test_kkt_stationarity_on_interior_customers(data):
    p, v, a, tau = data
    x = kkt_allocate(p, v, a, tau, 30_000.0, 500.0)
    interior = (x > 1e-6) & (x < 500.0 - 1e-6)
    marginal = (p * v * a / tau) * np.exp(-x / tau)
    assert interior.sum() > 10
    assert np.allclose(marginal[interior], marginal[interior][0], rtol=1e-6)


def test_dual_ascent_agrees_with_kkt_within_half_percent(data):
    p, v, a, tau = data
    B, cap = 30_000.0, 500.0
    obj_kkt = expected_saved(kkt_allocate(p, v, a, tau, B, cap), p, v, a, tau).sum()
    _, obj_grad = gradient_check(p, v, a, tau, B, cap)
    assert obj_grad == pytest.approx(obj_kkt, rel=0.005)


def test_segment_aware_beats_uniform(data):
    p, v, a, tau = data
    comp = strategy_comparison(p, v, a, tau, 40_000.0, 500.0)
    assert comp["segment_aware_kkt"]["expected_revenue_saved"] > \
        comp["uniform"]["expected_revenue_saved"]


def test_calibrated_vs_uncalibrated_interim_runs(data):
    # The old "uncalibrated never beats calibrated" assertion is gone: it held only because
    # both allocations were scored with p_cal. The label-based test arrives in Phase 8.4.
    p_cal, v, a, tau = data
    rng = np.random.default_rng(1)
    p_raw = np.clip(p_cal + rng.normal(0, 0.05, len(p_cal)), 0.01, 0.99)
    out = calibrated_vs_uncalibrated(p_cal, p_raw, v, a, tau, 40_000.0, 500.0)
    assert set(out) == {"saved_calibrated_allocation", "saved_uncalibrated_allocation",
                        "misallocation_cost"}


def test_match_offer_picks_nearest():
    assert match_offer(10_000.0, 100_000.0) == "discount_10"   # 10% of 100k
    assert match_offer(100.0, 100_000.0) == "service_call"
    assert match_offer(5.0, 100_000.0) == "loyalty_email"
