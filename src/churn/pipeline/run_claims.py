"""Step 8 entrypoint: `make claims` — claim 2 strategies, claim 1 calibration, sensitivity, rounds."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from churn.allocate import claims as cl
from churn.allocate import rounds as rd
from churn.allocate.evaluate import load_eval_problem, load_test_probs
from churn.allocate.report import write_report
from churn.config import ROOT, ensure_dirs, load_config


def _plot_sweep(rows: list[dict], path) -> None:
    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, col, title in [(axes[0], "saved_continuous", "Continuous spend"),
                           (axes[1], "saved_snapped", "After offer snapping")]:
        for name, g in df.groupby("strategy", sort=False):
            ax.plot(g["portfolio_budget"], g[col], marker="o", ms=3, label=name,
                    ls="--" if name == "global_kkt" else "-")
        ax.set_xscale("log")
        ax.set_xlabel("portfolio budget (EUR; test split uses its population share)")
        ax.set_title(title)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("expected revenue saved (test split)")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_calibration(cal: dict, path) -> None:
    df = pd.DataFrame(cal["table"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, col, label in [(axes[0], "ece", "ECE (lower = better calibrated)"),
                           (axes[1], "pr_auc", "PR-AUC (higher = better ranking)")]:
        ax.errorbar(df[col], df["realized_saved"],
                    yerr=[df["realized_saved"] - df["ci_lo"], df["ci_hi"] - df["realized_saved"]],
                    fmt="o", capsize=3)
        for _, r in df.iterrows():
            ax.annotate(r["source"].replace("p_", ""), (r[col], r["realized_saved"]),
                        fontsize=7, xytext=(4, 4), textcoords="offset points")
        ax.set_xlabel(label)
        ax.grid(alpha=0.3)
        rho = cal["spearman_vs_realized"][col]
        ax.set_title(f"Spearman rho = {rho:+.2f} (n={len(df)}, not significant)", fontsize=9)
    axes[0].set_ylabel(f"realized saved revenue ({cal['level']:.0%} bootstrap CI)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_sensitivity(sens: dict, path) -> None:
    rows = [r for r in sens["scenarios"] if r["kind"] == "single"]
    levels = sens["levels"]
    labels = [f"{p} {g}" for p in ("a", "t") for g in sorted({r["group_label"] for r in rows})]
    mat = np.full((len(labels), len(levels)), np.nan)
    idx = {l: i for i, l in enumerate(labels)}
    for r in rows:
        mat[idx[f"{r['param']} {r['group_label']}"], levels.index(r["level"])] = \
            r["misspecified"]["seg_vs_global"]
    fig, ax = plt.subplots(figsize=(5.5, 11))
    im = ax.imshow(mat * 100, aspect="auto", cmap="RdYlGn", vmin=-5, vmax=25)
    ax.set_xticks(range(len(levels)), [f"{l:+.0%}" for l in levels])
    ax.set_yticks(range(len(labels)), labels, fontsize=6)
    ax.set_title("segment-aware vs global KKT, % (misspecified, one param at a time)", fontsize=8)
    fig.colorbar(im, shrink=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _sensitivity_summary(sens: dict) -> dict:
    """Compact view for the report/API: together-scenarios in full, singles aggregated."""
    together = [{"param": r["param"], "level": r["level"],
                 "misspecified_ranking": r["misspecified"]["ranking"],
                 "misspecified_seg_vs_global": r["misspecified"]["seg_vs_global"],
                 "resolved_seg_vs_global": r["resolved"]["seg_vs_global"]}
                for r in sens["scenarios"] if r["kind"] == "together"]
    singles = pd.DataFrame([{"param": r["param"], "level": r["level"],
                             "seg_vs_global": r["misspecified"]["seg_vs_global"]}
                            for r in sens["scenarios"] if r["kind"] == "single"])
    agg = singles.groupby(["param", "level"])["seg_vs_global"].agg(["min", "mean", "max"]).reset_index()
    nominal = next(r for r in sens["scenarios"] if r["kind"] == "nominal")
    stress = [{"param": r["param"], "ranking": r["misspecified"]["ranking"],
               "seg_vs_global": r["misspecified"]["seg_vs_global"]}
              for r in sens["scenarios"] if r["kind"] == "stress"]
    return {"summary": sens["summary"], "stress": stress, "nominal_seg_vs_global": nominal["misspecified"]["seg_vs_global"],
            "together": together, "singles_by_param_level": agg.to_dict("records"),
            "levels": sens["levels"]}


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    art, acfg = ROOT / cfg["paths"]["artifacts"], cfg["allocation"]
    figs = ROOT / cfg["paths"]["reports"] / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    seed, n_boot, level = cfg["seed"], acfg["bootstrap_resamples"], acfg["bootstrap_level"]
    pr, y, frame, scale = load_eval_problem(cfg, acfg["eval_split"])
    budget = float(cfg["budget"]["total"]) * scale

    # ---- 8.3 strategies (claim 2)
    table = cl.strategy_table(pr, y, budget, acfg)
    diff = cl.realized_paired_bootstrap(pr, y, budget, "segment_aware_kkt", "global_kkt",
                                        n_boot, seed, level)
    sweep = cl.budget_sweep(pr, y, acfg["budget_sweep"], scale, acfg)
    _plot_sweep(sweep, figs / "strategy_vs_budget.png")
    strategy = {"split": acfg["eval_split"], "n_customers": int(len(y)), "budget": budget,
                "portfolio_budget": float(cfg["budget"]["total"]), "budget_scale": scale,
                "strategy_table": table, "seg_vs_global_realized": diff, "sweep": sweep}

    # ---- 8.4 calibration vs ranking (claim 1), labels as truth
    probs = load_test_probs(cfg, frame)
    cal = cl.calibration_experiment(pr, y, probs, budget, acfg,
                                    cfg["models"]["calibration"]["ece_bins"], n_boot, seed, level)
    _plot_calibration(cal, figs / "calibration_vs_ranking.png")

    # ---- 8.5 sensitivity
    sens = cl.sensitivity_experiment(pr, frame["segment_id"].to_numpy(), budget,
                                     acfg["sensitivity_levels"], acfg)
    _plot_sensitivity(sens, figs / "sensitivity_heatmap.png")
    sens_summary = _sensitivity_summary(sens)

    # ---- 8.6 reallocation rounds
    rounds = rd.compare(pr.p, pr.v, pr.a, pr.tau, budget, pr.cap, acfg["rounds"],
                        acfg["rounds_seeds"], seed, acfg["rounds_interval"])

    (art / "claims_strategy.json").write_text(json.dumps(strategy, indent=2, default=float))
    (art / "claims_calibration.json").write_text(json.dumps(cal, indent=2, default=float))
    (art / "claims_sensitivity.json").write_text(json.dumps(sens, indent=2, default=float))
    (art / "claims_rounds.json").write_text(json.dumps(rounds, indent=2, default=float))
    summary = {"split": acfg["eval_split"], "budget": budget, "portfolio_budget": strategy["portfolio_budget"],
               "strategy_table": table, "seg_vs_global_realized": diff, "budget_sweep": sweep,
               "calibration": cal, "sensitivity": sens_summary, "rounds": rounds}
    (art / "allocation_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    write_report(cfg)

    print(f"{acfg['eval_split']} split: n={len(y)}, budget {budget:,.0f}")
    for k, d in table.items():
        c, s = d["continuous"], d["snapped"]
        print(f"  {k:24s} cont {c['expected_revenue_saved']:>9,.0f} | snapped "
              f"{s['expected_revenue_saved']:>9,.0f} | realized {c['realized_revenue_saved']:>9,.0f}")
    print(f"realized seg-aware minus global: {diff['diff']:,.0f} [{diff['lo']:,.0f}, {diff['hi']:,.0f}]")
    print(pd.DataFrame(cal["table"]).round(4).to_string(index=False))
    print("spearman vs realized:", {k: round(v, 2) for k, v in cal["spearman_vs_realized"].items()})
    print("sensitivity:", sens["summary"])
    print(f"rounds: {rounds['rounds_saved']['mean']:,.0f} vs one-shot {rounds['one_shot_saved']['mean']:,.0f}; "
          f"diff {rounds['difference']}")


if __name__ == "__main__":
    main()
