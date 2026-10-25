import numpy as np
import pytest

from churn.allocate import claims as cl
from churn.allocate import rounds as rd
from churn.allocate import strategies as st
from churn.allocate.groups import explain_group
from churn.config import load_config

import pandas as pd

CFG = load_config()
ACFG = CFG["allocation"]
CAP = 500.0


def _problem(n=400, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.beta(2, 5, n)
    v = rng.uniform(2_000, 200_000, n)
    tiers = np.where(v < 70_000, "low", np.where(v < 140_000, "mid", "high"))
    eng = rng.choice(["low", "high"], n)
    a_glob, tau_glob = np.full(n, 0.30), 0.05 * v
    a = np.where(eng == "high", 0.36, 0.24)
    tau = tau_glob * np.where(tiers == "high", 1.25, np.where(tiers == "low", 0.8, 1.0))
    y = (rng.random(n) < p).astype(int)
    seg = rng.integers(0, 3, n)
    return st.Problem(p, v, a, tau, a_glob, tau_glob, CAP, tiers, eng), y, seg


# ------------------------------------------------------------------ calibration (claim 1)
def test_calibration_experiment_follows_labels_not_model_probabilities():
    pr, y, _ = _problem(800)
    perfect = np.where(y == 1, 0.9, 0.01)                 # "truth" probabilities = the labels
    misleading = np.where(y == 1, 0.01, 0.9)              # confidently wrong about who churns
    out = cl.calibration_experiment(pr, y, {"p_rf_raw": perfect, "p_bad": misleading},
                                    budget=5_000.0, acfg=ACFG, ece_bins=15, n_boot=100, seed=42,
                                    level=0.9)
    rows = {r["source"]: r for r in out["table"]}
    # the model-implied view (its own p) would rate both as attractive; labels say perfect >> bad
    assert rows["p_rf_raw"]["realized_saved"] > 3 * rows["p_bad"]["realized_saved"]
    assert rows["p_rf_raw"]["ci_lo"] <= rows["p_rf_raw"]["realized_saved"] <= rows["p_rf_raw"]["ci_hi"]
    assert rows["p_bad"]["diff_vs_base"] < 0
    assert rows["p_rf_raw"]["ece"] < rows["p_bad"]["ece"]


def test_calibration_realized_ignores_model_p_scale():
    pr, y, _ = _problem(600)
    p = np.clip(pr.p, 1e-3, 0.99)
    out = cl.calibration_experiment(pr, y, {"p_rf_raw": p, "p_scaled": p * 0.5}, 4_000.0, ACFG,
                                    15, 50, 42, 0.9)
    rows = {r["source"]: r["realized_saved"] for r in out["table"]}
    # binding budget: a constant rescaling of p is absorbed by lambda (same allocation)
    assert rows["p_scaled"] == pytest.approx(rows["p_rf_raw"], rel=1e-6)


# ------------------------------------------------------------------ sensitivity
def test_sensitivity_covers_requested_grid_and_records_rankings():
    pr, y, seg = _problem()
    levels = ACFG["sensitivity_levels"]
    out = cl.sensitivity_experiment(pr, seg, 3_000.0, levels, ACFG)
    n_groups = len(out["groups"])
    singles = [r for r in out["scenarios"] if r["kind"] == "single"]
    together = [r for r in out["scenarios"] if r["kind"] == "together"]
    assert levels == [-0.5, -0.25, 0.25, 0.5]
    assert len(singles) == n_groups * 2 * len(levels) and len(together) == 3 * len(levels)
    for r in out["scenarios"]:
        assert set(r["misspecified"]["ranking"]) == set(st.STRATEGY_NAMES)
    s = out["summary"]["misspecified"]
    assert s["n_scenarios"] == len(singles) + len(together)
    assert 0 <= s["seg_first"] <= s["n_scenarios"]


def test_sensitivity_resolved_segment_aware_is_optimal_under_own_model():
    pr, y, seg = _problem()
    out = cl.sensitivity_experiment(pr, seg, 3_000.0, [-0.5, 0.5], ACFG)
    for r in out["scenarios"]:
        assert r["resolved"]["seg_first"]                  # optimal for the model it was told


def test_sensitivity_stress_can_make_segment_aware_lose():
    pr, y, seg = _problem()
    out = cl.sensitivity_experiment(pr, seg, 3_000.0, [0.25], ACFG)
    stress = {r["param"]: r for r in out["scenarios"] if r["kind"] == "stress"}
    assert stress["reverse_a+reverse_t"]["misspecified"]["seg_vs_global"] < \
        out["scenarios"][0]["misspecified"]["seg_vs_global"]


# ------------------------------------------------------------------ rounds
def test_rounds_never_spend_more_than_budget_and_removed_get_nothing_later():
    pr, _, _ = _problem(300)
    B = 4_000.0
    for seed in range(5):
        out = rd.simulate_rounds(pr.p, pr.v, pr.a, pr.tau, B, CAP, 6, np.random.default_rng(seed))
        assert out["spent"] <= B + 1e-6
        assert sum(out["spent_by_round"]) <= B + 1e-6
        for r in range(1, 6):                          # customers gone before round r get no spend
            gone = ~out["alive_history"][r]
            assert out["x_history"][r][gone].sum() == 0.0
        cum = np.sum(out["x_history"], axis=0)
        assert (cum <= CAP + 1e-9).all()               # per-customer cap holds across rounds


def test_single_round_equals_one_shot():
    pr, _, _ = _problem(300)
    a = rd.simulate_rounds(pr.p, pr.v, pr.a, pr.tau, 4_000.0, CAP, 1, np.random.default_rng(3))
    b = rd.one_shot(pr.p, pr.v, pr.a, pr.tau, 4_000.0, CAP, np.random.default_rng(3))
    assert a["saved_value"] == pytest.approx(b["saved_value"])
    assert a["spent"] == pytest.approx(b["spent"])


def test_rounds_compare_is_seeded_and_reports_interval():
    pr, _, _ = _problem(200)
    args = (pr.p, pr.v, pr.a, pr.tau, 2_000.0, CAP, 3, 20, 42, 0.9)
    r1, r2 = rd.compare(*args), rd.compare(*args)
    assert r1 == r2
    assert r1["max_spent"] <= 2_000.0 + 1e-6
    assert r1["rounds_saved"]["lo"] <= r1["rounds_saved"]["mean"] <= r1["rounds_saved"]["hi"] + 1e-9


# ------------------------------------------------------------------ reasons
def test_explain_group_mentions_group_parameters():
    table = pd.DataFrame([{"segment_id": 1, "value_tier": "high", "engagement_class": "high",
                           "a_g": 0.36, "t_g": 0.0625},
                          {"segment_id": 2, "value_tier": "low", "engagement_class": "low",
                           "a_g": 0.24, "t_g": 0.04}])
    assert explain_group(table, 1, "high", CFG) == \
        "High-engagement, high value: responds strongly, offer sized up"
    assert explain_group(table, 2, "low", CFG) == \
        "Low-engagement, low value: responds weakly, offer sized down"
