import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useForecast, usePortfolio } from "../api";
import { fmtMoney } from "../lib/format";
import { chartColors, tooltipStyle } from "../lib/theme";
import { KpiCard, Panel, SegmentedControl } from "../components/ui";

const SCENARIOS = [
  { value: "no_intervention", label: "No intervention" },
  { value: "with_allocation", label: "With allocation" },
];
const BAND_ORDER = ["green", "amber", "red"];

export default function Overview() {
  const [scenario, setScenario] = useState("no_intervention");
  const portfolio = usePortfolio();
  const forecast = useForecast(scenario);

  if (portfolio.isLoading || forecast.isLoading) return <p className="msg">Loading…</p>;
  if (portfolio.error || forecast.error) return <p className="msg">API unavailable. Is `make api` running?</p>;

  const c = chartColors();
  const tip = tooltipStyle();
  const axis = { fill: c.axis, fontSize: 10 };
  const p = portfolio.data!;
  const bands = Object.entries(p.band_counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => BAND_ORDER.indexOf(a.name) - BAND_ORDER.indexOf(b.name));
  const bandColor: Record<string, string> = { green: c.green, amber: c.amber, red: c.red };
  const pts = forecast.data!.points.map((d) => ({
    month: d.month.slice(0, 7),
    Actual: d.actual,
    Forecast: d.forecast,
    Lower: d.lower,
    Upper: d.upper,
  }));

  return (
    <>
      <div className="grid-kpi">
        <KpiCard label="Customers" value={p.n_customers} />
        <KpiCard label="Revenue at risk" value={p.total_revenue_at_risk} />
        <KpiCard label="Red band" value={p.band_counts.red ?? 0} />
        <KpiCard label="Segments" value={p.by_segment.length} />
      </div>

      <div className="grid-2">
        <Panel title="Risk bands">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={bands} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} stroke={c.surface100}>
                {bands.map((b) => <Cell key={b.name} fill={bandColor[b.name] ?? c.purple} />)}
              </Pie>
              <Tooltip {...tip} />
              <Legend wrapperStyle={{ color: c.inkMuted }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Revenue at risk by segment">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={p.by_segment} layout="vertical">
              <XAxis type="number" tickFormatter={(v) => fmtMoney(v)} tick={axis} stroke={c.axis} />
              <YAxis type="category" dataKey="segment_name" width={140} tick={axis} stroke={c.axis} />
              <Tooltip {...tip} formatter={(v) => fmtMoney(Number(v))} cursor={{ fill: c.grid }} />
              <Bar dataKey="revenue_at_risk" fill={c.forecast} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title="Revenue at risk forecast"
        actions={<SegmentedControl label="Forecast scenario" options={SCENARIOS} value={scenario} onChange={setScenario} />}
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={pts}>
            <CartesianGrid stroke={c.grid} />
            <XAxis dataKey="month" tick={axis} stroke={c.axis} />
            <YAxis tickFormatter={(v) => fmtMoney(v)} tick={axis} stroke={c.axis} />
            <Tooltip {...tip} formatter={(v) => fmtMoney(Number(v))} />
            <Legend wrapperStyle={{ color: c.inkMuted }} />
            <Line dataKey="Actual" stroke={c.actual} strokeWidth={1.5} dot={false} />
            <Line dataKey="Forecast" stroke={c.forecast} strokeWidth={2} dot={false} />
            <Line dataKey="Lower" stroke={c.interval} strokeDasharray="4 4" dot={false} />
            <Line dataKey="Upper" stroke={c.interval} strokeDasharray="4 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>
    </>
  );
}
