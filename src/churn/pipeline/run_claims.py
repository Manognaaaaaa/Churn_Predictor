"""Step 8 entrypoint: `make claims` — claim 2 strategy comparison, budget sweep (Phase 8.3)."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from churn.allocate import claims as cl
from churn.allocate.evaluate import load_eval_problem
from churn.allocate.report import write_report
from churn.config import ROOT, ensure_dirs, load_config


def _plot_sweep(rows: list[dict], path) -> None:
    import pandas as pd
    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, col, title in [(axes[0], "saved_continuous", "Continuous spend"),
                           (axes[1], "saved_snapped", "After offer snapping")]:
        for name, g in df.groupby("strategy", sort=False):
            ax.plot(g["portfolio_budget"], g[col], marker="o", ms=3, label=name)
        ax.set_xscale("log")
        ax.set_xlabel("portfolio budget (EUR; test split uses its population share)")
        ax.set_title(title)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("expected revenue saved (test split)")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    art, acfg = ROOT / cfg["paths"]["artifacts"], cfg["allocation"]
    pr, y, frame, scale = load_eval_problem(cfg, acfg["eval_split"])
    budget = float(cfg["budget"]["total"]) * scale

    table = cl.strategy_table(pr, y, budget, acfg)
    diff = cl.realized_paired_bootstrap(pr, y, budget, "segment_aware_kkt", "global_kkt",
                                        acfg["bootstrap_resamples"], cfg["seed"],
                                        acfg["bootstrap_level"])
    sweep = cl.budget_sweep(pr, y, acfg["budget_sweep"], scale, acfg)
    fig_path = ROOT / cfg["paths"]["reports"] / "figures" / "strategy_vs_budget.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    _plot_sweep(sweep, fig_path)

    results = {"split": acfg["eval_split"], "n_customers": int(len(y)), "budget": budget,
               "portfolio_budget": float(cfg["budget"]["total"]), "budget_scale": scale,
               "strategy_table": table, "seg_vs_global_realized": diff, "sweep": sweep}
    path = art / "claims_strategy.json"
    path.write_text(json.dumps(results, indent=2, default=float))
    write_report(cfg)

    print(f"{acfg['eval_split']} split: n={len(y)}, budget {budget:,.0f}")
    for k, d in table.items():
        c, s = d["continuous"], d["snapped"]
        print(f"  {k:24s} cont saved {c['expected_revenue_saved']:>9,.0f} | "
              f"snapped {s['expected_revenue_saved']:>9,.0f} (spend {s['spend']:,.0f})")
    print(f"realized seg-aware minus global: {diff['diff']:,.0f} "
          f"[{diff['lo']:,.0f}, {diff['hi']:,.0f}] ({diff['level']:.0%} CI)")


if __name__ == "__main__":
    main()
