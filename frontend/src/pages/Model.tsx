import { useMetrics } from "../api";
import { fixed, full, pct1 } from "../lib/format";
import { DrawnChart } from "../components/DrawnChart";
import { Message, Skeleton } from "../components/bits";

const MODEL_LABELS: Record<string, string> = {
  logreg_mle: "Logistic regression (MLE)",
  logreg_map: "Logistic regression (MAP)",
  naive_bayes: "Naive Bayes",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lstm: "LSTM",
};
const ORDER = Object.keys(MODEL_LABELS);

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="panel" style={{ padding: "16px 18px" }}>
      <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 300, letterSpacing: "-0.04em" }}>{value}</div>
      {note && <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>{note}</div>}
    </div>
  );
}

function Compare({ label, before, after, fmt }: { label: string; before: number; after: number; fmt: (n: number) => string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr) minmax(0,1fr)", gap: 12, padding: "10px 0", borderBottom: "1px solid var(--line)", fontSize: 14 }}>
      <span style={{ color: "var(--ink-soft)" }}>{label}</span>
      <span style={{ textAlign: "right", color: "var(--ink-muted)" }}>{fmt(before)}</span>
      <span style={{ textAlign: "right", fontWeight: 600 }}>{fmt(after)}</span>
    </div>
  );
}

export default function Model() {
  const metrics = useMetrics();
  if (metrics.isLoading)
    return (
      <div style={{ padding: "56px clamp(16px, 3.4vw, 48px)", display: "flex", flexDirection: "column", gap: 20 }} aria-busy="true">
        <Skeleton w={420} h={44} /><Skeleton h={90} r={16} /><Skeleton h={260} r={16} />
      </div>
    );
  if (metrics.error || !metrics.data) return <Message>Model results could not be loaded. Check that the API is running, then reload.</Message>;

  const m = metrics.data;
  const test = m.test ?? {};
  const thr = m.threshold ?? {};
  const rows = [...(m.models ?? [])].sort((a, b) => ORDER.indexOf(a.name) - ORDER.indexOf(b.name));
  const curve = (m.calibration_curve ?? []).map((p) => ({ x: p.bin_mean_pred, y: p.bin_frac_pos, n: p.n }));
  const gapPts = test.ece_calibrated != null ? Math.max(1, Math.round(test.ece_calibrated * 100)) : null;
  const leak = m.leakage_check;
  const share = (d: { quantiles: Record<string, number>; n_eq_1: number }) => d.n_eq_1;

  return (
    <div style={{ padding: "56px clamp(16px, 3.4vw, 48px)", display: "flex", flexDirection: "column", gap: 28 }}>
      <div>
        <div style={{ color: "var(--blue-200)", fontWeight: 500, fontSize: 13 }}>Model</div>
        <h1 style={{ margin: "6px 0 0", fontWeight: 600, fontSize: "clamp(28px, 4.6vw, 40px)", lineHeight: 1.12, letterSpacing: "-0.04em", maxWidth: 820 }}>
          The model ranks customers well, and its percentages are close to what really happened{gapPts ? `, within about ${gapPts} points` : ""}.
        </h1>
        <p style={{ marginTop: 10, color: "var(--ink-muted)", maxWidth: 720 }}>
          Yearly value is the customer's estimated salary from the dataset. Every chance of leaving on this site is out-of-fold: each customer is scored by a model that never saw whether they left.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <Stat label="Best model" value={MODEL_LABELS[m.best_model] ?? m.best_model ?? "–"} />
        <Stat label="Calibration" value={m.calibration ?? "–"} />
        <Stat label="Test PR-AUC (calibrated)" value={pct1(test.pr_auc_calibrated)} />
        <Stat label="Test Brier (calibrated)" value={fixed(test.brier_calibrated)} />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
        <section className="panel" style={{ flex: "1 1 420px", minWidth: 0, padding: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>Model comparison (validation)</h2>
          <div style={{ overflowX: "auto", marginTop: 8 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 380 }}>
              <thead><tr><th className="th">Model</th><th className="th" style={{ textAlign: "right" }}>PR-AUC</th><th className="th" style={{ textAlign: "right" }}>Brier</th><th className="th" style={{ textAlign: "right" }}>ECE</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const best = r.name === m.best_model;
                  return (
                    <tr key={r.name} style={best ? { color: "var(--blue-100)", fontWeight: 600 } : undefined}>
                      <td className="td">{MODEL_LABELS[r.name] ?? r.name}{best && <span style={{ fontSize: 11, marginLeft: 8, padding: "2px 8px", borderRadius: 999, background: "rgba(var(--blue-500-rgb), .3)" }}>Best</span>}</td>
                      <td className="td" style={{ textAlign: "right" }}>{pct1(r.valid_pr_auc)}</td>
                      <td className="td" style={{ textAlign: "right" }}>{fixed(r.valid_brier)}</td>
                      <td className="td" style={{ textAlign: "right" }}>{fixed(r.valid_ece)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 10 }}>PR-AUC: how well real leavers sit at the top of the list (higher is better). Brier and ECE: how far the percentages are from what happened (lower is better).</p>
        </section>

        <section className="panel" style={{ flex: "1 1 460px", minWidth: 0, padding: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>Do the percentages match reality?</h2>
          <p style={{ fontSize: 13, color: "var(--ink-muted)", margin: "4px 0 10px" }}>Held-out test customers, grouped into bins. Points close to the dashed line mean the percentages can be taken at face value.</p>
          {curve.length ? (
            <DrawnChart points={curve} xLabel="Predicted chance of leaving" yLabel="Share who actually left" lineName="Our model" refName="Perfect match" label="Predicted chance of leaving against the share who actually left, held-out test customers" />
          ) : <Message>No calibration data yet.</Message>}
        </section>
      </div>

      <section className="panel" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>Operating point</h2>
        <p style={{ marginTop: 8, lineHeight: "24px" }}>
          Cost-optimal threshold <b>{fixed(thr.threshold, 3)}</b> (an offer costs 10% of customer value and cuts the chance of leaving by 30%). At that level the model flags <b>{full(thr.n_flagged)}</b> customers on the validation set, with a minimised total cost of <b>{full(thr.cost)}</b>.
        </p>
        <p style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 8 }}>
          Raw vs calibrated on test: PR-AUC {pct1(test.pr_auc_raw)} to {pct1(test.pr_auc_calibrated)}, Brier {fixed(test.brier_raw)} to {fixed(test.brier_calibrated)}, ECE {pct1(test.ece_raw)} to {pct1(test.ece_calibrated)}.
        </p>
      </section>

      <section className="panel" style={{ padding: 24 }} aria-labelledby="leak-title">
        <h2 id="leak-title" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>Leakage check</h2>
        {leak ? (
          <>
            <p style={{ fontSize: 14, color: "var(--ink-soft)", margin: "8px 0 14px", maxWidth: 760 }}>
              The first version scored every customer with a model fitted on 70% of them, so those customers looked more certain than they should. Customers who really left showed as 100%. Scores are now out-of-fold ({leak.method}).
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr) minmax(0,1fr)", gap: 12, fontSize: 13, color: "var(--ink-muted)", paddingBottom: 6, borderBottom: "1px solid var(--line)" }}>
              <span /><span style={{ textAlign: "right" }}>Before (in-sample)</span><span style={{ textAlign: "right" }}>After (out-of-fold)</span>
            </div>
            <Compare label="Customers shown at 99% or more" before={leak.before.distribution.n_eq_1} after={share(leak.after.distribution)} fmt={full} />
            <Compare label="High-risk customers" before={leak.before.distribution.band_counts.red} after={leak.after.distribution.band_counts.red} fmt={full} />
            <Compare label="Median chance of leaving" before={leak.before.distribution.quantiles.p50} after={leak.after.distribution.quantiles.p50} fmt={(n) => `${(n * 100).toFixed(1)}%`} />
            <Compare label="Top 10% most at risk start at" before={leak.before.distribution.quantiles.p90} after={leak.after.distribution.quantiles.p90} fmt={(n) => `${(n * 100).toFixed(0)}%`} />
            <Compare label="PR-AUC on the 7,000 training customers" before={leak.before.train_in_sample.pr_auc} after={leak.after.train_rows_oof.pr_auc} fmt={pct1} />
            <Compare label="PR-AUC on the held-out test customers" before={leak.before.test_holdout.pr_auc} after={leak.after.test_rows_oof.pr_auc} fmt={pct1} />
            <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 10 }}>
              In-sample, the training customers scored a PR-AUC of {pct1(leak.before.train_in_sample.pr_auc)} while held-out customers scored {pct1(leak.before.test_holdout.pr_auc)}. Out-of-fold, both groups score about the same, which is what an honest score looks like.
            </p>
          </>
        ) : <Message>The leakage check has not been run. Run the out-of-fold step of the pipeline.</Message>}
      </section>
    </div>
  );
}
