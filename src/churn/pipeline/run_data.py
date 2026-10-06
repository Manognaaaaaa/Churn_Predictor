"""Step 2 entrypoint: `make data` -> ingest + label + EDA report."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant

from churn.config import ROOT, dataset_cfg, ensure_dirs, load_config
from churn.data import ingest, label


def _figures(df: pd.DataFrame, ds: dict, outdir) -> list[str]:
    cfg = load_config()
    seed_fig = ROOT / cfg["paths"]["reports"]
    outdir.mkdir(parents=True, exist_ok=True)
    made = []

    cats = [c for c in ds["categorical"] if c in df.columns]
    for c in cats:
        rates = df.groupby(c)["churned"].mean().sort_values()
        fig, ax = plt.subplots(figsize=(6, 3.5))
        rates.plot.barh(ax=ax, color="#c0504d")
        ax.set_title(f"Churn rate by {c}")
        ax.set_xlabel("churn rate")
        fig.tight_layout()
        p = outdir / f"churn_by_{c}.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        made.append(p.name)

    if "Age" in df.columns:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for lab, grp in df.groupby("churned"):
            grp["Age"].plot.hist(bins=30, alpha=0.5, ax=ax,
                                 label=f"churned={lab}", density=True)
        ax.set_title("Age distribution by churn")
        ax.legend()
        fig.tight_layout()
        p = outdir / "age_by_churn.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        made.append(p.name)

    num = [c for c in ds["numeric"] if c in df.columns] + ["churned"]
    corr = df[num].corr()
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(num)), num, rotation=90, fontsize=7)
    ax.set_yticks(range(len(num)), num, fontsize=7)
    fig.colorbar(im, shrink=0.8)
    ax.set_title("Correlation matrix")
    fig.tight_layout()
    p = outdir / "correlation.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    made.append(p.name)
    return made


def _vif_table(df: pd.DataFrame, ds: dict) -> pd.DataFrame:
    num = [c for c in ds["numeric"] if c in df.columns and df[c].std() > 1e-12]
    x = add_constant(df[num].astype(float))
    rows = []
    for i, col in enumerate(x.columns):
        if col == "const":
            continue
        rows.append({"feature": col, "VIF": float(variance_inflation_factor(x.values, i))})
    return pd.DataFrame(rows).sort_values("VIF", ascending=False)


def main() -> None:
    cfg = load_config()
    ds = dataset_cfg(cfg)
    ensure_dirs(cfg)

    raw = ingest.load_raw(cfg)
    checks = ingest.schema_checks(raw, cfg)
    std = ingest.standardize(raw, cfg)
    labeled = label.static_labels(std)

    processed = ROOT / cfg["paths"]["processed"]
    labeled.to_parquet(processed / "labeled.parquet", index=False)

    fig_dir = ROOT / cfg["paths"]["reports"] / "figures"
    figs = _figures(labeled, ds, fig_dir)
    vif = _vif_table(labeled, ds)

    lines = ["# EDA report", "",
             f"Dataset: `{ds['path']}` ({checks['n_rows']} rows, "
             f"{checks['n_unique_ids']} unique customers)",
             f"Churn rate: **{checks['churn_rate']:.1%}** | null cells: {checks['n_null_cells']}", "",
             "## Churn rate by category", ""]
    for c in ds["categorical"]:
        if c in labeled.columns:
            rates = labeled.groupby(c)["churned"].mean().sort_values(ascending=False)
            lines.append(f"- **{c}**: " + ", ".join(f"{k} {v:.1%}" for k, v in rates.items()))
    lines += ["", "## VIF (collinearity)", "", vif.round(2).to_markdown(index=False), "",
              "## Figures", ""]
    lines += [f"![{f}](figures/{f})" for f in figs]
    lines += ["", "## Engagement co-occurrence", ""]
    if {"IsActiveMember", "NumOfProducts"} <= set(labeled.columns):
        cc = labeled.groupby("IsActiveMember")["NumOfProducts"].mean()
        lines.append(f"- Mean products held: active={cc.get(1, float('nan')):.2f}, "
                     f"inactive={cc.get(0, float('nan')):.2f}")
        for flag in (0, 1):
            sub = labeled[labeled["IsActiveMember"] == flag]
            lines.append(f"- Churn among IsActiveMember={flag}: {sub['churned'].mean():.1%}")
    lines += ["", "Note: dataset has no timestamps; the temporal co-occurrence test from the "
              "README plan is replaced by the static engagement comparison above."]
    (ROOT / cfg["paths"]["reports"] / "eda.md").write_text("\n".join(lines))

    print(f"labeled.parquet: {len(labeled)} rows, churn={checks['churn_rate']:.1%}")
    print(f"EDA report + {len(figs)} figures written to reports/")


if __name__ == "__main__":
    main()
