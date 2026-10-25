import type { ReactNode } from "react";

export interface KpiCardProps {
  label: string;
  info?: ReactNode;
  value: number | string;
  unit?: string;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  tone?: "positive" | "highlight";
}

const DELTA: Record<string, string> = { up: "text-green", down: "text-red", neutral: "text-ink-muted" };

export function KpiCard({ label, info, value, unit, delta, deltaTone = "neutral", tone }: KpiCardProps) {
  const shown = typeof value === "number" ? value.toLocaleString("en-US", { maximumFractionDigits: 0 }) : value;
  const ground =
    tone === "positive"
      ? "border-green-soft bg-green-soft shadow-panel"
      : tone === "highlight"
        ? "border-line-100 bg-surface-200 shadow-glow-gold"
        : "border-line-100 bg-surface-200 shadow-panel";
  return (
    <div className={`min-w-0 rounded-md border p-4 ${ground}`}>
      <div className={`t-label ${tone === "highlight" ? "text-gold" : ""}`}>{label}{info}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-1">
        <span className={`t-kpi ${tone === "positive" ? "text-green" : "text-ink"}`}>{shown}</span>
        {unit && <span className="text-[12px] text-ink-muted">{unit}</span>}
        {delta && <span className={`ml-2 text-[12px] font-semibold ${DELTA[deltaTone]}`}>{delta}</span>}
      </div>
    </div>
  );
}
