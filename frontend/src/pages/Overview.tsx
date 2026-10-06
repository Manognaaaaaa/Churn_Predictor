import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmtMoney, useForecast, usePortfolio } from "../api";

const BAND_COLORS: Record<string, string> = { green: "#22c55e", amber: "#f59e0b", red: "#ef4444" };

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}

export default function Overview() {
  const [scenario, setScenario] = useState("no_intervention");
  const portfolio = usePortfolio();
  const forecast = useForecast(scenario);

  if (portfolio.isLoading || forecast.isLoading) return <p className="text-slate-400">Loading…</p>;
  if (portfolio.error || forecast.error) return <p className="text-red-400">API unavailable – is `make api` running?</p>;

  const p = portfolio.data!;
  const bands = Object.entries(p.band_counts).map(([name, value]) => ({ name, value }));
  const pts = forecast.data!.points.map((d) => ({
    month: d.month.slice(0, 7),
    Actual: d.actual,
    Forecast: d.forecast,
    Lower: d.lower,
    Upper: d.upper,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi label="Customers" value={fmtMoney(p.n_customers)} />
        <Kpi label="Revenue at risk" value={fmtMoney(p.total_revenue_at_risk)} />
        <Kpi label="Red band" value={fmtMoney(p.band_counts.red ?? 0)} />
        <Kpi label="Segments" value={fmtMoney(p.by_segment.length)} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 font-medium">Risk bands</h2>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={bands} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}>
                {bands.map((b) => <Cell key={b.name} fill={BAND_COLORS[b.name] ?? "#64748b"} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 font-medium">Revenue at risk by segment</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={p.by_segment} layout="vertical">
              <XAxis type="number" tickFormatter={(v) => fmtMoney(v)} />
              <YAxis type="category" dataKey="segment_name" width={140} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v) => fmtMoney(Number(v))} />
              <Bar dataKey="revenue_at_risk" fill="#38bdf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-medium">Revenue at risk forecast</h2>
          <div className="flex gap-2 text-sm">
            {["no_intervention", "with_allocation"].map((s) => (
              <button key={s} onClick={() => setScenario(s)}
                className={`px-3 py-1 rounded ${scenario === s ? "bg-sky-600" : "bg-slate-800 text-slate-300"}`}>
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={pts}>
            <CartesianGrid stroke="#1e293b" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => fmtMoney(v)} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v) => fmtMoney(Number(v))} />
            <Legend />
            <Line dataKey="Actual" stroke="#e2e8f0" dot={false} />
            <Line dataKey="Forecast" stroke="#38bdf8" dot={false} />
            <Line dataKey="Lower" stroke="#475569" dot={false} strokeDasharray="4 4" />
            <Line dataKey="Upper" stroke="#475569" dot={false} strokeDasharray="4 4" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
