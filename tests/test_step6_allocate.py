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
    return p, v


def test_kkt_respects_budget_and_caps(data):
    p, v = data
    B, cap = 50_000.0, 500.0
    s = kkt_allocate(p, v, B, cap)
    assert s.sum() <= B + 1e-6
    assert (s >= 0).all() and (s <= cap + 1e-6).all()
    assert (s > 0).sum() > 0


def test_kkt_targets_high_value_first(data):
    p, v = data
    B = 20_000.0
    s = kkt_allocate(p, v, B, cap=500.0)
    score = v * p
    flagged = s > 0
    # mean value*p among flagged should exceed population mean
    assert score[flagged].mean() > score.mean()


def test_gradient_check_agrees(data):
    p, v = data
    B, cap = 30_000.0, 500.0
    s_kkt = kkt_allocate(p, v, B, cap)
    obj_kkt = expected_saved(s_kkt, p, v).sum()
    _, obj_grad = gradient_check(p, v, B, cap, iters=2000)
    assert obj_grad == pytest.approx(obj_kkt, rel=0.05)


def test_segment_aware_beats_uniform(data):
    p, v = data
    comp = strategy_comparison(p, v, 40_000.0, 500.0)
    assert comp["segment_aware_kkt"]["expected_revenue_saved"] > \
        comp["uniform"]["expected_revenue_saved"]


def test_uncalibrated_never_beats_calibrated(data):
    p_cal, v = data
    rng = np.random.default_rng(1)
    p_raw = np.clip(p_cal + rng.normal(0, 0.05, len(p_cal)), 0.01, 0.99)
    out = calibrated_vs_uncalibrated(p_cal, p_raw, v, 40_000.0, 500.0)
    assert out["misallocation_cost"] >= -1e-6


def test_match_offer_picks_nearest():
    assert match_offer(10_000.0, 100_000.0) == "discount_10"   # 10% of 100k
    assert match_offer(100.0, 100_000.0) == "service_call"
    assert match_offer(5.0, 100_000.0) == "loyalty_email"
