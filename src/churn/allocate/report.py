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


def write_report(cfg: dict) -> None:
    art = ROOT / cfg["paths"]["artifacts"]
    base = _read_json(art / "allocation_report.json")
    if base is None:
        return
    table = pd.read_parquet(art / "group_params.parquet")
    snap, g = base["offer_snapping"], base["gradient_check"]
    cvu = base["calibrated_vs_uncalibrated"]
    docs = ROOT / "docs"
    lines = ["# Allocation report", "",
             "## Response-curve groups (segment x value tier)", "",
             (docs / "response_curve_rule.md").read_text(encoding="utf-8"), "",
             table.round(4).to_markdown(index=False), "",
             (docs / "allocation_derivation.md").read_text(encoding="utf-8"), ""]
    claims = _read_json(art / "claims_strategy.json")
    if claims:
        lines += _strategy_section(claims)
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
              "## Sensitivity (interim +-30%; rebuilt in Phase 8.5)", "",
              pd.DataFrame(base["sensitivity"]).round(3).to_markdown(index=False), "",
              "## Calibrated vs uncalibrated (interim, circular; replaced in Phase 8.4)", "",
              f"Both allocations are scored with the calibrated probabilities, so calibrated wins "
              f"by construction ({cvu['saved_calibrated_allocation']:,.0f} vs "
              f"{cvu['saved_uncalibrated_allocation']:,.0f}). This does not test claim 1.", "",
              "## Assumptions",
              "- Response curves and offer costs/eligibility are assumptions, not measured uplift."]
    (ROOT / cfg["paths"]["reports"] / "allocation.md").write_text("\n".join(lines), encoding="utf-8")
