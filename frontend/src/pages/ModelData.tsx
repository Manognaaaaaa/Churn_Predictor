import { useState } from "react";
import {
  Line, LineChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useMetrics } from "../api";
import { fmtMetric, fmtMoney, fmtPct } from "../lib/format";
import { chartColors, tooltipStyle } from "../lib/theme";
import { GLOSSARY, MODEL_NAMES } from "../lib/plain";
import { useViewMode } from "../lib/viewMode";
import { Button, DataTable, Headline, InfoTip, Key, KpiCard, Panel } from "../components/ui";
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
const ECE_TRUST_LIMIT = 0.05;

interface ModelRow {
  name: string;
  label: string;
  pr_auc: string;
  brier: string;
  ece: string;
}

export default function ModelData() {
  const { isManager } = useViewMode();
  const metrics = useMetrics();
  const [showTable, setShowTable] = useState(false);
  if (metrics.isLoading) return <p className="msg">Loading…</p>;
  if (metrics.error)
    return (
      <p className="msg">
        {isManager ? "The data is not available. Check that the API is running." : "API unavailable. Is `make api` running?"}
      </p>
    );

  const c = chartColors();
  const axis = { fill: c.axis, fontSize: 10 };
  const m = metrics.data!;
  const names = isManager ? MODEL_NAMES : MODEL_LABELS;
  const models = (m.models ?? []) as {
    name: string;
    valid_pr_auc?: number;
    valid_brier?: number;
    valid_ece?: number;
  }[];
  models.sort((a, b) => MODEL_ORDER.indexOf(a.name) - MODEL_ORDER.indexOf(b.name));
  const rows: ModelRow[] = models.map((mo) => ({
    name: mo.name,
    label: names[mo.name] ?? mo.name,
    pr_auc: fmtPct(mo.valid_pr_auc),
    brier: fmtMetric(mo.valid_brier),
    ece: fmtMetric(mo.valid_ece),
  }));

  const columns: Column<ModelRow>[] = isManager
    ? [
        { key: "label", label: "Model" },
        { key: "pr_auc", label: <>Precision at top<InfoTip text={GLOSSARY.prAuc} /></>, align: "right" },
        { key: "brier", label: <>Error of the percentages<InfoTip text={GLOSSARY.brier} /></>, align: "right" },
        { key: "ece", label: <>Calibration gap<InfoTip text={GLOSSARY.ece} /></>, align: "right" },
      ]
    : [
        { key: "label", label: "Model" },
        { key: "pr_auc", label: "PR-AUC", align: "right" },
        { key: "brier", label: "Brier", align: "right" },
        { key: "ece", label: "ECE", align: "right" },
      ];

  const test = m.test ?? {};
  const thr = m.threshold ?? {};
  const curve = (m.calibration_curve ?? []) as { bin_mean_pred: number; bin_frac_pos: number; n: number }[];
  const curveData = curve.map((p) => ({ pred: p.bin_mean_pred, observed: p.bin_frac_pos, perfect: p.bin_mean_pred }));
  const nTest = curve.reduce((s, p) => s + p.n, 0);
  const baseRate = nTest ? curve.reduce((s, p) => s + p.n * p.bin_frac_pos, 0) / nTest : null;
  const trusted = test.ece_calibrated != null && test.ece_calibrated < ECE_TRUST_LIMIT;
  const bestName = names[m.best_model] ?? m.best_model ?? "–";

  const headline = (
    <Headline>
      The model is reliable enough to <Key>rank customers by risk</Key>.{" "}
      {trusted
        ? "When it says a customer has a 30% chance of leaving, about 30% of such customers really leave."
        : "Its percentages are approximate, so use them to rank customers, not as exact odds."}
    </Headline>
  );

  if (!isManager)
    return (
      <>
        {headline}
        <div className="grid-kpi">
          <KpiCard label="Best model" value={MODEL_LABELS[m.best_model] ?? m.best_model ?? "–"} />
          <KpiCard label="Calibration" value={m.calibration ?? "–"} />
          <KpiCard label="Test PR-AUC (calibrated)" value={fmtPct(test.pr_auc_calibrated)} />
          <KpiCard label="Test Brier (calibrated)" value={fmtMetric(test.brier_calibrated)} />
        </div>

        <div className="grid-2">
          <div className="min-w-0">
            <h2 className="t-panel-title mb-3">Model comparison (validation)</h2>
            <DataTable columns={columns} rows={rows} rowKey="name" highlightKey={m.best_model} />
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

  return (
    <>
      {headline}
      <div className="grid-2">
        <Panel title="How good is it at finding leavers?">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="t-hero">{fmtPct(test.pr_auc_calibrated)}</span>
            <span className="text-[14px] text-ink-muted">
              precision at top
              <InfoTip text={GLOSSARY.prAuc} />
            </span>
          </div>
          <p className="t-caption mt-2">
            {baseRate != null
              ? `A random list of customers would score ${fmtPct(baseRate)}, the share of customers who really left.`
              : "Higher is better."}
          </p>
        </Panel>

        <Panel title="Which model we use and why">
          <p className="m-0 text-[14px] leading-5">
            We tested {models.length} models. {bestName} was most accurate at ranking customers, so the dashboard uses it.
          </p>
          <div className="mt-2">
            <Button variant="ghost" className="!px-0" onClick={() => setShowTable((s) => !s)}>
              {showTable ? "Hide model comparison" : "Show model comparison"}
            </Button>
          </div>
        </Panel>
      </div>

      {showTable && (
        <div className="min-w-0">
          <DataTable columns={columns} rows={rows} rowKey="name" highlightKey={m.best_model} footer="Scores on customers held out during model selection." />
        </div>
      )}

      <Panel
        title="Do the percentages match reality?"
        note="Points close to the dashed line mean the percentages can be taken at face value."
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={curveData} margin={{ bottom: 18, left: 8 }}>
            <CartesianGrid stroke={c.grid} />
            <XAxis
              dataKey="pred" type="number" domain={[0, 1]} tick={axis} stroke={c.axis} tickFormatter={(v) => `${Math.round(v * 100)}%`}
              label={{ value: "Predicted chance of leaving", position: "insideBottom", offset: -10, fill: c.inkMuted, fontSize: 11 }}
            />
            <YAxis
              domain={[0, 1]} tick={axis} stroke={c.axis} tickFormatter={(v) => `${Math.round(v * 100)}%`}
              label={{ value: "Share who actually left", angle: -90, position: "insideLeft", fill: c.inkMuted, fontSize: 11 }}
            />
            <Tooltip {...tooltipStyle()} formatter={(v) => `${Math.round(Number(v) * 100)}%`} labelFormatter={(l) => `Predicted ${Math.round(Number(l) * 100)}%`} />
            <Legend verticalAlign="top" wrapperStyle={{ color: c.inkMuted }} />
            <Line dataKey="perfect" name="Perfect match" stroke={c.interval} strokeDasharray="4 4" dot={false} />
            <Line dataKey="observed" name="Our model" stroke={c.forecast} strokeWidth={2} dot={{ r: 3, fill: c.forecast, stroke: c.forecast }} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="When the model flags a customer">
        <p className="m-0 text-[14px] leading-5">
          The model flags a customer for an offer when their chance of leaving is above {Math.round((thr.threshold ?? 0) * 100)}%. At that
          level it flags {fmtMoney(thr.n_flagged)} customers and gives the lowest total cost (offer costs plus lost revenue).
        </p>
      </Panel>
    </>
  );
}
