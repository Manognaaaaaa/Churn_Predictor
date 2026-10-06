import {
  Line, LineChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmtMoney, useMetrics } from "../api";

const MODEL_LABELS: Record<string, string> = {
  logreg_mle: "Logistic (MLE)",
  logreg_map: "Logistic (MAP)",
  naive_bayes: "Naive Bayes",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lstm: "LSTM",
};

const MODEL_ORDER = ["logreg_mle", "logreg_map", "naive_bayes", "random_forest", "xgboost", "lstm"];

function pct(x: number | undefined): string {
  return x == null ? "–" : `${(100 * x).toFixed(1)}%`;
}

export default function ModelData() {
  const metrics = useMetrics();
  if (metrics.isLoading) return <p className="text-slate-400">Loading…</p>;
  if (metrics.error) return <p className="text-red-400">API unavailable – is `make api` running?</p>;

  const m = metrics.data!;
  const models = (m.models ?? []) as {
    name: string;
    valid_pr_auc?: number;
    valid_brier?: number;
    valid_ece?: number;
  }[];
  models.sort((a, b) => (MODEL_ORDER.indexOf(a.name) ?? 99) - (MODEL_ORDER.indexOf(b.name) ?? 99));

  const test = m.test ?? {};
  const thr = m.threshold ?? {};
  const curve = (m.calibration_curve ?? []) as {
    bin_mean_pred: number;
    bin_frac_pos: number;
    n: number;
  }[];
  const curveData = curve.map((c) => ({
    pred: c.bin_mean_pred,
    observed: c.bin_frac_pos,
    perfect: c.bin_mean_pred,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi label="Best model" value={MODEL_LABELS[m.best_model] ?? m.best_model ?? "–"} />
        <Kpi label="Calibration" value={m.calibration ?? "–"} />
        <Kpi label="Test PR-AUC (calibrated)" value={pct(test.pr_auc_calibrated)} />
        <Kpi label="Test Brier (calibrated)" value={test.brier_calibrated == null ? "–" : test.brier_calibrated.toFixed(4)} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 font-medium">Model comparison (validation)</h2>
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-800">
              <tr>
                <th className="text-left px-2 py-1.5">Model</th>
                <th className="text-right px-2 py-1.5">PR-AUC</th>
                <th className="text-right px-2 py-1.5">Brier</th>
                <th className="text-right px-2 py-1.5">ECE</th>
              </tr>
            </thead>
            <tbody>
              {models.map((mo) => (
                <tr
                  key={mo.name}
                  className={`border-b border-slate-800/50 ${mo.name === m.best_model ? "text-sky-300 font-medium" : ""}`}
                >
                  <td className="px-2 py-1.5">{MODEL_LABELS[mo.name] ?? mo.name}</td>
                  <td className="px-2 py-1.5 text-right">{pct(mo.valid_pr_auc)}</td>
                  <td className="px-2 py-1.5 text-right">{mo.valid_brier?.toFixed(4)}</td>
                  <td className="px-2 py-1.5 text-right">{mo.valid_ece?.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 font-medium">Calibration curve (test)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={curveData}>
              <CartesianGrid stroke="#1e293b" />
              <XAxis dataKey="pred" type="number" domain={[0, 0.6]} tick={{ fontSize: 10 }} tickFormatter={(v) => pct(v)} />
              <YAxis domain={[0, 0.6]} tickFormatter={(v) => pct(v)} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v) => pct(Number(v))} />
              <Legend />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 0.6, y: 0.6 }]} stroke="#64748b" strokeDasharray="4 4" />
              <Line dataKey="observed" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3 }} name="Observed churn rate" />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-slate-500 mt-2">
            Isotonic calibration maps raw scores to observed churn frequencies (11 test bins).
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm space-y-1">
        <h2 className="font-medium mb-1">Operating point</h2>
        <div>Cost-optimal threshold: <span className="font-mono">{thr.threshold?.toFixed(3)}</span> (offer cost 10% of customer value, uplift 30%)</div>
        <div>Flagged customers: <span className="font-mono">{fmtMoney(thr.n_flagged)}</span> · minimised cost: <span className="font-mono">{fmtMoney(thr.cost)}</span></div>
        <div className="text-xs text-slate-500">
          Raw vs calibrated test: PR-AUC {pct(test.pr_auc_raw)} → {pct(test.pr_auc_calibrated)} · Brier {test.brier_raw?.toFixed(4)} → {test.brier_calibrated?.toFixed(4)} · ECE {pct(test.ece_raw)} → {pct(test.ece_calibrated)}
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
