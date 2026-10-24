"""Builds reports/allocation.md from artifacts (allocate + claims pipelines both call this)."""
from __future__ import annotations

import json

import pandas as pd

from churn.config import ROOT


def _read_json(path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _strategy_section(res: dict) -> list[str]:
    rows = []
    for name, d in res["strategy_table"].items():
        for mode in ("continuous", "snapped"):
            m = d[mode]
            rows.append({"strategy": name, "spend mode": mode, "spend": m["spend"],
                         "expected saved": m["expected_revenue_saved"],
                         "targeted": m["n_targeted"], "saved per spend": m["saved_per_spend"],
                         "realized saved (labels)": m["realized_revenue_saved"]})
    df = pd.DataFrame(rows)
    d = res["seg_vs_global_realized"]
    st = res["strategy_table"]
    seg, glob = (st["segment_aware_kkt"]["continuous"]["expected_revenue_saved"],
                 st["global_kkt"]["continuous"]["expected_revenue_saved"])
    return [f"## Strategy comparison on the {res['split']} split (claim 2)", "",
            f"{res['n_customers']} customers, budget {res['budget']:,.0f} "
            f"(= portfolio budget {res['portfolio_budget']:,.0f} x population share "
            f"{res['budget_scale']:.2f}). All strategies are scored with the same segment-aware "
            "response model; `global_kkt` solves with one global a and t instead. "
            "*Continuous* = solved spend; *snapped* = after offer matching and budget re-balancing. "
            "*Realized saved* uses the true churn labels (one realisation, noisy).", "",
            df.round(3).to_markdown(index=False), "",
            f"Segment-aware vs global KKT (continuous): {seg:,.0f} vs {glob:,.0f} expected saved "
            f"({(seg / glob - 1):+.2%}). Realized difference {d['diff']:,.0f}, "
            f"{d['level']:.0%} bootstrap CI [{d['lo']:,.0f}, {d['hi']:,.0f}] over customers.", "",
            "![strategy vs budget](figures/strategy_vs_budget.png)", ""]


def _calibration_section(cal: dict) -> list[str]:
    df = pd.DataFrame(cal["table"])
    show = df[["source", "pr_auc", "brier", "ece", "realized_saved", "ci_lo", "ci_hi",
               "diff_vs_base", "diff_lo", "diff_hi", "realized_saved_snapped"]].round(4)
    corr = cal["spearman_vs_realized"]
    base = df["base"].iloc[0]
    all_zero = bool(((df["diff_lo"] <= 0) & (df["diff_hi"] >= 0)).all())
    cal_better = abs(corr["brier"]) > abs(corr["pr_auc"]) and abs(corr["ece"]) > abs(corr["pr_auc"])
    smote = df[df["source"] == "p_rf_smote_raw"].iloc[0]
    nb = df[df["source"] == "p_naive_bayes_raw"].iloc[0]
    rf = df[df["source"] == base].iloc[0]
    return ["## Calibration vs ranking on the test split (claim 1)", "",
            "Each probability source drives `segment_aware_kkt` at the same budget; the allocation is "
            "then scored by **realized** saved revenue, sum of y_i v_i a_i (1 - exp(-x_i / tau_i)), "
            "using the true churn labels (not any model's probability). Response parameters are the "
            f"same assumed ones for every source. CIs are {cal['level']:.0%} bootstrap intervals "
            f"({cal['n_boot']} resamples of test customers, spends held fixed). `diff_vs_base` is the "
            f"paired difference against `{base}`.", "",
            show.to_markdown(index=False), "",
            f"Spearman correlation with realized saved revenue (n = {len(df)}; no significance claimed): "
            f"ECE {corr['ece']:+.2f}, Brier {corr['brier']:+.2f}, PR-AUC {corr['pr_auc']:+.2f}.", "",
            "![calibration vs ranking](figures/calibration_vs_ranking.png)", "",
            "**Reading.**",
            f"- Paired differences against `{base}` all have intervals containing zero: {all_zero}. "
            "The data cannot separate the sources on realized savings.",
            f"- ECE and Brier correlate with realized saved revenue more strongly than PR-AUC does: "
            f"{cal_better}. With six points this is suggestive only, and Brier mixes ranking and "
            "calibration, so it cannot isolate calibration.",
            f"- The deliberately miscalibrated RF+SMOTE (ECE {smote['ece']:.3f} vs {rf['ece']:.3f}) changes "
            f"realized savings by {smote['realized_saved'] - rf['realized_saved']:+,.0f} relative to RF raw "
            f"(paired CI [{smote['diff_lo']:,.0f}, {smote['diff_hi']:,.0f}]).",
            f"- Naive Bayes changes realized savings by {nb['realized_saved'] - rf['realized_saved']:+,.0f} but also ranks much worse "
            f"(PR-AUC {nb['pr_auc']:.2f} vs {rf['pr_auc']:.2f}), so its loss cannot be attributed to calibration.",
            "- Why calibration has little room to matter here: when the budget binds, the KKT spend is "
            "x_i = tau_i ln(p_i a_i / (t_g lambda)). Multiplying every p_i by a constant is absorbed by "
            "lambda, so a pure scale error (Platt or raw vs isotonic of the same ranking) changes nothing; "
            "only distortions that change the relative p across customers matter, and those are ranking "
            "effects. Calibration would matter more for decisions about *whether* to spend at all "
            "(a fixed ROI threshold), which a fixed-budget allocation does not make.", ""]


def _sensitivity_section(sens: dict) -> list[str]:
    summ = sens["summary"]
    m, r = summ["misspecified"], summ["resolved"]
    together = pd.DataFrame(sens["together"])
    together["first_misspecified"] = together["misspecified_ranking"].apply(lambda x: x[0])
    together = together.drop(columns=["misspecified_ranking"]).round(4)
    singles = pd.DataFrame(sens["singles_by_param_level"]).round(4)
    stress = pd.DataFrame(sens["stress"])
    stress["first"] = stress["ranking"].apply(lambda x: x[0])
    stress = stress.drop(columns=["ranking"]).round(4)
    return ["## Sensitivity: +-25% and +-50% on every a_g and t_g (Phase 8.5)", "",
            "Each of the 24 group parameters of a and of t is varied one at a time (-50, -25, +25, +50%), "
            "and all together (a, t, both); 204 scenarios. Two readings:", "",
            "- *misspecified*: the world is perturbed but every strategy plans with its nominal "
            "assumptions (our current beliefs). This is the informative robustness test.",
            "- *resolved*: the segment-aware solver is told the perturbed parameters. It is optimal under "
            "its own model, so staying first is nearly automatic; only the margin is informative.", "",
            f"Misspecified: segment-aware is first in **{m['seg_first']} of {m['n_scenarios']}** scenarios and "
            f"loses to global KKT in **{m['seg_loses_to_global']}**; its margin over global KKT ranges "
            f"{m['min_seg_vs_global']:+.1%} to {m['max_seg_vs_global']:+.1%} (nominal "
            f"{sens['nominal_seg_vs_global']:+.1%}). Resolved: first in {r['seg_first']} of "
            f"{r['n_scenarios']}, margin {r['min_seg_vs_global']:+.1%} to {r['max_seg_vs_global']:+.1%}.", "",
            "All-together scenarios (segment-aware vs global KKT, relative margin):", "",
            together.to_markdown(index=False), "",
            "One-at-a-time scenarios aggregated over the 24 groups (misspecified margin, min / mean / max):", "",
            singles.to_markdown(index=False), "",
            "![sensitivity heatmap](figures/sensitivity_heatmap.png)", "",
            "**Stress test outside the requested grid** (assumed heterogeneity exactly backwards: "
            "a_g mirrored around the global a, and/or the tier ratio t_g / t inverted):", "",
            stress.to_markdown(index=False), "",
            "Reading: within +-50% perturbations the segment-aware plan keeps its lead because the "
            "*direction* of the assumed heterogeneity is unchanged. If the direction itself is wrong "
            "(tier effect on t reversed) it falls behind global KKT. The advantage rests on the "
            "assumed ordering of segments and tiers, which this data cannot verify.", ""]


def _rounds_section(rd: dict) -> list[str]:
    d = rd["difference"]
    lvl = f"{rd['level']:.0%}"
    return [f"## Reallocation rounds vs one-shot ({rd['rounds']} monthly rounds, {rd['n_seeds']} seeds)", "",
            "Simulation on the test split (see `src/churn/allocate/rounds.py` for assumptions): the "
            "horizon churn probability is split into per-round hazards; each round solves the "
            "incremental KKT problem on the remaining customers with pool / (rounds left); churned "
            "and saved customers leave and their unspent share stays in the pool; offer effects "
            "depend on cumulative spend and persist. One-shot allocates the same total budget up front.", "",
            f"| | mean saved | {lvl} interval |", "|---|---:|---|",
            f"| rounds | {rd['rounds_saved']['mean']:,.0f} | [{rd['rounds_saved']['lo']:,.0f}, {rd['rounds_saved']['hi']:,.0f}] |",
            f"| one-shot | {rd['one_shot_saved']['mean']:,.0f} | [{rd['one_shot_saved']['lo']:,.0f}, {rd['one_shot_saved']['hi']:,.0f}] |",
            f"| paired difference (rounds - one-shot) | {d['mean']:,.0f} (SE {d['mean_se']:,.0f}) | [{d['lo']:,.0f}, {d['hi']:,.0f}] |", "",
            f"Rounds beat one-shot in {d['share_seeds_rounds_better']:.0%} of seeds. Mean spend: rounds "
            f"{rd['rounds_spent_mean']:,.0f}, one-shot {rd['one_shot_spent_mean']:,.0f}; the largest total over "
            f"any run was {rd['max_spent']:,.2f} against a budget of {rd['budget']:,.0f}.", "",
            "Reading: in this model rounds do **not** beat a single up-front allocation. Only 1/6 of the "
            "budget is available in round 1, so customers are protected later, after some have already "
            "churned, while the benefit of re-allocating money away from removed customers is small "
            "(only a few percent of customers leave per round). Single-seed outcomes are very noisy (each "
            "saved customer is worth ~100k), hence the wide per-seed intervals; the mean difference is "
            f"{abs(d['mean'] / d['mean_se']):.1f} standard errors from zero. Rounds would pay off if the "
            "offer effect expired each round or if risk scores were refreshed with new information, "
            "neither of which is modelled.", ""]


def write_report(cfg: dict) -> None:
    art = ROOT / cfg["paths"]["artifacts"]
    base = _read_json(art / "allocation_report.json")
    if base is None:
        return
    table = pd.read_parquet(art / "group_params.parquet")
    snap, g = base["offer_snapping"], base["gradient_check"]
    docs = ROOT / "docs"
    lines = ["# Allocation report", "",
             "## Response-curve groups (segment x value tier)", "",
             (docs / "response_curve_rule.md").read_text(encoding="utf-8"), "",
             table.round(4).to_markdown(index=False), "",
             (docs / "allocation_derivation.md").read_text(encoding="utf-8"), ""]
    claims = _read_json(art / "claims_strategy.json")
    if claims:
        lines += _strategy_section(claims)
    cal = _read_json(art / "claims_calibration.json")
    if cal:
        lines += _calibration_section(cal)
    summary = _read_json(art / "allocation_summary.json")
    if summary:
        lines += _sensitivity_section(summary["sensitivity"])
        lines += _rounds_section(summary["rounds"])
    lines += ["## Production plan and offer matching (stage 2)", "",
              f"Portfolio budget {base['budget']:,.0f} {base['currency']} on all customers: "
              f"{base['allocated_customers']} targeted, {snap['snapped_spend']:,.0f} spent. "
              f"Continuous KKT would save {snap['continuous_saved']:,.0f}; after snapping to the "
              f"catalog (re-balanced in {snap['iterations']} rounds, effective stage-1 budget "
              f"{snap['effective_budget']:,.0f}) it saves {snap['snapped_saved']:,.0f}.", "",
              pd.Series(snap["offer_counts"]).rename("customers").to_frame().to_markdown(), "",
              "## KKT vs dual ascent", "",
              f"- KKT objective (continuous spend): {g['kkt_objective']:,.0f}",
              f"- Dual-ascent objective: {g['gradient_objective']:,.0f} (gap {g['rel_gap']:.3%})", "",
              "## Assumptions",
              "- Response curves and offer costs/eligibility are assumptions, not measured uplift."]
    (ROOT / cfg["paths"]["reports"] / "allocation.md").write_text("\n".join(lines), encoding="utf-8")
