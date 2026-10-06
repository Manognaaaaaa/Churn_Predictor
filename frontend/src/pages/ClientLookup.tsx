import { useState } from "react";
import { fmtMoney, useCustomer, useCustomers } from "../api";

const BANDS = ["", "red", "amber", "green"] as const;
const BAND_CLASS: Record<string, string> = {
  red: "bg-red-500/20 text-red-300 border-red-500/40",
  amber: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  green: "bg-green-500/20 text-green-300 border-green-500/40",
};

export default function ClientLookup() {
  const [band, setBand] = useState<string>("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const customers = useCustomers(band, 500);
  const detail = useCustomer(selected);

  const items = (customers.data?.items ?? []).filter(
    (c) => !search || c.customer_id.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="grid md:grid-cols-5 gap-4">
      <div className="md:col-span-3 space-y-3">
        <div className="flex gap-2 items-center">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customer id…"
            className="bg-slate-900 border border-slate-800 rounded-md px-3 py-1.5 text-sm flex-1 outline-none focus:border-sky-600"
          />
          <div className="flex gap-1 text-sm">
            {BANDS.map((b) => (
              <button
                key={b || "all"}
                onClick={() => setBand(b)}
                className={`px-3 py-1.5 rounded-md ${band === b ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"}`}
              >
                {b || "All"}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-slate-400 border-b border-slate-800">
              <tr>
                <th className="text-left px-3 py-2">Customer</th>
                <th className="text-right px-3 py-2">P(churn)</th>
                <th className="text-left px-3 py-2">Band</th>
                <th className="text-right px-3 py-2">Rev at risk</th>
                <th className="text-left px-3 py-2">Segment</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr
                  key={c.customer_id}
                  onClick={() => setSelected(c.customer_id)}
                  className={`cursor-pointer border-b border-slate-800/50 hover:bg-slate-800/60 ${
                    selected === c.customer_id ? "bg-slate-800" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 font-mono text-xs">{c.customer_id}</td>
                  <td className="px-3 py-1.5 text-right">{(100 * c.p_churn_calibrated).toFixed(1)}%</td>
                  <td className="px-3 py-1.5">
                    <span className={`px-2 py-0.5 rounded text-xs border ${BAND_CLASS[c.risk_band] ?? ""}`}>
                      {c.risk_band}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right">{fmtMoney(c.revenue_at_risk)}</td>
                  <td className="px-3 py-1.5 text-slate-400">{c.segment_name ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {customers.data && (
            <div className="px-3 py-2 text-xs text-slate-500">
              {items.length} of {customers.data.total} customers shown (top 500 by revenue at risk)
            </div>
          )}
        </div>
      </div>

      <div className="md:col-span-2">
        {!selected && <p className="text-slate-500 text-sm">Select a customer to see their risk profile.</p>}
        {selected && detail.isLoading && <p className="text-slate-400 text-sm">Loading…</p>}
        {selected && detail.data && (
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 space-y-4">
            <div>
              <div className="font-mono text-sm">{detail.data.customer_id}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2 py-0.5 rounded text-xs border ${BAND_CLASS[detail.data.risk_band] ?? ""}`}>
                  {detail.data.risk_band}
                </span>
                <span className="text-lg font-semibold">
                  {(100 * detail.data.p_churn_calibrated).toFixed(1)}% churn
                </span>
                <span className="text-xs text-slate-500">raw {(100 * detail.data.p_churn_raw).toFixed(1)}%</span>
              </div>
              <div className="text-sm text-slate-300 mt-1">
                Revenue at risk: <span className="font-semibold">{fmtMoney(detail.data.revenue_at_risk)}</span>
              </div>
              {detail.data.segment && (
                <div className="text-xs text-slate-400 mt-1">
                  Segment: {detail.data.segment.segment_name} · {detail.data.segment.value_tier} value
                </div>
              )}
            </div>

            <div>
              <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Top churn drivers (SHAP)</h3>
              <div className="space-y-1.5">
                {detail.data.top_drivers.map((d) => (
                  <div key={d.feature}>
                    <div className="flex justify-between text-xs">
                      <span>{d.label}</span>
                      <span className={d.contribution > 0 ? "text-red-300" : "text-green-300"}>
                        {d.contribution > 0 ? "+" : ""}
                        {d.contribution.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded mt-0.5">
                      <div
                        className={`h-1.5 rounded ${d.contribution > 0 ? "bg-red-400" : "bg-green-400"}`}
                        style={{
                          width: `${Math.min(100, Math.abs(d.contribution) * 50)}%`,
                          marginLeft: d.contribution < 0 ? undefined : "50%",
                          marginRight: d.contribution < 0 ? "50%" : undefined,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {detail.data.allocation && (
              <div className="rounded border border-sky-500/30 bg-sky-500/10 p-3 text-sm">
                <div className="font-medium text-sky-300">Recommended: {detail.data.allocation.offer}</div>
                <div className="text-xs text-slate-300 mt-1">
                  Spend {fmtMoney(detail.data.allocation.spend)} → save{" "}
                  {fmtMoney(detail.data.allocation.expected_revenue_saved)}
                </div>
                <div className="text-xs text-slate-400 mt-1">{detail.data.allocation.reason}</div>
              </div>
            )}

            <a
              href={`/customers/${detail.data.customer_id}/report.pdf`}
              target="_blank"
              rel="noreferrer"
              className="inline-block bg-sky-600 hover:bg-sky-500 text-white text-sm px-4 py-2 rounded-md"
            >
              Download PDF report
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
