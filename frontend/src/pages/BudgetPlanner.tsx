import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { allocate } from "../api";
import { fmtMoney } from "../lib/format";
import { chartColors, cssVar, tooltipStyle } from "../lib/theme";
import { CUSTOMER_CURRENCY, GLOSSARY, money, offerLabel } from "../lib/plain";
import { useSegmentLabel } from "../lib/usePlain";
import { useViewMode } from "../lib/viewMode";
import { useSession } from "../lib/session";
import { Button, DataTable, Headline, InfoTip, Key, KpiCard, Panel, SegmentedControl, TextInput } from "../components/ui";
import type { Column } from "../components/ui/DataTable";

const STRATEGY_KEYS = ["segment_aware", "uniform", "risk_proportional"] as const;
const ANALYST_LABELS: Record<string, string> = {
  segment_aware: "KKT segment-aware",
  uniform: "Uniform split",
  risk_proportional: "Risk-proportional",
};
const MANAGER_LABELS: Record<string, string> = {
  segment_aware: "Best return (recommended)",
  uniform: "Same amount for everyone",
  risk_proportional: "Most at-risk first",
};
const MANAGER_TIPS: Record<string, string> = {
  segment_aware: GLOSSARY.bestReturn,
  uniform: GLOSSARY.sameAmount,
  risk_proportional: GLOSSARY.mostAtRisk,
};
const CHIPS = [
  { label: "250K", value: 250_000 },
  { label: "500K", value: 500_000 },
  { label: "1M", value: 1_000_000 },
  { label: "2M", value: 2_000_000 },
];
const PAGE = 50;

interface AllocRow {
  customer_id: string;
  segment_name?: string;
  value_tier: string;
  offer: string;
  spend: number;
  expected_revenue_saved: number;
  reason: string;
}
interface AllocResult {
  budget: number;
  spent: number;
  expected_revenue_saved: number;
  n_targeted: number;
  allocations: AllocRow[];
}
interface RunResult {
  strategy: string;
  budget: number;
  chosen: AllocResult;
  saved: Record<string, number>;
}

function csv(rows: AllocRow[], label: (s?: string | null) => string): string {
  const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
  const head = ["customer_id", "group", "offer", "cost", "revenue_kept"];
  const lines = rows.map((r) =>
    [r.customer_id, label(r.segment_name), offerLabel(r.offer), r.spend, r.expected_revenue_saved].map(esc).join(","),
  );
  return [head.join(","), ...lines].join("\n");
}

export default function BudgetPlanner() {
  const { isManager } = useViewMode();
  const { setLastAllocation } = useSession();
  const segLabel = useSegmentLabel();
  const [budget, setBudget] = useState(1_000_000);
  const [strategy, setStrategy] = useState<string>("segment_aware");
  const [rows, setRows] = useState(PAGE);

  // Runs the chosen strategy and the other two in parallel so the headline can compare them.
  const run = useMutation({
    mutationFn: async ({ budget, strategy }: { budget: number; strategy: string }): Promise<RunResult> => {
      const all = await Promise.all(STRATEGY_KEYS.map((s) => allocate(budget, s) as Promise<AllocResult>));
      const byKey = Object.fromEntries(STRATEGY_KEYS.map((s, i) => [s, all[i]]));
      return {
        strategy,
        budget,
        chosen: byKey[strategy],
        saved: Object.fromEntries(STRATEGY_KEYS.map((s) => [s, byKey[s].expected_revenue_saved])),
      };
    },
    onSuccess: (r) =>
      setLastAllocation({ budget: r.budget, spent: r.chosen.spent, expected_revenue_saved: r.chosen.expected_revenue_saved }),
  });

  const res = run.data;
  const a = res?.chosen;
  const c = chartColors();
  const labels = isManager ? MANAGER_LABELS : ANALYST_LABELS;
  const roi = a && a.spent > 0 ? a.expected_revenue_saved / a.spent : 0;
  const even = res?.saved.uniform;
  const vsEven = a && even && res.strategy !== "uniform" ? a.expected_revenue_saved / even - 1 : null;

  const columns: Column<AllocRow>[] = isManager
    ? [
        { key: "customer_id", label: "Customer", mono: true },
        { key: "segment_name", label: <>Group<InfoTip text={GLOSSARY.group} /></>, muted: true, render: (r) => segLabel(r.segment_name) },
        { key: "offer", label: "Offer", render: (r) => offerLabel(r.offer) },
        { key: "spend", label: `Cost (${CUSTOMER_CURRENCY})`, align: "right", render: (r) => fmtMoney(r.spend) },
        {
          key: "expected_revenue_saved", label: `Revenue kept (${CUSTOMER_CURRENCY})`, align: "right", tone: "green",
          render: (r) => `+${fmtMoney(r.expected_revenue_saved)}`,
        },
      ]
    : [
        { key: "customer_id", label: "Customer", mono: true },
        { key: "value_tier", label: "Tier", muted: true },
        { key: "offer", label: "Offer", mono: true },
        { key: "spend", label: "Spend", align: "right", render: (r) => fmtMoney(r.spend) },
        {
          key: "expected_revenue_saved", label: "Revenue saved", align: "right", tone: "green",
          render: (r) => `+${fmtMoney(r.expected_revenue_saved)}`,
        },
      ];

  const download = () => {
    if (!a) return;
    const url = URL.createObjectURL(new Blob([csv(a.allocations, segLabel)], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "retention-offers.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const chart = res && (
    <Panel title="Revenue saved by strategy" note={`Expected revenue saved in ${CUSTOMER_CURRENCY} for the same budget. The strategy you chose is gold.`}>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart
          data={STRATEGY_KEYS.map((s) => ({ key: s, name: labels[s].replace(" (recommended)", ""), value: res.saved[s] }))}
          layout="vertical"
          margin={{ right: 56 }}
        >
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={isManager ? 170 : 130} tickLine={false} axisLine={false} tick={{ fill: c.inkMuted, fontSize: 12 }} />
          <Tooltip {...tooltipStyle()} cursor={{ fill: c.grid }} formatter={(v) => `${CUSTOMER_CURRENCY}${fmtMoney(Number(v))}`} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {STRATEGY_KEYS.map((s) => <Cell key={s} fill={s === res.strategy ? cssVar("--gold") : c.forecast} />)}
            <LabelList dataKey="value" position="right" formatter={(v: number) => money(v)} fill={c.ink} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );

  return (
    <>
      {a && (
        <Headline>
          Spending <Key>{money(a.spent)}</Key> is expected to keep <Key>{money(a.expected_revenue_saved)}</Key> of revenue, a return
          of <Key>{roi.toFixed(1)}x</Key>.
          {vsEven != null && Math.abs(vsEven) >= 0.005 && (
            <>
              {" "}
              That is <Key>{Math.round(Math.abs(vsEven) * 100)}%</Key> {vsEven > 0 ? "more" : "less"} than spreading the budget evenly.
            </>
          )}
        </Headline>
      )}
      <Panel
        note={
          isManager
            ? MANAGER_TIPS[strategy]
            : "Runs the step-6 KKT water-filling solver live (per-customer cap from config). Segment-aware maximises expected revenue saved under the budget constraint; the two baselines come from the step-6 comparison."
        }
      >
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="block">
              <span className="t-label mb-1 block">
                {isManager ? `Budget to spend on retention offers (${CUSTOMER_CURRENCY})` : "Budget"}
              </span>
              {isManager ? (
                <TextInput
                  inputMode="numeric"
                  value={budget ? budget.toLocaleString("en-US") : ""}
                  onChange={(e) => setBudget(Number(e.target.value.replace(/\D/g, "")))}
                />
              ) : (
                <TextInput type="number" min={1000} step={10000} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
              )}
            </label>
            {isManager && (
              <div className="mt-2 flex flex-wrap gap-1">
                {CHIPS.map((ch) => (
                  <button
                    key={ch.label}
                    type="button"
                    onClick={() => setBudget(ch.value)}
                    className={`rounded-pill border px-3 py-[2px] text-[13px] ${
                      budget === ch.value ? "border-cyan-soft bg-cyan-soft text-cyan" : "border-line-100 text-ink-muted hover:text-ink"
                    }`}
                  >
                    {ch.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <span className="t-label mb-1 block">
              {isManager ? "How to spend it" : "Strategy"}
              {isManager && <InfoTip text={MANAGER_TIPS[strategy]} />}
            </span>
            <SegmentedControl
              label="Allocation strategy"
              options={STRATEGY_KEYS.map((s) => ({ value: s, label: labels[s] }))}
              value={strategy}
              onChange={setStrategy}
            />
          </div>
          <Button variant="primary" onClick={() => run.mutate({ budget, strategy })} disabled={run.isPending || budget < 1}>
            {run.isPending ? (isManager ? "Working…" : "Optimising…") : isManager ? "Show the plan" : "Run allocation"}
          </Button>
        </div>
      </Panel>

      {run.isError && <p className="text-red">Allocation failed: {(run.error as Error).message}</p>}

      {a && (
        <>
          <div className={isManager ? "grid-kpi" : "grid-kpi-3"}>
            <KpiCard label="Budget" value={isManager ? money(a.budget) : a.budget} />
            <KpiCard label="Spent" value={isManager ? money(a.spent) : a.spent} />
            <KpiCard
              label="Expected revenue saved"
              info={isManager ? <InfoTip text={GLOSSARY.saved} /> : undefined}
              value={isManager ? money(a.expected_revenue_saved) : a.expected_revenue_saved}
              tone="positive"
            />
            {isManager && <KpiCard label="Return on budget" info={<InfoTip text={GLOSSARY.returnOnBudget} />} value={`${roi.toFixed(1)}x`} />}
          </div>
          {chart}
          <DataTable
            columns={columns}
            rows={isManager ? a.allocations.slice(0, rows) : a.allocations}
            rowKey="customer_id"
            footer={
              isManager && (
                <span className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    Showing {Math.min(rows, a.allocations.length)} of {fmtMoney(a.n_targeted)} customers who get an offer
                    {a.allocations.length < a.n_targeted && `. The list holds the ${fmtMoney(a.allocations.length)} with the most revenue kept`}.
                  </span>
                  <span className="flex gap-2">
                    {rows < a.allocations.length && (
                      <Button variant="ghost" onClick={() => setRows((n) => n + PAGE)}>Show more</Button>
                    )}
                    <Button onClick={download}>Download list (CSV)</Button>
                  </span>
                </span>
              )
            }
          />
        </>
      )}
    </>
  );
}
