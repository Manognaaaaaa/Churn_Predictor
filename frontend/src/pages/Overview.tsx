import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useForecast, usePortfolio } from "../api";
import type { ForecastPoint } from "../api";
import { fmtMoney } from "../lib/format";
import { chartColors, tooltipStyle } from "../lib/theme";
import { FORECAST_CURRENCY, GLOSSARY, CUSTOMER_CURRENCY, money, moneyFull, riskWord } from "../lib/plain";
import { useSegmentLabel, useNarrow } from "../lib/usePlain";
import { useViewMode } from "../lib/viewMode";
import { useSession } from "../lib/session";
import { Headline, InfoTip, Key, KpiCard, Panel, SegmentedControl } from "../components/ui";
import type { Band } from "../components/ui";

const BAND_ORDER = ["green", "amber", "red"];
const WINDOW = 4;

function weekText(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
function weekTick(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
}

function SegmentTick({ x, y, payload, max }: { x?: number; y?: number; payload?: { value: string }; max: number }) {
  const v = payload?.value ?? "";
  const text = v.length > max ? `${v.slice(0, max - 1)}…` : v;
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} fill="currentColor" className="text-ink-muted">
      <title>{v}</title>
      {text}
    </text>
  );
}

export default function Overview() {
  const { isManager } = useViewMode();
  const { openCustomers, lastAllocation } = useSession();
  const narrow = useNarrow();
  const [scenario, setScenario] = useState("no_intervention");
  const portfolio = usePortfolio();
  const doNothing = useForecast("no_intervention");
  const withBudget = useForecast("with_allocation");
  const segLabel = useSegmentLabel();
  const forecast = scenario === "no_intervention" ? doNothing : withBudget;

  if (portfolio.isLoading || doNothing.isLoading || withBudget.isLoading) return <p className="msg">Loading…</p>;
  if (portfolio.error || doNothing.error || withBudget.error)
    return (
      <p className="msg">
        {isManager ? "The data is not available. Check that the API is running." : "API unavailable. Is `make api` running?"}
      </p>
    );

  const c = chartColors();
  const tip = tooltipStyle();
  const axis = { fill: c.axis, fontSize: 10 };
  const p = portfolio.data!;
  const bands = Object.entries(p.band_counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => BAND_ORDER.indexOf(a.name) - BAND_ORDER.indexOf(b.name));
  const bandColor: Record<string, string> = { green: c.green, amber: c.amber, red: c.red };
  const high = p.band_counts.red ?? 0;
  const highShare = p.n_customers ? high / p.n_customers : 0;

  const segs = p.by_segment
    .map((s) => ({ raw: s.segment_name, name: segLabel(s.segment_name), value: s.revenue_at_risk, customers: s.customers }))
    .sort((a, b) => b.value - a.value);
  const top = segs[0];
  const topShare = top && p.total_revenue_at_risk ? top.value / p.total_revenue_at_risk : 0;

  // Forecast series. Manager view smooths the spiky weekly history with a trailing average.
  const raw: ForecastPoint[] = forecast.data!.points;
  const actuals: number[] = [];
  const pts = raw.map((d) => {
    if (d.actual != null) actuals.push(d.actual);
    const win = actuals.slice(-WINDOW);
    const avg = d.actual != null ? win.reduce((s, x) => s + x, 0) / win.length : null;
    return {
      month: isManager ? d.month.slice(0, 10) : d.month.slice(0, 7),
      Actual: isManager ? avg : d.actual,
      Raw: d.actual,
      Forecast: d.forecast,
      Lower: d.lower,
      Upper: d.upper,
    };
  });
  const sumForecast = (r: typeof doNothing) => (r.data?.points ?? []).reduce((s, d) => s + (d.forecast ?? 0), 0);
  const gain = sumForecast(withBudget) - sumForecast(doNothing);
  const weeks = (doNothing.data?.points ?? []).filter((d) => d.forecast != null).length;

  const kpiSaved = lastAllocation
    ? <KpiCard label="Revenue saved with current budget" value={money(lastAllocation.expected_revenue_saved)} tone="positive" />
    : <KpiCard label="Customer groups" value={p.by_segment.length} />;

  const bandCards = isManager ? (
    <>
      <KpiCard label="Customers" value={p.n_customers} />
      <KpiCard
        label="Revenue at risk"
        info={<InfoTip text={GLOSSARY.revenueAtRisk} />}
        value={money(p.total_revenue_at_risk)}
      />
      <KpiCard
        label="High-risk customers"
        info={<InfoTip text={GLOSSARY.band} />}
        value={high}
        delta={`${Math.round(highShare * 100)}% of customers`}
      />
      {kpiSaved}
    </>
  ) : (
    <>
      <KpiCard label="Customers" value={p.n_customers} />
      <KpiCard label="Revenue at risk" value={p.total_revenue_at_risk} />
      <KpiCard label="Red band" value={p.band_counts.red ?? 0} />
      <KpiCard label="Segments" value={p.by_segment.length} />
    </>
  );

  const pie = (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={bands}
          dataKey="value"
          nameKey="name"
          innerRadius={55}
          outerRadius={85}
          stroke={c.surface100}
          cursor="pointer"
          onClick={(d) => openCustomers({ band: d.name as Band })}
        >
          {bands.map((b) => <Cell key={b.name} fill={bandColor[b.name] ?? c.purple} />)}
        </Pie>
        <Tooltip
          {...tip}
          formatter={(v, _n, item) =>
            isManager
              ? [`${fmtMoney(Number(v))} (${Math.round((Number(v) / p.n_customers) * 100)}%)`, riskWord(item.payload.name as Band)]
              : [String(v), item.payload.name as string]
          }
        />
        {!isManager && <Legend wrapperStyle={{ color: c.inkMuted }} />}
      </PieChart>
    </ResponsiveContainer>
  );

  return (
    <>
      <Headline>
        <Key>{fmtMoney(high)} customers</Key> are at high risk of leaving. Together, customers put{" "}
        <Key>{money(p.total_revenue_at_risk)}</Key> of revenue at risk.
        {top && (
          <>
            {" "}
            <Key>{top.name}</Key> carry the largest share (<Key>{Math.round(topShare * 100)}%</Key>).
          </>
        )}
      </Headline>

      <div className="grid-kpi">{bandCards}</div>

      <div className="grid-2">
        {isManager ? (
          <Panel title="How many customers are at risk" note="Click a slice or a row to see those customers.">
            <div className="relative">
              {pie}
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="t-kpi">{fmtMoney(high)}</span>
                <span className="t-caption">high risk</span>
              </div>
            </div>
            <ul className="m-0 mt-2 grid list-none gap-1 p-0">
              {[...bands].reverse().map((b) => (
                <li key={b.name}>
                  <button
                    type="button"
                    onClick={() => openCustomers({ band: b.name as Band })}
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-[14px] hover:bg-surface-300"
                  >
                    <span className="inline-block h-2 w-2 rounded-pill" style={{ background: bandColor[b.name] }} />
                    <span>{riskWord(b.name as Band)}</span>
                    <span className="ml-auto tabular-nums">
                      {fmtMoney(b.value)} ({Math.round((b.value / p.n_customers) * 100)}%)
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        ) : (
          <Panel title="Risk bands">{pie}</Panel>
        )}

        <Panel
          title={isManager ? "Where the revenue at risk is" : "Revenue at risk by segment"}
          note={isManager ? `Revenue at risk in ${CUSTOMER_CURRENCY}. Click a bar to see the customers in that group.` : undefined}
        >
          <ResponsiveContainer width="100%" height={isManager ? Math.max(240, segs.length * 34 + 30) : 240}>
            <BarChart
              data={isManager ? segs : p.by_segment}
              layout="vertical"
              margin={isManager ? { right: narrow ? 44 : 52 } : undefined}
            >
              {isManager ? (
                <XAxis type="number" hide />
              ) : (
                <XAxis type="number" tickFormatter={(v) => fmtMoney(v)} tick={axis} stroke={c.axis} />
              )}
              {isManager ? (
                <YAxis
                  type="category"
                  dataKey="name"
                  width={narrow ? 120 : 250}
                  tickLine={false}
                  axisLine={false}
                  tick={<SegmentTick max={narrow ? 19 : 45} />}
                  interval={0}
                />
              ) : (
                <YAxis type="category" dataKey="segment_name" width={140} tick={axis} stroke={c.axis} />
              )}
              <Tooltip
                {...tip}
                cursor={{ fill: c.grid }}
                formatter={(v, _n, item) =>
                  isManager
                    ? [`${moneyFull(Number(v))} (${Math.round((Number(v) / p.total_revenue_at_risk) * 100)}% of total)`, item.payload.name as string]
                    : fmtMoney(Number(v))
                }
              />
              <Bar
                dataKey={isManager ? "value" : "revenue_at_risk"}
                fill={c.forecast}
                radius={[0, 4, 4, 0]}
                cursor="pointer"
                onClick={(d) => openCustomers({ segment: (d as unknown as { raw?: string; segment_name?: string }).raw ?? (d as unknown as { segment_name: string }).segment_name })}
              >
                {isManager && (
                  <LabelList dataKey="value" position="right" formatter={(v: number) => money(v)} fill={c.ink} fontSize={11} />
                )}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title={isManager ? "Expected weekly revenue" : "Revenue at risk forecast"}
        actions={
          <SegmentedControl
            label="Forecast scenario"
            options={
              isManager
                ? [
                    { value: "no_intervention", label: "If we do nothing" },
                    { value: "with_allocation", label: "If we spend the budget" },
                  ]
                : [
                    { value: "no_intervention", label: "No intervention" },
                    { value: "with_allocation", label: "With allocation" },
                  ]
            }
            value={scenario}
            onChange={setScenario}
          />
        }
        note={
          isManager
            ? `Weekly revenue in ${FORECAST_CURRENCY}, week by week. Solid line: past weeks (4-week average, with the raw weeks faint behind it). Dashed line: forecast, after the revenue we expect to lose to churn. Dotted lines: likely range. ${
                gain >= 0 ? "Spending the budget raises" : "Spending the budget lowers"
              } expected revenue by ${money(Math.abs(gain), FORECAST_CURRENCY)} over the ${weeks} forecast weeks.`
            : undefined
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={pts}>
            <CartesianGrid stroke={c.grid} />
            <XAxis
              dataKey="month"
              tick={axis}
              stroke={c.axis}
              tickFormatter={isManager ? weekTick : undefined}
              minTickGap={isManager ? 40 : 5}
            />
            <YAxis tickFormatter={(v) => (isManager ? money(v, FORECAST_CURRENCY) : fmtMoney(v))} tick={axis} stroke={c.axis} width={isManager ? 62 : 60} />
            <Tooltip
              {...tip}
              labelFormatter={isManager ? (l) => `Week ending ${weekText(String(l))}` : undefined}
              formatter={(v) => (isManager ? moneyFull(Number(v), FORECAST_CURRENCY) : fmtMoney(Number(v)))}
            />
            <Legend wrapperStyle={{ color: c.inkMuted }} />
            {isManager && <Line dataKey="Raw" name="Raw weekly revenue" stroke={c.actual} strokeOpacity={0.3} strokeWidth={1} dot={false} />}
            <Line dataKey="Actual" name={isManager ? "Past revenue (4-week average)" : "Actual"} stroke={c.actual} strokeWidth={1.5} dot={false} />
            <Line
              dataKey="Forecast"
              name={isManager ? "Forecast" : "Forecast"}
              stroke={c.forecast}
              strokeWidth={2}
              strokeDasharray={isManager ? "6 4" : undefined}
              dot={false}
            />
            <Line dataKey="Lower" name={isManager ? "Likely range (low)" : "Lower"} stroke={c.interval} strokeDasharray="2 4" dot={false} />
            <Line dataKey="Upper" name={isManager ? "Likely range (high)" : "Upper"} stroke={c.interval} strokeDasharray="2 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>
    </>
  );
}
