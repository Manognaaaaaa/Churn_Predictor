import {
  Line, LineChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useMetrics } from "../api";
import { fmtMetric, fmtMoney, fmtPct } from "../lib/format";
import { chartColors, tooltipStyle } from "../lib/theme";
import { DataTable, KpiCard, Panel } from "../components/ui";
import type { Column } from "../components/ui/DataTable";

const MODEL_LABELS: Record<string, string> = {
  logreg_mle: "Logistic (MLE)",
  logreg_map: "Logistic (MAP)",
  naive_bayes: "Naive Bayes",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lstm: "LSTM",
};

const MODEL_ORDER = ["logreg_mle", "logreg_map", "naive_bayes", "random_forest", "xgboost", "lstm"];

interface ModelRow {
  name: string;
  label: string;
  pr_auc: string;
  brier: string;
  ece: string;
}

const COLUMNS: Column<ModelRow>[] = [
  { key: "label", label: "Model" },
  { key: "pr_auc", label: "PR-AUC", align: "right" },
  { key: "brier", label: "Brier", align: "right" },
  { key: "ece", label: "ECE", align: "right" },
];

export default function ModelData() {
  const metrics = useMetrics();
  if (metrics.isLoading) return <p className="msg">Loading…</p>;
  if (metrics.error) return <p className="msg">API unavailable. Is `make api` running?</p>;

  const c = chartColors();
  const axis = { fill: c.axis, fontSize: 10 };
  const m = metrics.data!;
  const models = (m.models ?? []) as {
    name: string;
    valid_pr_auc?: number;
    valid_brier?: number;
    valid_ece?: number;
  }[];
  models.sort((a, b) => MODEL_ORDER.indexOf(a.name) - MODEL_ORDER.indexOf(b.name));
  const rows: ModelRow[] = models.map((mo) => ({
    name: mo.name,
    label: MODEL_LABELS[mo.name] ?? mo.name,
    pr_auc: fmtPct(mo.valid_pr_auc),
    brier: fmtMetric(mo.valid_brier),
    ece: fmtMetric(mo.valid_ece),
  }));

  const test = m.test ?? {};
  const thr = m.threshold ?? {};
  const curve = (m.calibration_curve ?? []) as { bin_mean_pred: number; bin_frac_pos: number; n: number }[];
  const curveData = curve.map((p) => ({ pred: p.bin_mean_pred, observed: p.bin_frac_pos }));

  return (
    <>
      <div className="grid-kpi">
        <KpiCard label="Best model" value={MODEL_LABELS[m.best_model] ?? m.best_model ?? "–"} />
        <KpiCard label="Calibration" value={m.calibration ?? "–"} />
        <KpiCard label="Test PR-AUC (calibrated)" value={fmtPct(test.pr_auc_calibrated)} />
        <KpiCard label="Test Brier (calibrated)" value={fmtMetric(test.brier_calibrated)} />
      </div>

      <div className="grid-2">
        <div className="min-w-0">
          <h2 className="t-panel-title mb-3">Model comparison (validation)</h2>
          <DataTable columns={COLUMNS} rows={rows} rowKey="name" highlightKey={m.best_model} />
        </div>

        <Panel
          title="Calibration curve (test)"
          note="Isotonic calibration maps raw scores to observed churn frequencies (11 test bins)."
        >
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={curveData}>
              <CartesianGrid stroke={c.grid} />
              <XAxis dataKey="pred" type="number" domain={[0, 1]} tick={axis} stroke={c.axis} tickFormatter={(v) => fmtPct(v)} />
              <YAxis domain={[0, 1]} tick={axis} stroke={c.axis} tickFormatter={(v) => fmtPct(v)} />
              <Tooltip {...tooltipStyle()} formatter={(v) => fmtPct(Number(v))} />
              <Legend wrapperStyle={{ color: c.inkMuted }} />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={c.interval} strokeDasharray="4 4" />
              <Line dataKey="observed" stroke={c.forecast} strokeWidth={2} dot={{ r: 3, fill: c.forecast, stroke: c.forecast }} name="Observed churn rate" />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title="Operating point"
        note={`Raw vs calibrated test: PR-AUC ${fmtPct(test.pr_auc_raw)} → ${fmtPct(test.pr_auc_calibrated)} · Brier ${fmtMetric(test.brier_raw)} → ${fmtMetric(test.brier_calibrated)} · ECE ${fmtPct(test.ece_raw)} → ${fmtPct(test.ece_calibrated)}`}
      >
        <div className="grid gap-1">
          <div>
            Cost-optimal threshold: <span className="t-metric">{fmtMetric(thr.threshold, 3)}</span> (offer cost 10% of customer value, uplift 30%)
          </div>
          <div>
            Flagged customers: <span className="t-metric">{fmtMoney(thr.n_flagged)}</span> · minimised cost:{" "}
            <span className="t-metric">{fmtMoney(thr.cost)}</span>
          </div>
        </div>
      </Panel>
    </>
  );
}
