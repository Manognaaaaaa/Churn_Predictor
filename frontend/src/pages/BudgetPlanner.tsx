import { useState } from "react";
import { useAllocate } from "../api";
import { fmtMoney } from "../lib/format";
import { Button, DataTable, KpiCard, Panel, SegmentedControl, TextInput } from "../components/ui";
import type { Column } from "../components/ui/DataTable";

const STRATEGIES = [
  { value: "segment_aware", label: "KKT segment-aware" },
  { value: "uniform", label: "Uniform split" },
  { value: "risk_proportional", label: "Risk-proportional" },
];

interface AllocRow {
  customer_id: string;
  value_tier: string;
  offer: string;
  spend: number;
  expected_revenue_saved: number;
  reason: string;
}

const COLUMNS: Column<AllocRow>[] = [
  { key: "customer_id", label: "Customer", mono: true },
  { key: "value_tier", label: "Tier", muted: true },
  { key: "offer", label: "Offer", mono: true },
  { key: "spend", label: "Spend", align: "right", render: (r) => fmtMoney(r.spend) },
  {
    key: "expected_revenue_saved", label: "Revenue saved", align: "right", tone: "green",
    render: (r) => `+${fmtMoney(r.expected_revenue_saved)}`,
  },
];

export default function BudgetPlanner() {
  const [budget, setBudget] = useState(1_000_000);
  const [strategy, setStrategy] = useState<string>("segment_aware");
  const alloc = useAllocate();

  return (
    <>
      <Panel note="Runs the step-6 KKT water-filling solver live (per-customer cap from config). Segment-aware maximises expected revenue saved under the budget constraint; the two baselines come from the step-6 comparison.">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block min-w-[220px] flex-1">
            <span className="t-label mb-1 block">Budget</span>
            <TextInput
              type="number"
              min={1000}
              step={10000}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
          </label>
          <div>
            <span className="t-label mb-1 block">Strategy</span>
            <SegmentedControl label="Allocation strategy" options={STRATEGIES} value={strategy} onChange={setStrategy} />
          </div>
          <Button variant="primary" onClick={() => alloc.mutate({ budget, strategy })} disabled={alloc.isPending}>
            {alloc.isPending ? "Optimising…" : "Run allocation"}
          </Button>
        </div>
      </Panel>

      {alloc.isError && <p className="text-red">Allocation failed: {(alloc.error as Error).message}</p>}

      {alloc.data && (
        <>
          <div className="grid-kpi-3">
            <KpiCard label="Budget" value={alloc.data.budget} />
            <KpiCard label="Spent" value={alloc.data.spent} />
            <KpiCard label="Expected revenue saved" value={alloc.data.expected_revenue_saved} tone="positive" />
          </div>
          <DataTable columns={COLUMNS} rows={alloc.data.allocations as AllocRow[]} rowKey="customer_id" />
        </>
      )}
    </>
  );
}
