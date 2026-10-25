import numpy as np
import pytest

from churn.allocate import offers as of
from churn.allocate.solver import kkt_allocate
from churn.config import load_config

CAT = load_config()["allocation"]["offers"]
CAP, MIN_SPEND = 500.0, 0.5


def _population(n=800, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.beta(2, 5, n)
    v = rng.uniform(1_000, 200_000, n)
    tiers = np.where(v < 70_000, "low", np.where(v < 140_000, "mid", "high"))
    eng = rng.choice(["low", "high"], n)
    a = np.where(eng == "high", 0.33, 0.26)
    tau = 0.05 * v * np.where(tiers == "high", 1.25, np.where(tiers == "low", 0.8, 1.0))
    return p, v, tiers, eng, a, tau


def test_snap_picks_cheapest_covering_eligible_offer():
    v = np.array([100_000.0] * 3)
    tiers, eng = np.array(["mid"] * 3), np.array(["low", "low", "high"])
    names, cost = of.offer_matrix(v, tiers, eng, CAT, CAP)
    offer, spend = of.snap_to_offers(np.array([3.0, 60.0, 200.0]), cost, names, MIN_SPEND)
    assert list(offer) == ["loyalty_email", "service_call", "retention_bonus"]
    assert list(spend) == [5.0, 100.0, 250.0]


def test_snap_falls_back_to_largest_eligible_when_none_covers():
    v = np.array([100_000.0])
    names, cost = of.offer_matrix(v, np.array(["mid"]), np.array(["low"]), CAT, CAP)
    offer, spend = of.snap_to_offers(np.array([400.0]), cost, names, MIN_SPEND)
    assert offer[0] == "service_call" and spend[0] == 100.0     # low engagement tops out at 100


def test_ineligible_and_over_cap_offers_never_chosen():
    v = np.array([400_000.0])                     # value_discount would cost 2000 > cap
    names, cost = of.offer_matrix(v, np.array(["high"]), np.array(["high"]), CAT, CAP)
    assert np.isinf(cost[0, names.index("value_discount")])
    low = of.offer_matrix(v, np.array(["high"]), np.array(["low"]), CAT, CAP)[1]
    assert np.isinf(low[0, names.index("retention_bonus")])    # not eligible for low engagement


def test_untargeted_customers_get_no_offer():
    names, cost = of.offer_matrix(np.array([1e5]), np.array(["mid"]), np.array(["high"]), CAT, CAP)
    offer, spend = of.snap_to_offers(np.array([0.1]), cost, names, MIN_SPEND)
    assert offer[0] == of.NO_OFFER and spend[0] == 0.0


@pytest.mark.parametrize("budget", [5_000.0, 40_000.0, 150_000.0])
def test_budget_and_caps_hold_after_snapping(budget):
    p, v, tiers, eng, a, tau = _population()
    out = of.allocate_with_offers(lambda b: kkt_allocate(p, v, a, tau, b, CAP), v, tiers, eng,
                                  budget, CAP, CAT, MIN_SPEND, 25)
    assert out["spend"].sum() <= budget + 1e-9
    assert (out["spend"] <= CAP + 1e-9).all() and (out["spend"] >= 0).all()
    assert ((out["spend"] > 0) == (out["offer"] != of.NO_OFFER)).all()
    assert out["spend"].sum() > 0.9 * budget            # re-balancing does not leave it idle


def test_spend_equals_real_offer_cost():
    p, v, tiers, eng, a, tau = _population()
    out = of.allocate_with_offers(lambda b: kkt_allocate(p, v, a, tau, b, CAP), v, tiers, eng,
                                  30_000.0, CAP, CAT, MIN_SPEND, 25)
    names, cost = of.offer_matrix(v, tiers, eng, CAT, CAP)
    for i in np.flatnonzero(out["spend"] > 0)[:50]:
        assert out["spend"][i] == pytest.approx(cost[i, names.index(out["offer"][i])])


def test_fallback_drops_customers_when_rebalancing_cannot_fit():
    p, v, tiers, eng, a, tau = _population()
    stubborn = lambda b: np.full(len(p), 200.0)            # ignores the budget: always overshoots
    out = of.allocate_with_offers(stubborn, v, tiers, eng, 20_000.0, CAP, CAT, MIN_SPEND, 5)
    assert out["dropped"] > 0 and out["spend"].sum() <= 20_000.0 + 1e-9


def test_undershoot_is_rebalanced_upwards():
    p, v, tiers, eng, a, tau = _population()
    solve = lambda b: kkt_allocate(p, v, a, tau, b, CAP)
    out = of.allocate_with_offers(solve, v, tiers, eng, 40_000.0, CAP, CAT, MIN_SPEND, 40)
    assert out["effective_budget"] > 40_000.0               # low-engagement groups top out early
