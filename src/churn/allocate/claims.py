"""Claim experiments: strategy comparison (claim 2), calibration vs ranking (claim 1), sensitivity."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from churn.allocate import solver as sv
from churn.allocate import strategies as st
from churn.allocate.evaluate import bootstrap_ci
from churn.models.metrics import brier, ece, pr_auc


# ---------------------------------------------------------------- claim 2: strategies
def strategy_table(pr: st.Problem, y: np.ndarray, budget: float, acfg: dict) -> dict:
    """Per strategy: continuous and offer-snapped evaluation at the same budget."""
    out = {}
    for name in st.STRATEGY_NAMES:
        x = st.allocate(name, pr, budget)
        snap = st.allocate_snapped(name, pr, budget, acfg)
        out[name] = {"continuous": st.evaluate(pr, x, y, acfg["min_spend"]),
                     "snapped": st.evaluate(pr, snap["spend"], y, acfg["min_spend"])}
    return out


def realized_paired_bootstrap(pr: st.Problem, y: np.ndarray, budget: float, a_name: str,
                              b_name: str, n_boot: int, seed: int, level: float) -> dict:
    """Bootstrap CI (over customers) of realized saved(a_name) - realized saved(b_name), fixed spends."""
    def per_customer(name: str) -> np.ndarray:
        x = st.allocate(name, pr, budget)
        return y * sv.expected_saved(x, np.ones_like(pr.p), pr.v, pr.a, pr.tau)

    diff = per_customer(a_name) - per_customer(b_name)
    mean, lo, hi = bootstrap_ci(diff, n_boot, seed, level)
    return {"a": a_name, "b": b_name, "diff": mean, "lo": lo, "hi": hi, "level": level}


def budget_sweep(pr: st.Problem, y: np.ndarray, budgets: list[float], scale: float,
                 acfg: dict) -> list[dict]:
    """Expected saved revenue per strategy over a grid of portfolio budgets (scaled to the split)."""
    rows = []
    for B in budgets:
        b = B * scale
        for name in st.STRATEGY_NAMES:
            x = st.allocate(name, pr, b)
            snap = st.allocate_snapped(name, pr, b, acfg)
            rows.append({"portfolio_budget": B, "split_budget": b, "strategy": name,
                         "saved_continuous": st.evaluate(pr, x)["expected_revenue_saved"],
                         "saved_snapped": st.evaluate(pr, snap["spend"])["expected_revenue_saved"],
                         "spend_snapped": float(snap["spend"].sum())})
    return rows


# ---------------------------------------------------------------- claim 1: calibration
def calibration_experiment(pr: st.Problem, y: np.ndarray, probs: dict[str, np.ndarray],
                           budget: float, acfg: dict, ece_bins: int, n_boot: int, seed: int,
                           level: float) -> dict:
    """Allocate with each probability source, score by REALIZED saved revenue (true labels).

    realized = sum_i y_i v_i a_i (1 - exp(-x_i / tau_i)): the actual outcome, not any model's p.
    The response parameters (a, tau) are the same assumed ones for every source; only the
    probabilities used to choose spend differ.
    """
    y = np.asarray(y, int)
    rows = []
    for name, p in probs.items():
        p = np.asarray(p, float)
        pr_s = replace(pr, p=p)
        x = st.allocate("segment_aware_kkt", pr_s, budget)
        per_cust = y * sv.expected_saved(x, np.ones_like(p), pr.v, pr.a, pr.tau)
        mean, lo, hi = bootstrap_ci(per_cust, n_boot, seed, level)
        snap = st.allocate_snapped("segment_aware_kkt", pr_s, budget, acfg)
        rows.append({"source": name, "pr_auc": pr_auc(y, p), "brier": brier(y, p),
                     "ece": ece(y, p, ece_bins), "realized_saved": mean, "ci_lo": lo, "ci_hi": hi,
                     "realized_saved_snapped": float(
                         (y * sv.expected_saved(snap["spend"], np.ones_like(p), pr.v, pr.a,
                                                pr.tau)).sum()),
                     "n_targeted": int((x >= acfg["min_spend"]).sum())})
    base = "p_rf_raw" if "p_rf_raw" in probs else next(iter(probs))
    xs = {n: st.allocate("segment_aware_kkt", replace(pr, p=np.asarray(p, float)), budget)
          for n, p in probs.items()}
    pc = {n: y * sv.expected_saved(x, np.ones(len(y)), pr.v, pr.a, pr.tau) for n, x in xs.items()}
    for r in rows:
        d, lo, hi = bootstrap_ci(pc[r["source"]] - pc[base], n_boot, seed, level)
        r.update({"diff_vs_base": d, "diff_lo": lo, "diff_hi": hi, "base": base})
    df = pd.DataFrame(rows)
    corr = {}
    for col in ("ece", "brier", "pr_auc"):
        rho = spearmanr(df[col], df["realized_saved"])[0] if len(df) > 2 else float("nan")
        corr[col] = float(rho)
    return {"table": rows, "spearman_vs_realized": corr, "level": level, "n_boot": n_boot}


# ---------------------------------------------------------------- sensitivity
def _group_index(pr: st.Problem, seg_ids: np.ndarray) -> tuple[np.ndarray, list[tuple[int, str]]]:
    keys = list(zip(seg_ids.tolist(), pr.tiers.tolist()))
    uniq = sorted(set(keys))
    lookup = {k: i for i, k in enumerate(uniq)}
    return np.array([lookup[k] for k in keys]), uniq


def sensitivity_experiment(pr: st.Problem, seg_ids: np.ndarray, budget: float,
                           levels: list[float], acfg: dict) -> dict:
    """Perturb each a_g and t_g (one at a time) and all together by `levels` (e.g. -50%...+50%).

    Two readings, both recorded:
    - misspecified: the world is perturbed but every strategy still plans with its nominal
      assumptions (what we believe today). Allocations stay fixed; evaluation changes. This is the
      informative robustness test.
    - resolved: the segment-aware solver is told the perturbed group parameters and re-solves.
      (global_kkt keeps its single global curve.) Segment-aware is optimal under its own model,
      so staying first here is close to automatic; the margin is what is informative.
    """
    gidx, groups = _group_index(pr, seg_ids)
    nominal = {n: st.allocate(n, pr, budget) for n in st.STRATEGY_NAMES}

    def evaluate_all(x_by: dict[str, np.ndarray], a: np.ndarray, tau: np.ndarray) -> dict:
        return {n: float(sv.expected_saved(x, pr.p, pr.v, a, tau).sum()) for n, x in x_by.items()}

    scenarios = [{"param": "none", "group": "all", "level": 0.0, "kind": "nominal"}]
    for level in levels:
        for param in ("a", "t"):
            for g in range(len(groups)):
                scenarios.append({"param": param, "group": g, "level": level, "kind": "single"})
        for param in ("a", "t", "a+t"):
            scenarios.append({"param": param, "group": "all", "level": level, "kind": "together"})

    # extra stress test (not in the +-% grid): the assumed heterogeneity is exactly backwards
    for param in ("reverse_a", "reverse_t", "reverse_a+reverse_t"):
        scenarios.append({"param": param, "group": "all", "level": 0.0, "kind": "stress"})

    rows = []
    for sc in scenarios:
        fa = np.ones(len(pr.p))
        ft = np.ones(len(pr.p))
        mask = np.ones(len(pr.p), bool) if sc["group"] == "all" else (gidx == sc["group"])
        if sc["kind"] == "stress":
            a_s, tau_s = pr.a.copy(), pr.tau.copy()
            if "reverse_a" in sc["param"]:
                a_s = 2 * pr.a_glob - pr.a                     # mirror a_g around the global a
            if "reverse_t" in sc["param"]:
                tau_s = pr.tau_glob ** 2 / pr.tau              # invert the tier ratio t_g / t
        else:
            if "a" in sc["param"].split("+"):
                fa[mask] = 1 + sc["level"]
            if "t" in sc["param"].split("+"):
                ft[mask] = 1 + sc["level"]
            a_s, tau_s = pr.a * fa, pr.tau * ft
        mis = evaluate_all(nominal, a_s, tau_s)                     # misspecified
        pr_s = replace(pr, a=a_s, tau=tau_s)
        resolved_x = dict(nominal)
        resolved_x["segment_aware_kkt"] = st.allocate("segment_aware_kkt", pr_s, budget)
        res = evaluate_all(resolved_x, a_s, tau_s)

        def summarize(vals: dict) -> dict:
            ranking = sorted(vals, key=vals.get, reverse=True)
            return {"ranking": ranking, "seg_first": ranking[0] == "segment_aware_kkt",
                    "seg_beats_global": vals["segment_aware_kkt"] >= vals["global_kkt"],
                    "seg_vs_global": vals["segment_aware_kkt"] / vals["global_kkt"] - 1}

        row = {**sc, "group_label": ("all" if sc["group"] == "all" else
                                      f"seg{groups[sc['group']][0]}/{groups[sc['group']][1]}"),
               "misspecified": {**summarize(mis), "saved": mis},
               "resolved": {**summarize(res), "saved": res}}
        rows.append(row)

    def counts(kind: str) -> dict:
        sub = [r for r in rows if r["kind"] in ("single", "together")]
        return {"n_scenarios": len(sub),
                "seg_first": int(sum(r[kind]["seg_first"] for r in sub)),
                "seg_loses_to_global": int(sum(not r[kind]["seg_beats_global"] for r in sub)),
                "min_seg_vs_global": float(min(r[kind]["seg_vs_global"] for r in sub)),
                "max_seg_vs_global": float(max(r[kind]["seg_vs_global"] for r in sub))}

    return {"groups": [list(map(str, g)) for g in groups], "levels": levels, "scenarios": rows,
            "summary": {"misspecified": counts("misspecified"), "resolved": counts("resolved")}}
