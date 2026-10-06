import { useState } from "react";
import { fmtMoney, useAllocate } from "../api";

const STRATEGIES = ["segment_aware", "uniform", "risk_proportional"] as const;
const LABELS: Record<string, string> = {
  segment_aware: "KKT segment-aware",
  uniform: "Uniform split",
  risk_proportional: "Risk-proportional",
};

interface AllocRow {
  customer_id: string;
  value_tier: string;
  offer: string;
  spend: number;
  expected_revenue_saved: number;
  reason: string;
}

export default function BudgetPlanner() {
  const [budget, setBudget] = useState(1_000_000);
  const [strategy, setStrategy] = useState<string>("segment_aware");
  const alloc = useAllocate();

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 space-y-3">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="text-sm flex-1 min-w-56">
            <span className="block text-xs uppercase tracking-wide text-slate-400 mb-1">Budget</span>
            <input
              type="number"
              min={1000}
              step={10000}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-3 py-1.5 text-sm outline-none focus:border-sky-600"
            />
          </label>
          <div className="flex gap-1 text-sm">
            {STRATEGIES.map((s) => (
              <button
                key={s}
                onClick={() => setStrategy(s)}
                className={`px-3 py-1.5 rounded-md ${strategy === s ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"}`}
              >
                {LABELS[s]}
              </button>
            ))}
          </div>
          <button
            onClick={() => alloc.mutate({ budget, strategy })}
            disabled={alloc.isPending}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded-md"
          >
            {alloc.isPending ? "Optimising…" : "Run allocation"}
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Runs the step-6 KKT water-filling solver live (per-customer cap from config). Segment-aware maximises
          expected revenue saved under the budget constraint; the two baselines come from the step-6 comparison.
        </p>
      </div>

      {alloc.isError && (
        <p className="text-red-400 text-sm">Allocation failed: {(alloc.error as Error).message}</p>
      )}

      {alloc.data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Kpi label="Budget" value={fmtMoney(alloc.data.budget)} />
            <Kpi label="Spent" value={fmtMoney(alloc.data.spent)} />
            <Kpi
              label="Expected revenue saved"
              value={fmtMoney(alloc.data.expected_revenue_saved)}
              highlight
            />
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="text-left px-3 py-2">Customer</th>
                  <th className="text-left px-3 py-2">Tier</th>
                  <th className="text-left px-3 py-2">Offer</th>
                  <th className="text-right px-3 py-2">Spend</th>
                  <th className="text-right px-3 py-2">Saved</th>
                </tr>
              </thead>
              <tbody>
                {(alloc.data.allocations as AllocRow[]).map((a) => (
                  <tr key={a.customer_id} className="border-b border-slate-800/50">
                    <td className="px-3 py-1.5 font-mono text-xs">{a.customer_id}</td>
                    <td className="px-3 py-1.5 text-slate-300">{a.value_tier}</td>
                    <td className="px-3 py-1.5">{a.offer}</td>                    <td className="px-3 py-1.5 text-right">{fmtMoney(a.spend)}</td>
                    <td className="px-3 py-1.5 text-right text-green-300">+{fmtMoney(a.expected_revenue_saved)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded-lg border p-4 ${highlight ? "border-green-500/40 bg-green-500/10" : "border-slate-800 bg-slate-950"}`}>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
